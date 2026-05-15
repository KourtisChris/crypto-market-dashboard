# ============================================================
# backend/feeds/binance.py
# Real-time prices via WebSocket + candle opens via REST
# ============================================================

import asyncio
import json
import logging
import time
import aiohttp
import websockets
from config import BINANCE_WS_BASE, BINANCE_REST_BASE, TIMEFRAMES

logger = logging.getLogger(__name__)

# candle open cache: "SYMBOL_TF" → open_price
_opens:    dict[str, float] = {}
_opens_ts: dict[str, float] = {}

CANDLE_TTL = {"1M": 60, "1H": 3600, "1D": 86400, "1W": 604800}


class BinanceFeed:
    def __init__(self, state: dict):
        self.state = state

    async def run(self):
        await asyncio.gather(
            self._ws_loop(),
            self._candle_refresh_loop(),
        )

    # ----------------------------------------------------------
    # WebSocket — real-time prices
    # ----------------------------------------------------------
    async def _ws_loop(self):
        # Wait for top100 to load first
        for _ in range(30):
            if self.state.get("top100"):
                break
            await asyncio.sleep(2)

        while True:
            try:
                streams = self._build_streams()
                if not streams:
                    await asyncio.sleep(10)
                    continue
                url = BINANCE_WS_BASE + "/".join(streams)
                logger.info(f"[Binance WS] Connecting — {len(streams)} streams")
                async with websockets.connect(url, ping_interval=20) as ws:
                    async for raw in ws:
                        self._handle_tick(json.loads(raw))
            except Exception as e:
                logger.error(f"[Binance WS] {e} — reconnecting in 5s")
                await asyncio.sleep(5)

    def _build_streams(self) -> list[str]:
        streams = {"btcusdt@ticker", "ethusdt@ticker", "ethbtc@ticker"}
        for coin in self.state.get("top100", []):
            sym = coin["symbol"]
            if sym in ("BTC", "ETH"):
                continue
            streams.add(f"{sym.lower()}usdt@ticker")
            if coin["direct_btc"]:
                streams.add(f"{sym.lower()}btc@ticker")
        return list(streams)

    def _handle_tick(self, msg: dict):
        data   = msg.get("data", msg)
        symbol = data.get("s", "").upper()
        price  = float(data.get("c", 0))
        if symbol and price:
            self.state.setdefault("prices", {})[symbol] = price

    # ----------------------------------------------------------
    # Candle opens — refreshed when TTL expires
    # ----------------------------------------------------------
    async def _candle_refresh_loop(self):
        while True:
            symbols = self._all_symbols()
            await self._refresh(symbols)
            await asyncio.sleep(60)   # check every minute (needed for 1M TF)

    def _all_symbols(self) -> set[str]:
        syms = {"BTCUSDT", "ETHUSDT", "ETHBTC"}
        for coin in self.state.get("top100", []):
            sym = coin["symbol"]
            if sym in ("BTC", "ETH"):
                continue
            syms.add(f"{sym}USDT")
            if coin["direct_btc"]:
                syms.add(f"{sym}BTC")
        return syms

    async def _refresh(self, symbols: set[str]):
        now = time.time()
        async with aiohttp.ClientSession() as session:
            tasks = []
            for symbol in symbols:
                for tf, interval in TIMEFRAMES.items():
                    key = f"{symbol}_{tf}"
                    if now - _opens_ts.get(key, 0) > CANDLE_TTL[tf]:
                        tasks.append(self._fetch_open(session, symbol, tf, interval))
            for i in range(0, len(tasks), 20):
                await asyncio.gather(*tasks[i:i+20])
                await asyncio.sleep(0.3)
            if tasks:
                logger.info(f"[Binance REST] Refreshed {len(tasks)} candle opens")

    async def _fetch_open(self, session, symbol: str, tf: str, interval: str):
        try:
            async with session.get(
                f"{BINANCE_REST_BASE}/klines",
                params={"symbol": symbol, "interval": interval, "limit": 1}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        key = f"{symbol}_{tf}"
                        _opens[key]    = float(data[0][1])   # index 1 = open price
                        _opens_ts[key] = time.time()
        except Exception as e:
            logger.debug(f"[Binance REST] {symbol} {tf}: {e}")


# ----------------------------------------------------------
# Public helpers — used by signals engine
# ----------------------------------------------------------
def get_pct_change(symbol: str, tf: str, prices: dict) -> float | None:
    """% change of a symbol from candle open to current price."""
    open_p = _opens.get(f"{symbol}_{tf}")
    close  = prices.get(symbol)
    if not open_p or not close or open_p == 0:
        return None
    return (close - open_p) / open_p * 100


def get_altbtc_pct(alt_symbol: str, tf: str, prices: dict) -> float | None:
    """
    ALT/BTC % change for rank 51-100 coins (no direct BTC pair).
    Calculated as: (ALT/BTC ratio now) vs (ALT/BTC ratio at candle open).
    """
    alt_usdt = prices.get(f"{alt_symbol}USDT")
    btc_usdt = prices.get("BTCUSDT")
    if not alt_usdt or not btc_usdt or btc_usdt == 0:
        return None
    alt_open = _opens.get(f"{alt_symbol}USDT_{tf}")
    btc_open = _opens.get(f"BTCUSDT_{tf}")
    if not alt_open or not btc_open or btc_open == 0:
        return None
    ratio_now  = alt_usdt / btc_usdt
    ratio_open = alt_open / btc_open
    if ratio_open == 0:
        return None
    return (ratio_now - ratio_open) / ratio_open * 100

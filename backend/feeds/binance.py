# ============================================================
# backend/feeds/binance.py
# Real-time prices via WebSocket + candle opens via REST
# + 24h volume + funding rate
# ============================================================

import asyncio
import json
import logging
import time
import aiohttp
import websockets
from config import (
    BINANCE_WS_BASE, BINANCE_REST_BASE, BINANCE_FUTURES_BASE,
    TIMEFRAMES, VOLUME_FUNDING_REFRESH_S,
)

logger = logging.getLogger(__name__)

# candle open cache: "SYMBOL_TF" → open_price
_opens:    dict[str, float] = {}
_opens_ts: dict[str, float] = {}

CANDLE_TTL = {"1M": 60, "1H": 3600, "1D": 86400, "1W": 604800}

# volume & funding rate cache
_volume_data: dict = {
    "btc_24h":   0.0,
    "alt_24h":   0.0,
    "total_24h": 0.0,
    "timestamp": 0.0,
    "stale":     True,
}
_funding_data: dict = {
    "rate":      None,
    "timestamp": 0.0,
    "stale":     True,
}


class BinanceFeed:
    def __init__(self, state: dict):
        self.state = state

    async def run(self):
        await asyncio.gather(
            self._ws_loop(),
            self._candle_refresh_loop(),
            self._volume_funding_loop(),
        )

    # ----------------------------------------------------------
    # WebSocket — real-time prices
    # ----------------------------------------------------------
    async def _ws_loop(self):
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
            await asyncio.sleep(60)

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
                        _opens[key]    = float(data[0][1])
                        _opens_ts[key] = time.time()
        except Exception as e:
            logger.debug(f"[Binance REST] {symbol} {tf}: {e}")

    # ----------------------------------------------------------
    # Volume + Funding Rate — refreshed every 60s
    # ----------------------------------------------------------
    async def _volume_funding_loop(self):
        while True:
            try:
                await asyncio.gather(
                    self._fetch_volume(),
                    self._fetch_funding_rate(),
                )
            except Exception as e:
                logger.error(f"[Binance] Volume/Funding error: {e}")
            await asyncio.sleep(VOLUME_FUNDING_REFRESH_S)

    async def _fetch_volume(self):
        """Fetch 24h volume for BTC and top alts from Binance ticker."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BINANCE_REST_BASE}/ticker/24hr"
                ) as resp:
                    if resp.status != 200:
                        _volume_data["stale"] = True
                        return
                    tickers = await resp.json()

            btc_vol   = 0.0
            alt_vol   = 0.0
            total_vol = 0.0

            # Get top100 symbols for alt volume calculation
            top100_syms = {
                c["symbol"] for c in self.state.get("top100", [])
                if c["symbol"] not in ("BTC", "ETH")
            }

            for t in tickers:
                sym    = t.get("symbol", "")
                vol_usd = float(t.get("quoteVolume", 0))

                if sym == "BTCUSDT":
                    btc_vol = vol_usd
                elif sym.endswith("USDT"):
                    base = sym[:-4]
                    total_vol += vol_usd
                    if base in top100_syms:
                        alt_vol += vol_usd

            _volume_data["btc_24h"]   = btc_vol
            _volume_data["alt_24h"]   = alt_vol
            _volume_data["total_24h"] = total_vol
            _volume_data["timestamp"] = time.time()
            _volume_data["stale"]     = False

            # Store in state for engine access
            self.state["volume"] = dict(_volume_data)
            logger.debug(f"[Binance] Volume — BTC: ${btc_vol/1e9:.1f}B Alt: ${alt_vol/1e9:.1f}B")

        except Exception as e:
            _volume_data["stale"] = True
            logger.error(f"[Binance] Volume fetch error: {e}")

    async def _fetch_funding_rate(self):
        """Fetch latest funding rate for BTCUSDT from Binance Futures."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BINANCE_FUTURES_BASE}/fapi/v1/fundingRate",
                    params={"symbol": "BTCUSDT", "limit": 1}
                ) as resp:
                    if resp.status != 200:
                        _funding_data["stale"] = True
                        return
                    data = await resp.json()

            if data:
                rate = float(data[0].get("fundingRate", 0))
                _funding_data["rate"]      = rate
                _funding_data["timestamp"] = time.time()
                _funding_data["stale"]     = False
                self.state["funding"] = dict(_funding_data)
                logger.debug(f"[Binance] Funding rate: {rate:.4%}")

        except Exception as e:
            _funding_data["stale"] = True
            logger.error(f"[Binance] Funding rate error: {e}")


# ----------------------------------------------------------
# Public helpers — used by signals engine
# ----------------------------------------------------------
def get_pct_change(symbol: str, tf: str, prices: dict) -> float | None:
    open_p = _opens.get(f"{symbol}_{tf}")
    close  = prices.get(symbol)
    if not open_p or not close or open_p == 0:
        return None
    return (close - open_p) / open_p * 100


def get_altbtc_pct(alt_symbol: str, tf: str, prices: dict) -> float | None:
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


def get_volume_data() -> dict:
    return _volume_data


def get_funding_data() -> dict:
    return _funding_data

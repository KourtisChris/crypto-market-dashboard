# ============================================================
# backend/feeds/coingecko.py
# Global metrics: BTC.D (CMC), TOTAL/TOTAL2/TOTAL3 (CoinGecko)
# Top 100 coin list (CoinGecko)
# Candle opens approximated from BTC ratio
# ============================================================

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
import aiohttp
from config import (
    COINGECKO_BASE, COINGECKO_API_KEY, COINGECKO_REFRESH_SECONDS,
    TOP_TOTAL, TOP_DIRECT_BTC, CMC_BASE, CMC_API_KEY,
    BINANCE_REST_BASE, STABLECOINS, TIMEFRAMES,
)

logger = logging.getLogger(__name__)

# global candle open cache: "{key}_{TF}" → (value, candle_start_ts)
_global_opens: dict[str, tuple[float, int]] = {}

_BINANCE_INTERVAL = {"1M": "1m", "1H": "1h", "1D": "1d", "1W": "1w"}


def _candle_start_ts(tf: str) -> int:
    """Returns Unix timestamp of the start of the current candle (UTC)."""
    now = datetime.now(timezone.utc)
    if tf == "1M":
        dt = now.replace(second=0, microsecond=0)
    elif tf == "1H":
        dt = now.replace(minute=0, second=0, microsecond=0)
    elif tf == "1D":
        dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # 1W — starts on Monday
        dt = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    return int(dt.timestamp())


def update_global_opens(btcd: float, total2: float, total3: float,
                         others_d: float, total: float):
    """Called every 5 min. Updates open only when candle changes."""
    for tf in TIMEFRAMES:
        ts = _candle_start_ts(tf)
        for key, val in [("btcd", btcd), ("total2", total2), ("total3", total3),
                         ("others_d", others_d), ("total", total)]:
            cache_key = f"{key}_{tf}"
            existing  = _global_opens.get(cache_key)
            if existing is None or existing[1] != ts:
                _global_opens[cache_key] = (val, ts)
                logger.debug(f"[GlobalOpen] New candle: {cache_key} = {val:.4f}")


def set_global_open(key: str, tf: str, value: float):
    _global_opens[f"{key}_{tf}"] = (value, _candle_start_ts(tf))
    logger.info(f"[GlobalOpen] {key}_{tf} = {value:.4f}")


def get_global_pct_change(key: str, tf: str, current: float) -> float:
    """% change from candle open to current value."""
    existing = _global_opens.get(f"{key}_{tf}")
    if not existing or existing[0] == 0:
        return 0.0
    return (current - existing[0]) / existing[0] * 100


class CoinGeckoFeed:
    def __init__(self, state: dict):
        self.state       = state
        self.cg_headers  = {
            "accept": "application/json",
            "x-cg-demo-api-key": COINGECKO_API_KEY,
        }
        self.cmc_headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": CMC_API_KEY,
        }

    async def run(self):
        async with aiohttp.ClientSession() as session:
            await self._load_opens(session)
        while True:
            try:
                await self._fetch_all()
            except Exception as e:
                logger.error(f"[CoinGecko] {e}")
            await asyncio.sleep(COINGECKO_REFRESH_SECONDS)

    # ----------------------------------------------------------
    # Startup: load candle opens via BTC ratio approximation
    # Logic: BTC open from Binance REST → scale global metrics
    # proportionally. Accurate enough for 1H/1D/1W.
    # For 1M we use the same approach but with 1m candle.
    # ----------------------------------------------------------
    async def _load_opens(self, session):
        logger.info("[GlobalOpen] Loading candle opens from Binance...")
        try:
            btc_now  = await self._btc_price_now(session)
            btcd_now = await self._btcd_from_cmc(session)
            cg       = await self._cg_global_raw(session)
            if not all([btc_now, btcd_now, cg]):
                logger.warning("[GlobalOpen] Missing data — skipping")
                return
            for tf in TIMEFRAMES:
                btc_open = await self._btc_candle_open(session, _BINANCE_INTERVAL[tf])
                if not btc_open:
                    continue
                ratio = btc_open / btc_now
                set_global_open("btcd",     tf, btcd_now          * ratio)
                set_global_open("total",    tf, cg["total"]       * ratio)
                set_global_open("total2",   tf, cg["total2"]      * ratio)
                set_global_open("total3",   tf, cg["total3"]      * ratio)
                set_global_open("others_d", tf, cg["others_d"])
                logger.info(
                    f"[GlobalOpen] {tf} BTC_open={btc_open:.2f} "
                    f"ratio={ratio:.4f} BTC.D_open={btcd_now*ratio:.2f}%"
                )
            logger.info("[GlobalOpen] Candle opens loaded ✅")
        except Exception as e:
            logger.error(f"[GlobalOpen] {e}")

    async def _btc_price_now(self, session) -> float | None:
        try:
            async with session.get(
                f"{BINANCE_REST_BASE}/ticker/price",
                params={"symbol": "BTCUSDT"}
            ) as r:
                return float((await r.json())["price"]) if r.status == 200 else None
        except:
            return None

    async def _btc_candle_open(self, session, interval: str) -> float | None:
        try:
            async with session.get(
                f"{BINANCE_REST_BASE}/klines",
                params={"symbol": "BTCUSDT", "interval": interval, "limit": 1}
            ) as r:
                data = await r.json()
                return float(data[0][1]) if r.status == 200 and data else None
        except:
            return None

    async def _cg_global_raw(self, session) -> dict | None:
        try:
            async with session.get(
                f"{COINGECKO_BASE}/global", headers=self.cg_headers
            ) as r:
                if r.status != 200:
                    return None
                d     = (await r.json()).get("data", {})
                mc    = d.get("market_cap_percentage", {})
                total = d.get("total_market_cap", {}).get("usd", 0)
                btc_c = total * mc.get("btc", 0) / 100
                eth_c = total * mc.get("eth", 0) / 100
                return {
                    "total":    total,
                    "total2":   total - btc_c,
                    "total3":   total - btc_c - eth_c,
                    "others_d": 100 - mc.get("btc",0) - mc.get("eth",0)
                                    - mc.get("bnb",0) - mc.get("sol",0) - mc.get("xrp",0),
                }
        except:
            return None

    async def _btcd_from_cmc(self, session) -> float | None:
        try:
            async with session.get(
                f"{CMC_BASE}/global-metrics/quotes/latest",
                headers=self.cmc_headers
            ) as r:
                if r.status != 200:
                    return None
                btcd = (await r.json()).get("data", {}).get("btc_dominance")
                if btcd:
                    logger.info(f"[CMC] BTC.D: {btcd:.2f}%")
                return btcd
        except:
            return None

    # ----------------------------------------------------------
    # Periodic fetch (every 5 min)
    # ----------------------------------------------------------
    async def _fetch_all(self):
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                self._fetch_global(session),
                self._fetch_top100(session),
            )

    async def _fetch_global(self, session):
        btcd = await self._btcd_from_cmc(session)
        cg   = await self._cg_global_raw(session)
        if not cg:
            return
        if btcd is None:
            btcd = 0.0
        update_global_opens(btcd, cg["total2"], cg["total3"], cg["others_d"], cg["total"])
        self.state["global"] = {
            "btcd":      btcd,
            "total":     cg["total"],
            "total2":    cg["total2"],
            "total3":    cg["total3"],
            "others_d":  cg["others_d"],
            "timestamp": time.time(),
        }
        logger.info(f"[CoinGecko] Global — BTC.D: {btcd:.2f}%")

    async def _fetch_top100(self, session):
        params = {
            "vs_currency": "usd",
            "order":       "market_cap_desc",
            "per_page":    TOP_TOTAL,
            "page":        1,
            "sparkline":   "false",
        }
        async with session.get(
            f"{COINGECKO_BASE}/coins/markets",
            headers=self.cg_headers, params=params
        ) as r:
            if r.status != 200:
                return
            coins  = await r.json()
            top100 = []
            for rank, coin in enumerate(coins, 1):
                sym = coin.get("symbol", "").upper()
                if sym in STABLECOINS:
                    continue
                top100.append({
                    "rank":       rank,
                    "symbol":     sym,
                    "direct_btc": rank <= TOP_DIRECT_BTC,
                })
            self.state["top100"] = top100
            logger.info(f"[CoinGecko] Top100 — {len(top100)} coins")

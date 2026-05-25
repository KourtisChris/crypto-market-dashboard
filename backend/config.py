# ============================================================
# backend/config.py
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# --- Credentials ---
DATABASE_URL      = os.getenv("DATABASE_URL")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
CMC_API_KEY       = os.getenv("CMC_API_KEY")
VAPID_PUBLIC_KEY  = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL       = os.getenv("VAPID_EMAIL", "mailto:admin@example.com")

# --- External APIs ---
BINANCE_WS_BASE      = "wss://stream.binance.com:9443/stream?streams="
BINANCE_REST_BASE    = "https://api.binance.com/api/v3"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"
COINGECKO_BASE       = "https://api.coingecko.com/api/v3"
CMC_BASE             = "https://pro-api.coinmarketcap.com/v1"
FEAR_GREED_BASE      = "https://api.alternative.me"

# --- Refresh intervals ---
COINGECKO_REFRESH_SECONDS  = 300   # 5 min
ENGINE_CHECK_SECONDS       = 60    # engine runs every 60s
VOLUME_FUNDING_REFRESH_S   = 60    # volume + funding rate
FEAR_GREED_REFRESH_S       = 3600  # fear & greed (1h)

# --- Timeframes ---
TIMEFRAMES = {
    "1M": "1m",
    "1H": "1h",
    "1D": "1d",
    "1W": "1w",
}

# --- Signal thresholds (primary criteria) ---
THRESHOLD_MULTIPLIER = 0.25
THRESHOLDS = {
    "1M": {
        "btc":    0.06 * THRESHOLD_MULTIPLIER ,
        "btcd":   0.0075 * THRESHOLD_MULTIPLIER ,
        "total2": 0.05 * THRESHOLD_MULTIPLIER ,
        "ethbtc": 0.03 * THRESHOLD_MULTIPLIER ,
    },
    "1H": {
        "btc":    0.5 * THRESHOLD_MULTIPLIER,
        "btcd":   0.075 * THRESHOLD_MULTIPLIER,
        "total2": 0.6 * THRESHOLD_MULTIPLIER,
        "ethbtc": 0.4 * THRESHOLD_MULTIPLIER,
    },
    "1D": {
        "btc":    1.5 * THRESHOLD_MULTIPLIER,
        "btcd":   0.25 * THRESHOLD_MULTIPLIER,
        "total2": 2.0 * THRESHOLD_MULTIPLIER,
        "ethbtc": 1.25 * THRESHOLD_MULTIPLIER,
    },
    "1W": {
        "btc":    3.5 * THRESHOLD_MULTIPLIER,
        "btcd":   0.7 * THRESHOLD_MULTIPLIER,
        "total2": 4.0 * THRESHOLD_MULTIPLIER,
        "ethbtc": 2.5 * THRESHOLD_MULTIPLIER,
    },
}

LATE_ALTS_BTCD_LEVEL = 57.0

# --- Confirmation thresholds ---

# Funding rate
FUNDING_DEEPLY_NEGATIVE = -0.0003   # < -0.03%
FUNDING_NEGATIVE        = 0.0
FUNDING_NEUTRAL_MIN     = -0.0001
FUNDING_NEUTRAL_MAX     = 0.0002
FUNDING_HIGH_POSITIVE   = 0.0003    # > +0.03%

# Fear & Greed
FEAR_GREED_EXTREME_FEAR  = 20
FEAR_GREED_FEAR          = 40
FEAR_GREED_NEUTRAL_MAX   = 60
FEAR_GREED_GREED_MAX     = 75
# extreme greed >= 75

# Stable dominance change (pp in last ~1h window)
STABLE_D_SHARPLY_RISING  = 0.5    # +0.5pp
STABLE_D_RISING          = 0.2    # +0.2pp
STABLE_D_FALLING         = -0.2   # -0.2pp
# neutral = within ±0.2pp

# Volume: ratio current / 30d avg
VOLUME_ABOVE_AVG_RATIO   = 1.0    # > 30d avg
VOLUME_BELOW_AVG_RATIO   = 0.85   # < 85% of 30d avg (falling)

# --- Conflict resolution priority (lower = higher priority) ---
SIGNAL_PRIORITY = {
    "Risk Off":    1,
    "Alts Short":  2,
    "BTC Long":    3,
    "Alts Long":   4,
    "ETH Leading": 5,
    "Late Alts":   6,
    "Neutral":     7,
}

# --- Top N coins ---
TOP_DIRECT_BTC = 50
TOP_TOTAL      = 100

# --- Stablecoins & wrapped tokens ---
STABLECOINS = {
    "USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USDD",
    "FRAX", "LUSD", "GUSD", "USDE", "FDUSD",
    "WBTC", "WETH", "WBNB", "STETH", "RETH", "CBETH",
    "LEO", "CRO", "U",
}

_missing = [k for k, v in {
    "DATABASE_URL":      DATABASE_URL,
    "COINGECKO_API_KEY": COINGECKO_API_KEY,
    "CMC_API_KEY":       CMC_API_KEY,
}.items() if not v]

if _missing:
    raise EnvironmentError(f"Missing env vars: {', '.join(_missing)}")

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
BINANCE_WS_BASE   = "wss://stream.binance.com:9443/stream?streams="
BINANCE_REST_BASE = "https://api.binance.com/api/v3"
COINGECKO_BASE    = "https://api.coingecko.com/api/v3"
CMC_BASE          = "https://pro-api.coinmarketcap.com/v1"

# --- Refresh intervals ---
COINGECKO_REFRESH_SECONDS = 300   # 5 min
ENGINE_CHECK_SECONDS      = 60    # 1M engine runs every 60s

# --- Timeframes ---
# label → binance interval string
TIMEFRAMES = {
    "1M": "1m",
    "1H": "1h",
    "1D": "1d",
    "1W": "1w",
}

# --- State thresholds (%) per timeframe ---
# Each state has: btc, btcd, total2, ethbtc
# Values are the minimum % move required to activate a state

# #TEST THRESHOLDS - more noise for testing
THRESHOLD_MULTIPLIER = 2
THRESHOLDS = {
    "1M": {
        "btc":    0.04 * THRESHOLD_MULTIPLIER * 1.5 ,
        "btcd":   0.0075 * THRESHOLD_MULTIPLIER * 1.5 ,
        "total2": 0.05 * THRESHOLD_MULTIPLIER * 1.5 ,
        "ethbtc": 0.03 * THRESHOLD_MULTIPLIER * 1.5 ,
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
# --- Late Alts BTC.D level threshold ---
LATE_ALTS_BTCD_LEVEL = 57.0   # BTC.D below this = late cycle - default: 54

# THRESHOLDS = {
#     "1M": {
#         "btc":    0.08,
#         "btcd":   0.015,
#         "total2": 0.10,
#         "ethbtc": 0.06,
#     },
#     "1H": {
#         "btc":    1.0,
#         "btcd":   0.15,
#         "total2": 1.2,
#         "ethbtc": 0.8,
#     },
#     "1D": {
#         "btc":    3.0,
#         "btcd":   0.50,
#         "total2": 4.0,
#         "ethbtc": 2.5,
#     },
#     "1W": {
#         "btc":    7.0,
#         "btcd":   1.00,
#         "total2": 8.0,
#         "ethbtc": 5.0,
#     },
# }
# # --- Late Alts BTC.D level threshold ---
# LATE_ALTS_BTCD_LEVEL = 57.0   # BTC.D below this = late cycle - default: 54

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

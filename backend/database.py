# ============================================================
# backend/database.py
# ============================================================

import asyncpg
import logging
import os
import json

logger = logging.getLogger(__name__)

_pool = None

DEFAULT_TF_SETTINGS = {"1M": True, "1H": True, "1D": True, "1W": True}


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=1,
        max_size=5,
        ssl="require",
        statement_cache_size=0,
    )
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS state_history (
                id          SERIAL PRIMARY KEY,
                tf          TEXT NOT NULL,
                state_label TEXT NOT NULL,
                state_type  TEXT NOT NULL,
                btc_chg     FLOAT DEFAULT 0,
                btcd_chg    FLOAT DEFAULT 0,
                total2_chg  FLOAT DEFAULT 0,
                ethbtc_chg  FLOAT DEFAULT 0,
                btcd_level  FLOAT DEFAULT 0,
                score       FLOAT DEFAULT 0,
                btc_price   FLOAT DEFAULT 0,
                total2_val  FLOAT DEFAULT 0,
                eth_price   FLOAT DEFAULT 0,
                recorded_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        for col, typ in [("btc_price","FLOAT"),("total2_val","FLOAT"),("eth_price","FLOAT")]:
            await conn.execute(f"""
                ALTER TABLE state_history
                ADD COLUMN IF NOT EXISTS {col} {typ} DEFAULT 0
            """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sh_tf_ts
            ON state_history (tf, recorded_at DESC)
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id         SERIAL PRIMARY KEY,
                endpoint   TEXT UNIQUE NOT NULL,
                p256dh     TEXT NOT NULL,
                auth       TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS heatmap_history (
                id          SERIAL PRIMARY KEY,
                tf          TEXT NOT NULL,
                state_label TEXT NOT NULL,
                state_type  TEXT NOT NULL,
                recorded_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hh_tf_ts
            ON heatmap_history (tf, recorded_at DESC)
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_subscribers (
                chat_id     TEXT PRIMARY KEY,
                joined_at   TIMESTAMPTZ DEFAULT NOW(),
                tf_settings TEXT DEFAULT '{}'
            )
        """)
        await conn.execute("""
            ALTER TABLE telegram_subscribers
            ADD COLUMN IF NOT EXISTS tf_settings TEXT DEFAULT '{}'
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS volume_history (
                id          SERIAL PRIMARY KEY,
                btc_24h     FLOAT DEFAULT 0,
                alt_24h     FLOAT DEFAULT 0,
                total_24h   FLOAT DEFAULT 0,
                recorded_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vh_ts
            ON volume_history (recorded_at DESC)
        """)
    logger.info("[DB] Initialized ✅")


# ----------------------------------------------------------
# State History
# ----------------------------------------------------------
async def record_state(tf: str, state_label: str, state_type: str,
                       metrics=None, score: float = 0.0,
                       btc_price: float = 0.0, total2_val: float = 0.0,
                       eth_price: float = 0.0):
    btc_chg = btcd_chg = total2_chg = ethbtc_chg = btcd_level = 0.0
    if metrics:
        btc_chg    = round(metrics.btc_chg,    4)
        btcd_chg   = round(metrics.btcd_chg,   4)
        total2_chg = round(metrics.total2_chg, 4)
        ethbtc_chg = round(metrics.ethbtc_chg, 4)
        btcd_level = round(metrics.btcd_level,  4)
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO state_history
                (tf, state_label, state_type, btc_chg, btcd_chg,
                 total2_chg, ethbtc_chg, btcd_level, score,
                 btc_price, total2_val, eth_price)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """, tf, state_label, state_type,
            btc_chg, btcd_chg, total2_chg, ethbtc_chg, btcd_level,
            round(score, 4),
            round(btc_price, 2), round(total2_val, 0), round(eth_price, 4))
    logger.info(f"[DB] State recorded: [{tf}] {state_label} (score: {score:.3f})")


async def get_state_history(tf: str, limit: int = 50) -> list[dict]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, tf, state_label, state_type,
                   btc_chg, btcd_chg, total2_chg, ethbtc_chg,
                   btcd_level, score, recorded_at
            FROM state_history WHERE tf = $1
            ORDER BY recorded_at DESC LIMIT $2
        """, tf, limit)
    return [dict(r) for r in rows]


async def get_latest_states() -> dict:
    result = {}
    async with _pool.acquire() as conn:
        for tf in ["1M", "1H", "1D", "1W"]:
            row = await conn.fetchrow("""
                SELECT state_label, state_type, recorded_at,
                       btc_price, total2_val, eth_price
                FROM state_history WHERE tf = $1
                ORDER BY recorded_at DESC LIMIT 1
            """, tf)
            result[tf] = dict(row) if row else None
    return result


async def get_latest_state(tf: str) -> dict | None:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT state_label, state_type, score, recorded_at
            FROM state_history WHERE tf = $1
            ORDER BY recorded_at DESC LIMIT 1
        """, tf)
    return dict(row) if row else None


# ----------------------------------------------------------
# Heatmap History
# ----------------------------------------------------------
async def record_heatmap_state(tf: str, state_label: str, state_type: str):
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO heatmap_history (tf, state_label, state_type)
            VALUES ($1, $2, $3)
        """, tf, state_label, state_type)


async def get_heatmap_data(tf: str, interval: str = None) -> list[dict]:
    trunc_map = {"1M": "minute", "1H": "hour", "1D": "day", "1W": "week"}
    default_intervals = {
        "1M": "24 hours",
        "1H": "168 hours",
        "1D": "180 days",
        "1W": "156 weeks",
    }
    trunc         = trunc_map[tf]
    used_interval = interval if interval else default_intervals[tf]

    async with _pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT DISTINCT ON (date_trunc('{trunc}', recorded_at))
                date_trunc('{trunc}', recorded_at) AS period,
                state_label, state_type
            FROM heatmap_history
            WHERE tf = $1 AND recorded_at >= NOW() - INTERVAL '{used_interval}'
            ORDER BY date_trunc('{trunc}', recorded_at) DESC, recorded_at DESC
        """, tf)
    return [dict(r) for r in rows]


# ----------------------------------------------------------
# Volume History (30-day rolling average)
# ----------------------------------------------------------
async def record_volume(btc_24h: float, alt_24h: float, total_24h: float):
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO volume_history (btc_24h, alt_24h, total_24h)
            VALUES ($1, $2, $3)
        """, btc_24h, alt_24h, total_24h)
    async with _pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM volume_history
            WHERE recorded_at < NOW() - INTERVAL '31 days'
        """)


async def get_volume_averages() -> dict:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                AVG(btc_24h)   AS btc_24h,
                AVG(alt_24h)   AS alt_24h,
                AVG(total_24h) AS total_24h,
                COUNT(*)       AS cnt
            FROM volume_history
            WHERE recorded_at >= NOW() - INTERVAL '30 days'
        """)
    if not row or row["cnt"] < 24:
        return {}
    return {
        "btc_24h":   float(row["btc_24h"]   or 0),
        "alt_24h":   float(row["alt_24h"]   or 0),
        "total_24h": float(row["total_24h"] or 0),
    }


# ----------------------------------------------------------
# Telegram Subscribers
# ----------------------------------------------------------
async def add_telegram_subscriber(chat_id: str):
    default = json.dumps(DEFAULT_TF_SETTINGS)
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO telegram_subscribers (chat_id, tf_settings)
            VALUES ($1, $2) ON CONFLICT (chat_id) DO NOTHING
        """, chat_id, default)
    logger.info(f"[Telegram] Subscriber added: {chat_id}")


async def remove_telegram_subscriber(chat_id: str):
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM telegram_subscribers WHERE chat_id = $1", chat_id
        )
    logger.info(f"[Telegram] Subscriber removed: {chat_id}")


async def get_telegram_subscribers() -> list[str]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT chat_id FROM telegram_subscribers")
    return [row["chat_id"] for row in rows]


async def get_subscriber_tf_settings(chat_id: str) -> dict:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tf_settings FROM telegram_subscribers WHERE chat_id = $1",
            chat_id
        )
    if not row or not row["tf_settings"]:
        return dict(DEFAULT_TF_SETTINGS)
    try:
        settings = json.loads(row["tf_settings"])
        for tf in DEFAULT_TF_SETTINGS:
            if tf not in settings:
                settings[tf] = True
        return settings
    except:
        return dict(DEFAULT_TF_SETTINGS)


async def update_subscriber_tf_settings(chat_id: str, settings: dict):
    async with _pool.acquire() as conn:
        await conn.execute("""
            UPDATE telegram_subscribers
            SET tf_settings = $2
            WHERE chat_id = $1
        """, chat_id, json.dumps(settings))


async def get_subscribers_for_tf(tf: str) -> list[str]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT chat_id, tf_settings FROM telegram_subscribers"
        )
    result = []
    for row in rows:
        try:
            settings = json.loads(row["tf_settings"] or "{}")
            if settings.get(tf, True):
                result.append(row["chat_id"])
        except:
            result.append(row["chat_id"])
    return result


# ----------------------------------------------------------
# Web Push
# ----------------------------------------------------------
async def add_push_subscription(endpoint: str, p256dh: str, auth: str):
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO push_subscriptions (endpoint, p256dh, auth)
            VALUES ($1,$2,$3)
            ON CONFLICT (endpoint) DO UPDATE SET p256dh=$2, auth=$3
        """, endpoint, p256dh, auth)


async def remove_push_subscription(endpoint: str):
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint=$1", endpoint
        )


async def get_push_subscriptions() -> list[dict]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT endpoint, p256dh, auth FROM push_subscriptions"
        )
    return [dict(r) for r in rows]
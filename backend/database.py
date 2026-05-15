# ============================================================
# backend/database.py
# ============================================================

import asyncpg
import logging
import os

logger = logging.getLogger(__name__)

_pool = None


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
                recorded_at TIMESTAMPTZ DEFAULT NOW()
            )
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
    logger.info("[DB] Initialized ✅")


# ----------------------------------------------------------
# State History
# ----------------------------------------------------------
async def record_state(tf: str, state_label: str, state_type: str,
                       metrics=None, score: float = 0.0):
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
                 total2_chg, ethbtc_chg, btcd_level, score)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """, tf, state_label, state_type,
            btc_chg, btcd_chg, total2_chg, ethbtc_chg, btcd_level,
            round(score, 4))
    logger.info(f"[DB] State recorded: [{tf}] {state_label} (score: {score:.3f})")


async def get_state_history(tf: str, limit: int = 50) -> list[dict]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, tf, state_label, state_type,
                   btc_chg, btcd_chg, total2_chg, ethbtc_chg,
                   btcd_level, score, recorded_at
            FROM state_history
            WHERE tf = $1
            ORDER BY recorded_at DESC
            LIMIT $2
        """, tf, limit)
    return [dict(r) for r in rows]


async def get_latest_states() -> dict:
    result = {}
    async with _pool.acquire() as conn:
        for tf in ["1M", "1H", "1D", "1W"]:
            row = await conn.fetchrow("""
                SELECT state_label, state_type, recorded_at
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


async def get_heatmap_data(tf: str) -> list[dict]:
    trunc_map    = {"1M": "minute", "1H": "hour",      "1D": "day",      "1W": "week"}
    interval_map = {"1M": "24 hours","1H": "168 hours", "1D": "180 days", "1W": "156 weeks"}
    trunc    = trunc_map[tf]
    interval = interval_map[tf]
    async with _pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT DISTINCT ON (date_trunc('{trunc}', recorded_at))
                date_trunc('{trunc}', recorded_at) AS period,
                state_label, state_type
            FROM state_history
            WHERE tf = $1 AND recorded_at >= NOW() - INTERVAL '{interval}'
            ORDER BY date_trunc('{trunc}', recorded_at) DESC, recorded_at DESC
        """, tf)
    return [dict(r) for r in rows]


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

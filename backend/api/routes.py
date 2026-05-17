# ============================================================
# backend/api/routes.py — REST endpoints
# ============================================================

import time
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import database
from engine.signals import build_metrics, get_market_state, score_coins, get_top_strong, get_top_weak
from config import TIMEFRAMES

logger = logging.getLogger(__name__)

router = APIRouter()

_state: dict = {}

def set_state(s: dict):
    global _state
    _state = s


@router.get("/api/snapshot")
async def snapshot():
    prices = _state.get("prices", {})
    glb    = _state.get("global", {})

    if not prices or not glb:
        return JSONResponse({"error": "Data not ready"}, status_code=503)

    states     = {}
    metrics    = {}
    top_movers = {}

    for tf in TIMEFRAMES:
        m = build_metrics(tf, _state)
        if m is None:
            continue

        result = get_market_state(m, tf)
        states[tf] = {
            "label": result.label,
            "type":  result.type,
            "emoji": result.emoji,
            "score": result.score,
        }
        metrics[tf] = {
            "btc_chg":    round(m.btc_chg,    2),
            "btcd_chg":   round(m.btcd_chg,   2),
            "total2_chg": round(m.total2_chg,  2),
            "total3_chg": round(m.total3_chg,  2),
            "ethbtc_chg": round(m.ethbtc_chg,  2),
            "btcd_level": round(m.btcd_level,   2),
        }
        scores = score_coins(tf, _state)
        top_movers[tf] = {
            "strong": [_coin_dict(c) for c in get_top_strong(scores)],
            "weak":   [_coin_dict(c) for c in get_top_weak(scores)],
        }

    return {
        "prices": {
            "BTCUSDT": prices.get("BTCUSDT"),
            "ETHUSDT": prices.get("ETHUSDT"),
            "ETHBTC":  prices.get("ETHBTC"),
        },
        "global": {
            "btcd":     round(glb.get("btcd",    0), 2),
            "total":    glb.get("total",  0),
            "total2":   glb.get("total2", 0),
            "total3":   glb.get("total3", 0),
            "others_d": round(glb.get("others_d", 0), 2),
        },
        "states":     states,
        "metrics":    metrics,
        "top_movers": top_movers,
        "timestamp":  time.time(),
    }


@router.get("/api/history/{tf}")
async def history(tf: str, limit: int = 50):
    if tf not in TIMEFRAMES:
        raise HTTPException(400, f"Invalid tf. Use: {list(TIMEFRAMES.keys())}")
    rows = await database.get_state_history(tf, limit)
    return {"tf": tf, "history": _serialize(rows)}


@router.get("/api/heatmap/{tf}")
async def heatmap(tf: str):
    if tf not in TIMEFRAMES:
        raise HTTPException(400, f"Invalid tf. Use: {list(TIMEFRAMES.keys())}")
    rows = await database.get_heatmap_data(tf)
    return {"tf": tf, "data": _serialize(rows)}


@router.get("/api/latest-states")
async def latest_states():
    rows = await database.get_latest_states()
    result = {}
    for tf, row in rows.items():
        if row:
            result[tf] = {
                "label":       row["state_label"],
                "type":        row["state_type"],
                "recorded_at": row["recorded_at"].isoformat(),
                "btc_price":   row.get("btc_price",  0) or 0,
                "total2_val":  row.get("total2_val", 0) or 0,
                "eth_price":   row.get("eth_price",  0) or 0,
            }
        else:
            result[tf] = None
    return result


class PushSub(BaseModel):
    endpoint: str
    keys: dict

class PushUnsub(BaseModel):
    endpoint: str

@router.post("/api/push/subscribe")
async def push_subscribe(sub: PushSub):
    await database.add_push_subscription(
        sub.endpoint,
        sub.keys.get("p256dh", ""),
        sub.keys.get("auth",   ""),
    )
    return {"status": "subscribed"}

@router.post("/api/push/unsubscribe")
async def push_unsubscribe(body: PushUnsub):
    await database.remove_push_subscription(body.endpoint)
    return {"status": "unsubscribed"}

@router.get("/api/push/vapid-public-key")
async def vapid_public_key():
    import os
    key = os.getenv("VAPID_PUBLIC_KEY", "")
    if not key:
        raise HTTPException(500, "VAPID_PUBLIC_KEY not set")
    return {"publicKey": key}


def _coin_dict(c) -> dict:
    return {
        "symbol":        c.symbol,
        "rank":          c.rank,
        "altbtc_chg":    round(c.altbtc_chg, 2),
        "vs_total2":     round(c.vs_total2,  2),
        "score":         round(c.score,      2),
        "hidden_signal": c.hidden_signal,
    }

def _serialize(rows: list[dict]) -> list[dict]:
    result = []
    for r in rows:
        row = dict(r)
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        result.append(row)
    return result
# ============================================================
# backend/api/routes.py — REST endpoints
# ============================================================

import time
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import database
from engine.signals import (
    build_metrics, get_market_state, score_coins,
    get_top_strong, get_top_weak, build_confirmation_data,
)
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

        result = get_market_state(m, tf, _state)
        states[tf] = {
            "label":         result.label,
            "type":          result.type,
            "emoji":         result.emoji,
            "score":         result.score,
            "hits":          result.hits,
            "total":         result.total,
            "confidence":    result.confidence,
            "primary_hits":  result.primary_hits,
            "primary_total": result.primary_total,
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
            "stable_d": round(glb.get("stable_d", 0), 2),
        },
        "states":     states,
        "metrics":    metrics,
        "top_movers": top_movers,
        "timestamp":  time.time(),
    }


@router.get("/api/confirmations")
async def confirmations():
    prices = _state.get("prices", {})
    glb    = _state.get("global", {})

    if not prices or not glb:
        return JSONResponse({"error": "Data not ready"}, status_code=503)

    c        = build_confirmation_data(_state)
    fg       = _state.get("fear_greed", {})
    vol      = _state.get("volume", {})
    fund     = _state.get("funding", {})
    vol_avg  = _state.get("volume_avg", {})
    stable_d = glb.get("stable_d", 0)

    all_signal_scores = {}
    for tf in TIMEFRAMES:
        m = build_metrics(tf, _state)
        if m is None:
            continue
        result = get_market_state(m, tf, _state)
        all_signal_scores[tf] = [
            {
                "id":           s.label.lower().replace(" ", "_"),
                "name":         s.label,
                "hits":         s.hits,
                "total":        s.total,
                "score":        s.score,
                "confidence":   s.confidence,
                "primary_hits": s.primary_hits,
                "active":       s.active,
            }
            for s in result.all_scores
        ]

    return {
        "timestamp": time.time(),
        "raw_data": {
            "btc_volume_24h":     vol.get("btc_24h",   0),
            "btc_volume_30d_avg": vol_avg.get("btc_24h", None),
            "alt_volume_24h":     vol.get("alt_24h",   0),
            "alt_volume_30d_avg": vol_avg.get("alt_24h", None),
            "total_volume_24h":   vol.get("total_24h", 0),
            "funding_rate":       fund.get("rate"),
            "fear_greed_value":   fg.get("value"),
            "fear_greed_label":   fg.get("label", "Unknown"),
            "stable_d":           round(stable_d, 2),
            "stable_d_1h_change": round(c.stable_d_change, 3) if c.stable_d_change is not None else None,
            "usdt_d":             round(glb.get("usdt_d", 0), 2),
            "usdc_d":             round(glb.get("usdc_d", 0), 2),
        },
        "stale_flags": {
            "volume":     c.volume_stale,
            "funding":    c.funding_stale,
            "fear_greed": c.fear_greed_stale,
        },
        "evaluated": {
            "volume":     _eval_volume_label(c),
            "funding":    _eval_funding_label(c.funding_rate),
            "fear_greed": _eval_fg_label(c.fear_greed_value),
            "stable_d":   _eval_stable_label(c.stable_d_change),
        },
        "all_scores": all_signal_scores,
    }


@router.get("/api/history/{tf}")
async def history(tf: str, limit: int = 50):
    if tf not in TIMEFRAMES:
        raise HTTPException(400, f"Invalid tf. Use: {list(TIMEFRAMES.keys())}")
    rows = await database.get_state_history(tf, limit)
    return {"tf": tf, "history": _serialize(rows)}


@router.get("/api/heatmap/{tf}")
async def heatmap(tf: str, interval: str = None):
    if tf not in TIMEFRAMES:
        raise HTTPException(400, f"Invalid tf. Use: {list(TIMEFRAMES.keys())}")
    rows = await database.get_heatmap_data(tf, interval=interval)
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


# ----------------------------------------------------------
# Web Push
# ----------------------------------------------------------
class PushSub(BaseModel):
    endpoint: str
    keys: dict

class PushUnsub(BaseModel):
    endpoint: str

@router.post("/api/push/subscribe")
async def push_subscribe(sub: PushSub):
    await database.add_push_subscription(
        sub.endpoint, sub.keys.get("p256dh",""), sub.keys.get("auth",""),
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


# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------
def _eval_volume_label(c) -> str:
    if c.btc_volume_ratio is None:
        return "unknown"
    if c.btc_volume_ratio >= 1.0:
        return "above_avg"
    if c.btc_volume_ratio < 0.85:
        return "below_avg"
    return "neutral"

def _eval_funding_label(rate) -> str:
    if rate is None:
        return "unknown"
    from config import FUNDING_DEEPLY_NEGATIVE, FUNDING_NEUTRAL_MIN, FUNDING_NEUTRAL_MAX, FUNDING_HIGH_POSITIVE
    if rate < FUNDING_DEEPLY_NEGATIVE:   return "deeply_negative"
    if rate < FUNDING_NEUTRAL_MIN:       return "negative"
    if rate <= FUNDING_NEUTRAL_MAX:      return "neutral"
    if rate > FUNDING_HIGH_POSITIVE:     return "high_positive"
    return "positive"

def _eval_fg_label(val) -> str:
    if val is None: return "unknown"
    if val < 20:    return "extreme_fear"
    if val < 40:    return "fear"
    if val < 60:    return "neutral"
    if val < 75:    return "greed"
    return "extreme_greed"

def _eval_stable_label(change) -> str:
    if change is None: return "unknown"
    from config import STABLE_D_SHARPLY_RISING, STABLE_D_RISING, STABLE_D_FALLING
    if change > STABLE_D_SHARPLY_RISING: return "sharply_rising"
    if change > STABLE_D_RISING:         return "rising"
    if change < STABLE_D_FALLING:        return "falling"
    return "neutral"

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
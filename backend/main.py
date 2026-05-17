# ============================================================
# backend/main.py — Orchestrator
# ============================================================

import asyncio
import logging
import os

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

import database
from config import TIMEFRAMES
from feeds.binance   import BinanceFeed
from feeds.coingecko import CoinGeckoFeed
from engine.signals  import build_metrics, get_market_state, score_coins
from api.routes      import router, set_state
from api.websocket   import manager, broadcast_state_change, send_web_push

# ----------------------------------------------------------
# Logging
# ----------------------------------------------------------
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("main")

# ----------------------------------------------------------
# FastAPI app
# ----------------------------------------------------------
app = FastAPI(title="Crypto Market Dashboard", version="2.0.0")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    from api.routes import snapshot
    await manager.connect(ws)
    try:
        while True:
            try:
                snap = await snapshot()
                if isinstance(snap, dict) and "error" not in snap:
                    import json
                    await ws.send_text(json.dumps({"type": "snapshot", **snap}))
            except WebSocketDisconnect:
                break
            except Exception:
                break
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)

# Serve React frontend from /frontend/dist
_frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(_frontend_path):
    app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend")
    logger.info(f"[App] Serving frontend from {_frontend_path}")

# ----------------------------------------------------------
# Shared state
# ----------------------------------------------------------
state: dict = {
    "prices": {},
    "global": {},
    "top100": [],
}

prev_states: dict[str, str] = {tf: "" for tf in TIMEFRAMES}

# ----------------------------------------------------------
# Engine loop — checks market state every 60s
# ----------------------------------------------------------
async def engine_loop():
    logger.info("[Engine] Waiting for initial data...")
    for _ in range(60):
        if state["prices"] and state["global"] and state["top100"]:
            if len(state["prices"]) > 10:
                break
        await asyncio.sleep(5)

    logger.info(f"[Engine] Data ready — prices: {len(state['prices'])}, top100: {len(state['top100'])}")

    while True:
        try:
            await _check_states()
        except Exception as e:
            logger.error(f"[Engine] {e}")
        await asyncio.sleep(60)


async def _check_states():
    for tf in TIMEFRAMES:
        m = build_metrics(tf, state)
        if m is None:
            continue

        result = get_market_state(m, tf)
        prev   = prev_states.get(tf, "")

        logger.info(
            f"[Engine] {tf}: {result.emoji} {result.label} (score={result.score:.3f}) | "
            f"BTC:{m.btc_chg:.2f}% BTC.D:{m.btcd_chg:.2f}% T2:{m.total2_chg:.2f}%"
        )

        if result.label != prev and prev != "":
            logger.info(f"[Engine] {tf}: {prev} → {result.label}")

            # 1. Save to database
            await database.record_state(
                tf, result.label, result.type, m, result.score
            )

            # 2. Broadcast via WebSocket
            await broadcast_state_change(
                tf, result.label, result.type, result.score, m
            )

            # 3. Web Push notification
            await send_web_push(result.label, tf, result.type)

        elif prev == "":
            # First run — only record if different from last saved state
            last = await database.get_latest_state(tf)
            if not last or last["state_label"] != result.label:
                await database.record_state(
                    tf, result.label, result.type, m, result.score
                )
        await database.record_heatmap_state(tf, result.label, result.type)
        prev_states[tf] = result.label


# ----------------------------------------------------------
# Entry point
# ----------------------------------------------------------
async def main():
    logger.info("=" * 52)
    logger.info("  Crypto Market Dashboard — Starting")
    logger.info("=" * 52)

    await database.init_db()
    set_state(state)

    port   = int(os.getenv("PORT", 8081))
    config = uvicorn.Config(
        app       = app,
        host      = "0.0.0.0",
        port      = port,
        loop      = "none",
        log_level = "warning",
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        server.serve(),
        CoinGeckoFeed(state).run(),
        BinanceFeed(state).run(),
        engine_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())

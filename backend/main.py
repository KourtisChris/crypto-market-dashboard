# ============================================================
# backend/main.py — Orchestrator
# ============================================================

import asyncio
import logging
import os
import aiohttp

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

import database
from config import TIMEFRAMES
from feeds.binance   import BinanceFeed
from feeds.coingecko import CoinGeckoFeed
from engine.signals  import build_metrics, get_market_state, score_coins, get_top_strong, get_top_weak
from api.routes      import router, set_state
from api.websocket   import manager, broadcast_state_change, send_web_push

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("main")

# Telegram config
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_ALERTS_TOKEN", "")
TELEGRAM_BOT_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
DASHBOARD_URL    = "https://crypto-dashboard-frontend-fo5q.onrender.com"
ALERT_GUIDE_URL  = "https://example.com/alert-guide.pdf"  # replace with real PDF link

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

_frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(_frontend_path):
    app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend")
    logger.info(f"[App] Serving frontend from {_frontend_path}")

state: dict = {
    "prices": {},
    "global": {},
    "top100": [],
}

prev_states: dict[str, str] = {tf: "" for tf in TIMEFRAMES}


# ----------------------------------------------------------
# Telegram — format & send alert
# ----------------------------------------------------------
def _format_alert(state_label: str, state_type: str, tf: str,
                  strong_coins: list, weak_coins: list) -> str:

    emoji_map = {
        "long":     "🟢",
        "short":    "🔴",
        "caution":  "🟡",
        "risk_off": "⚫",
        "neutral":  "⚪",
    }
    emoji = emoji_map.get(state_type, "📊")

    TF_LABELS = {"1M": "1 Minute", "1H": "1 Hour", "1D": "1 Day", "1W": "1 Week"}
    tf_label = TF_LABELS.get(tf, tf)

    label = state_label

    lines = [
        f"{emoji} <b>{label}</b>",
        f"",
        f"Timeframe: {tf_label}",
    ]

    # Add top coins for alt signals
    label_lower = label.lower()
    if any(x in label_lower for x in ["alts long", "eth leading", "late alts", "rotation"]):
        if strong_coins:
            lines.append("")
            lines.append("📈 <b>Top 3 strongest alts:</b>")
            for i, c in enumerate(strong_coins[:3], 1):
                sym = c.symbol  # e.g. ENAUSDT
                lines.append(f"{i}. <code>{sym}</code>")

    elif "alts short" in label_lower:
        if weak_coins:
            lines.append("")
            lines.append("📉 <b>Top 3 weakest alts:</b>")
            for i, c in enumerate(weak_coins[:3], 1):
                sym = c.symbol
                lines.append(f"{i}. <code>{sym}</code>")

    lines += [
        f"",
        f'For more details visit <a href="{DASHBOARD_URL}">Market State Dashboard</a>',
        f"",
        f"<i>Alerts are sent automatically when market state changes. No action needed — just wait!</i>",
        f'<a href="{ALERT_GUIDE_URL}">Alert Guide</a>: How to Read &amp; Act on Alerts',
    ]

    return "\n".join(lines)


async def _send_telegram_alert(text: str):
    """Sends alert to all Telegram subscribers."""
    if not TELEGRAM_TOKEN:
        logger.warning("[Telegram] No TELEGRAM_ALERTS_TOKEN set")
        return

    subscribers = await database.get_telegram_subscribers()
    if not subscribers:
        logger.info("[Telegram] No subscribers")
        return

    url = f"{TELEGRAM_BOT_URL}/sendMessage"
    dead = []

    async with aiohttp.ClientSession() as session:
        for chat_id in subscribers:
            try:
                async with session.post(url, json={
                    "chat_id":                  chat_id,
                    "text":                     text,
                    "parse_mode":               "HTML",
                    "disable_web_page_preview": True,
                }) as resp:
                    if resp.status in (400, 403):
                        dead.append(chat_id)
                    elif resp.status == 200:
                        logger.info(f"[Telegram] Alert sent to {chat_id}")
            except Exception as e:
                logger.error(f"[Telegram] Error sending to {chat_id}: {e}")

    for chat_id in dead:
        await database.remove_telegram_subscriber(chat_id)


# ----------------------------------------------------------
# Telegram — bot command polling (/start, /stop)
# ----------------------------------------------------------
async def telegram_poll():
    """Polls Telegram for new /start and /stop commands."""
    if not TELEGRAM_TOKEN:
        logger.warning("[Telegram] No TELEGRAM_ALERTS_TOKEN — bot polling disabled")
        return

    offset = None
    logger.info("[Telegram] Bot polling started")

    while True:
        try:
            url    = f"{TELEGRAM_BOT_URL}/getUpdates"
            params = {"timeout": 0, "allowed_updates": ["message"]}
            if offset is not None:
                params["offset"] = offset

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(5)
                        continue
                    data = await resp.json()

            for update in data.get("result", []):
                offset  = update["update_id"] + 1
                msg     = update.get("message", {})
                text    = msg.get("text", "").strip()
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if not chat_id:
                    continue

                if text == "/start":
                    await database.add_telegram_subscriber(chat_id)
                    await _send_welcome(chat_id)
                    logger.info(f"[Telegram] /start from {chat_id}")

                elif text == "/stop":
                    await database.remove_telegram_subscriber(chat_id)
                    await _send_message(chat_id,
                        "📴 <b>Unsubscribed</b>\n\nYou will no longer receive alerts.\nSend /start to resubscribe."
                    )
                    logger.info(f"[Telegram] /stop from {chat_id}")

        except Exception as e:
            logger.error(f"[Telegram] Poll error: {e}")

        await asyncio.sleep(2)


async def _send_welcome(chat_id: str):
    text = (
        "👋 <b>Welcome to Market State Alerts!</b>\n\n"
        "You will now receive alerts whenever the crypto market state changes.\n\n"
        "<b>States tracked:</b>\n"
        "🟢 Alts Long\n · 🔴 Alts Short\n · 🟠 BTC Long\n"
        "🔵 ETH Leading\n · 🟡 Late Alts\n · ⚫ Risk Off\n · ⚪ Neutral\n\n"
        f'📊 <a href="{DASHBOARD_URL}">Open Dashboard</a>\n'
        f'📖 <a href="{ALERT_GUIDE_URL}">Alert Guide</a>\n\n'
        "<i>Send /stop to unsubscribe.</i>"
    )
    await _send_message(chat_id, text)


async def _send_message(chat_id: str, text: str):
    if not TELEGRAM_TOKEN:
        return
    url = f"{TELEGRAM_BOT_URL}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={
            "chat_id":                  chat_id,
            "text":                     text,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
        })


# ----------------------------------------------------------
# Engine loop
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
    prices = state.get("prices", {})
    glb    = state.get("global", {})

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

        btc_price  = prices.get("BTCUSDT", 0) or 0
        eth_price  = prices.get("ETHUSDT", 0) or 0
        total2_val = glb.get("total2", 0) or 0

        if result.label != prev and prev != "":
            logger.info(f"[Engine] {tf}: {prev} → {result.label}")

            await database.record_state(
                tf, result.label, result.type, m, result.score,
                btc_price=btc_price,
                total2_val=total2_val,
                eth_price=eth_price,
            )
            await broadcast_state_change(
                tf, result.label, result.type, result.score, m
            )
            await send_web_push(result.label, tf, result.type)

            # Score coins for alt signals
            scores       = score_coins(tf, state)
            strong_coins = get_top_strong(scores, 3)
            weak_coins   = get_top_weak(scores, 3)

            # Send Telegram alert
            alert_text = _format_alert(
                result.label, result.type, tf,
                strong_coins, weak_coins
            )
            await _send_telegram_alert(alert_text)

        elif prev == "":
            last = await database.get_latest_state(tf)
            if not last or last["state_label"] != result.label:
                await database.record_state(
                    tf, result.label, result.type, m, result.score,
                    btc_price=btc_price,
                    total2_val=total2_val,
                    eth_price=eth_price,
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
        telegram_poll(),
    )


if __name__ == "__main__":
    asyncio.run(main())
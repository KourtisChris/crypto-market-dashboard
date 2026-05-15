# ============================================================
# backend/api/websocket.py
# WebSocket connection manager + Web Push notifications
# ============================================================

import asyncio
import json
import logging
import os
from fastapi import WebSocket, WebSocketDisconnect

import database

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)
        logger.info(f"[WS] Client connected. Total: {len(self._clients)}")

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)
        logger.info(f"[WS] Client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, data: dict):
        if not self._clients:
            return
        msg  = json.dumps(data)
        dead = []
        for ws in self._clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# Singleton
manager = WSManager()


async def broadcast_state_change(tf: str, label: str, type_: str,
                                  score: float, metrics):
    """Called by engine when state changes — pushes to all WS clients."""
    await manager.broadcast({
        "type":        "state_change",
        "tf":          tf,
        "state_label": label,
        "state_type":  type_,
        "score":       score,
        "metrics": {
            "btc_chg":    round(metrics.btc_chg,    2),
            "btcd_chg":   round(metrics.btcd_chg,   2),
            "total2_chg": round(metrics.total2_chg, 2),
            "btcd_level": round(metrics.btcd_level,  2),
        },
    })


async def send_web_push(label: str, tf: str, type_: str):
    """Sends Web Push notification to all subscribed browsers."""
    try:
        from pywebpush import webpush, WebPushException

        private_key = os.getenv("VAPID_PRIVATE_KEY", "")
        email       = os.getenv("VAPID_EMAIL", "mailto:admin@example.com")

        if not private_key:
            logger.warning("[Push] VAPID_PRIVATE_KEY not set — skipping")
            return

        subscriptions = await database.get_push_subscriptions()
        if not subscriptions:
            return

        icon_map = {
            "long":     "🟢",
            "short":    "🔴",
            "caution":  "🟡",
            "risk_off": "⚫",
            "neutral":  "⚪",
        }
        icon    = icon_map.get(type_, "📊")
        payload = json.dumps({
            "title": f"{icon} {label} — {tf}",
            "body":  f"Market state changed to {label}",
            "tf":    tf,
            "type":  type_,
        })

        dead = []
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                    },
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims={"sub": email},
                )
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    dead.append(sub["endpoint"])
            except Exception as e:
                logger.error(f"[Push] {e}")

        for ep in dead:
            await database.remove_push_subscription(ep)

        logger.info(f"[Push] Sent to {len(subscriptions) - len(dead)} subscribers")

    except ImportError:
        logger.warning("[Push] pywebpush not installed")

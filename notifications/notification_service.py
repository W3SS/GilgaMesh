"""
PROMETHEUS NOTIFICATION SERVICE
Gerencia envio de alertas para Discord, Telegram e Webhooks via fila.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic_settings import BaseSettings

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

class NotificationConfig(BaseSettings):
    DISCORD_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"

config = NotificationConfig()

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NotificationService")

# ============================================================================
# MODELS
# ============================================================================

class Channel(str, Enum):
    DISCORD = "discord"
    TELEGRAM = "telegram"
    LOG = "log"

class NotificationRequest(BaseModel):
    channel: Channel
    title: str
    message: str
    metadata: Dict[str, Any] = {}
    priority: str = "normal"  # low, normal, high, critical

# ============================================================================
# SERVICE CORE
# ============================================================================

class NotificationManager:
    async def send(self, notification: NotificationRequest):
        """Roteia notificação para o canal correto"""
        try:
            if notification.channel == Channel.LOG:
                self._send_log(notification)
            elif notification.channel == Channel.DISCORD:
                await self._send_discord(notification)
            elif notification.channel == Channel.TELEGRAM:
                await self._send_telegram(notification)
            
            logger.info(f"Notification sent: {notification.title} -> {notification.channel}")
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            raise

    def _send_log(self, n: NotificationRequest):
        """Fallback: apenas loga"""
        log_method = logger.error if n.priority == "critical" else logger.info
        log_method(f"[{n.priority.upper()}] {n.title}: {n.message}")

    async def _send_discord(self, n: NotificationRequest):
        """Envia para Discord Webhook"""
        if not config.DISCORD_WEBHOOK_URL:
            logger.warning("Discord webhook not configured")
            return self._send_log(n)
        
        # TODO: Implementar httpx post para Discord
        logger.info(f"Stub: Sending to Discord: {n.title}")

    async def _send_telegram(self, n: NotificationRequest):
        """Envia para Telegram Bot"""
        if not config.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram token not configured")
            return self._send_log(n)
            
        # TODO: Implementar httpx post para Telegram
        logger.info(f"Stub: Sending to Telegram: {n.title}")

# ============================================================================
# API
# ============================================================================

app = FastAPI(title="Prometheus Notification Service")
manager = NotificationManager()

@app.post("/notify")
async def send_notification(notification: NotificationRequest, background_tasks: BackgroundTasks):
    """Enfileira envio de notificação"""
    background_tasks.add_task(manager.send, notification)
    return {"status": "queued"}

@app.get("/health")
async def health():
    return {"status": "ok"}

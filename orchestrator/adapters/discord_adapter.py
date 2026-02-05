"""
Discord Notification Adapter - Implements NotificationPort for Discord
"""

import httpx
import logging
from typing import Literal

from ports.notification import NotificationPort, Priority, Channel


logger = logging.getLogger(__name__)


class DiscordAdapter:
    """Discord notification adapter using webhooks"""
    
    def __init__(self, webhook_url: str, http_client: httpx.AsyncClient):
        self.webhook_url = webhook_url
        self.http_client = http_client
        
    async def send(
        self,
        title: str,
        message: str,
        priority: Priority = "normal",
        channel: Channel = "discord"
    ) -> bool:
        """Send notification via Discord webhook"""
        try:
            # Map priority to color
            color_map = {
                "low": 0x808080,  # Gray
                "normal": 0x3498db,  # Blue
                "high": 0xf39c12,  # Orange
                "critical": 0xe74c3c  # Red
            }
            
            payload = {
                "embeds": [{
                    "title": title,
                    "description": message,
                    "color": color_map.get(priority, 0x3498db)
                }]
            }
            
            response = await self.http_client.post(
                self.webhook_url,
                json=payload,
                timeout=5.0
            )
            
            if response.status_code == 204:
                logger.debug(f"Discord notification sent: {title}")
                return True
            else:
                logger.warning(f"Discord returned {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False


class NullNotificationAdapter:
    """Null object pattern - does nothing (for testing/dev)"""
    
    async def send(
        self,
        title: str,
        message: str,
        priority: Priority = "normal",
        channel: Channel = "discord"
    ) -> bool:
        logger.info(f"[NULL NOTIF] {title}: {message}")
        return True

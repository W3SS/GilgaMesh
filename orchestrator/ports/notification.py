"""
Notification Port - Interface for sending notifications to external channels
"""

from typing import Protocol, Literal


Priority = Literal["low", "normal", "high", "critical"]
Channel = Literal["discord", "telegram", "email"]


class NotificationPort(Protocol):
    """Protocol for notification services"""
    
    async def send(
        self,
        title: str,
        message: str,
        priority: Priority = "normal",
        channel: Channel = "discord"
    ) -> bool:
        """
        Send a notification to the specified channel
        
        Args:
            title: Notification title
            message: Notification body
            priority: Message priority level
            channel: Target channel
            
        Returns:
            True if sent successfully, False otherwise
        """
        ...

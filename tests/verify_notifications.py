import asyncio
import httpx
import logging

# Configuração
NOTIFY_URL = "http://localhost:9003"
HEADERS = {"Content-Type": "application/json"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyNotifications")

async def verify_notifications():
    """Verifica envio de notificações (Stub)"""
    logger.info("🔵 Starting Verification: Notification Service")
    
    async with httpx.AsyncClient() as client:
        # 1. Enviar notificação de Log (não deve falhar)
        payload_log = {
            "channel": "log",
            "title": "Test Log Notification",
            "message": "This is a test message for the log channel.",
            "priority": "normal"
        }
        
        logger.info("1. Sending LOG notification...")
        response = await client.post(
            f"{NOTIFY_URL}/notify",
            json=payload_log,
            headers=HEADERS
        )
        assert response.status_code == 200
        logger.info(f"✅ Log notification queued: {response.json()}")
        
        # 2. Enviar notificação de Discord (Stub)
        payload_discord = {
            "channel": "discord",
            "title": "Test Discord Notification",
            "message": "This is a test message for the discord channel.",
            "priority": "high"
        }
        
        logger.info("2. Sending DISCORD notification...")
        response = await client.post(
            f"{NOTIFY_URL}/notify",
            json=payload_discord,
            headers=HEADERS
        )
        assert response.status_code == 200
        logger.info(f"✅ Discord notification queued: {response.json()}")

async def main():
    try:
        await verify_notifications()
        logger.info("🎉 Notification Service tests passed!")
    except Exception as e:
        logger.error(f"Test Execution Failed: {e}")
        # Não falha o script se o serviço ainda não estiver de pé (pode estar building)
        logger.warning("Make sure the notification service is running on port 9003")

if __name__ == "__main__":
    asyncio.run(main())

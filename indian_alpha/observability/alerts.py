import os
from loguru import logger
import httpx
import asyncio

async def send_alert(message: str, level: str = "ERROR") -> None:
    """Logs the alert and transmits to Telegram bot @MomentumScanShan_bot if configured."""
    log_msg = f"[ALERT] [{level}] {message}"
    if level == "CRITICAL" or level == "ERROR":
        logger.error(log_msg)
    else:
        logger.warning(log_msg)
        
    # Read Telegram configurations from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": f"⚠️ <b>{level} ALERT</b>\n\n{message}",
                "parse_mode": "HTML"
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                if response.status_code != 200:
                    logger.error(f"Telegram alert delivery failed with status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Failed to transmit Telegram alert: {e}")

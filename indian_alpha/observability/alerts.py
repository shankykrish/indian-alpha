from loguru import logger
import httpx
import asyncio

async def send_alert(message: str, level: str = "ERROR") -> None:
    """Logs the alert and can optionally trigger a Slack or Discord Webhook if configured."""
    log_msg = f"[ALERT] [{level}] {message}"
    if level == "CRITICAL" or level == "ERROR":
        logger.error(log_msg)
    else:
        logger.warning(log_msg)
        
    # Hook for future integration (e.g. Discord/Slack webhook)
    # webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    # if webhook_url:
    #     try:
    #         async with httpx.AsyncClient() as client:
    #             await client.post(webhook_url, json={"content": log_msg})
    #     except Exception as e:
    #         logger.error(f"Failed to transmit webhook alert: {e}")

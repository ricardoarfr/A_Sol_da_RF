import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

ZAPI_BASE = f"https://api.z-api.io/instances/{settings.ZAPI_INSTANCE_ID}/token/{settings.ZAPI_TOKEN}"


async def send_text_message(phone: str, message: str) -> dict:
    """Send a text message via Z-API."""
    url = f"{ZAPI_BASE}/send-text"
    headers = {"Client-Token": settings.ZAPI_CLIENT_TOKEN}
    payload = {"phone": phone, "message": message}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Message sent to {phone}: status {response.status_code}")
        return response.json()

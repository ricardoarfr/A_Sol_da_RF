import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def send_text_message(phone: str, message: str) -> dict:
    """Send a text message via whatsapp-service (Baileys)."""
    url = f"{settings.WHATSAPP_SERVICE_URL}/send"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json={"phone": phone, "message": message})
        response.raise_for_status()
        logger.info(f"Message sent to {phone}: status {response.status_code}")
        return response.json()

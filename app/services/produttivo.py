import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def _get_headers() -> dict:
    return {
        "Cookie": f"_produttivo_session={settings.PRODUTTIVO_SESSION_COOKIE}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def get_activities(filters: dict = None) -> list:
    """Fetch activities from Produttivo API."""
    url = f"{settings.PRODUTTIVO_BASE_URL}/api/v1/accounts/{settings.PRODUTTIVO_ACCOUNT_ID}/activities"
    params = filters or {}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_get_headers(), params=params)
        response.raise_for_status()
        return response.json()


async def get_technicians() -> list:
    """Fetch technicians (field agents) from Produttivo API."""
    url = f"{settings.PRODUTTIVO_BASE_URL}/api/v1/accounts/{settings.PRODUTTIVO_ACCOUNT_ID}/users"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_get_headers())
        response.raise_for_status()
        return response.json()

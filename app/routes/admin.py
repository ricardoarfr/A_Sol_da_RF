import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from app.config import settings
from app.services import ai_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)


def _require_admin(token: str = Depends(_api_key_header)) -> None:
    if not token or token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


class AIConfigPayload(BaseModel):
    provider: str
    model: str
    api_key: str


@router.get("/ai-config", dependencies=[Depends(_require_admin)])
async def get_ai_config() -> dict:
    config = ai_config.read_config()
    return {**config, "api_key": "***" if config.get("api_key") else ""}


@router.post("/ai-config", dependencies=[Depends(_require_admin)])
async def save_ai_config(payload: AIConfigPayload) -> dict:
    ai_config.write_config(payload.model_dump())
    return {"status": "ok"}

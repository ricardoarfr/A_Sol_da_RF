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


class AIModelPayload(BaseModel):
    name: str
    provider: str
    model: str
    api_key: str


class AIModelUpdatePayload(BaseModel):
    name: str
    provider: str
    model: str
    api_key: str = ""


@router.get("/ai-models", dependencies=[Depends(_require_admin)])
async def list_models() -> dict:
    return {"models": ai_config.list_models(), "active_id": ai_config._load().get("active_id")}


@router.post("/ai-models", dependencies=[Depends(_require_admin)])
async def add_model(payload: AIModelPayload) -> dict:
    try:
        model = ai_config.add_model(payload.name, payload.provider, payload.model, payload.api_key)
        return model
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/ai-models/{model_id}", dependencies=[Depends(_require_admin)])
async def update_model(model_id: str, payload: AIModelUpdatePayload) -> dict:
    try:
        model = ai_config.update_model(model_id, payload.name, payload.provider, payload.model, payload.api_key or None)
        return model
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/ai-models/{model_id}", dependencies=[Depends(_require_admin)])
async def delete_model(model_id: str) -> dict:
    ai_config.delete_model(model_id)
    return {"status": "ok"}


@router.put("/ai-models/{model_id}/activate", dependencies=[Depends(_require_admin)])
async def activate_model(model_id: str) -> dict:
    try:
        ai_config.activate_model(model_id)
        return {"status": "ok", "active_id": model_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from app.config import settings
from app.services import ai_config, phone_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)


def _require_admin(token: str = Depends(_api_key_header)) -> None:
    if not token or token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# --- AI Models ---

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
        return ai_config.add_model(payload.name, payload.provider, payload.model, payload.api_key)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/ai-models/{model_id}", dependencies=[Depends(_require_admin)])
async def update_model(model_id: str, payload: AIModelUpdatePayload) -> dict:
    try:
        return ai_config.update_model(model_id, payload.name, payload.provider, payload.model, payload.api_key or None)
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


# --- Authorized Phones ---

class PhonePayload(BaseModel):
    phone: str
    name: str = ""


@router.get("/phones", dependencies=[Depends(_require_admin)])
async def list_phones() -> dict:
    return {"phones": phone_auth.list_phones()}


@router.post("/phones", dependencies=[Depends(_require_admin)])
async def add_phone(payload: PhonePayload) -> dict:
    try:
        return phone_auth.add_phone(payload.phone, payload.name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/phones/{phone_id}", dependencies=[Depends(_require_admin)])
async def update_phone(phone_id: str, payload: PhonePayload) -> dict:
    try:
        return phone_auth.update_phone(phone_id, payload.phone, payload.name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/phones/{phone_id}", dependencies=[Depends(_require_admin)])
async def delete_phone(phone_id: str) -> dict:
    phone_auth.delete_phone(phone_id)
    return {"status": "ok"}

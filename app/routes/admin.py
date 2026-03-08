import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from app.config import settings
from app.services import ai_config, phone_auth, ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)


def _require_admin(token: str = Depends(_api_key_header)) -> None:
    if not token or token != settings.ADMIN_TOKEN:
        logger.warning("[admin] acesso negado — token ausente ou inválido (recebido: %r)", token[:6] + "…" if token else "vazio")
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
        await ai.validate_key(payload.provider, payload.model, payload.api_key)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
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


# --- WhatsApp (proxy para whatsapp-service) ---

@router.get("/whatsapp/status", dependencies=[Depends(_require_admin)])
async def whatsapp_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(f"{settings.WHATSAPP_SERVICE_URL}/status")
            return res.json()
    except Exception:
        return {"status": "disconnected"}


@router.post("/whatsapp/start", dependencies=[Depends(_require_admin)])
async def whatsapp_start() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(f"{settings.WHATSAPP_SERVICE_URL}/start")
            return res.json()
    except Exception:
        raise HTTPException(status_code=503, detail="whatsapp-service indisponível")


@router.get("/whatsapp/qr", dependencies=[Depends(_require_admin)])
async def whatsapp_qr() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(f"{settings.WHATSAPP_SERVICE_URL}/qr")
            if res.status_code == 404:
                raise HTTPException(status_code=404, detail="QR não disponível")
            return res.json()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="whatsapp-service indisponível")


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

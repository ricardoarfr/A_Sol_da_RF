import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from app.config import settings
from app.services import ai_config, phone_auth, ai, systems as systems_svc, auth_methods as auth_methods_svc, endpoints_svc, agents_svc, executor, agent_runner, importer

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
    models = await ai_config.list_models()
    active = next((m["id"] for m in models if m.get("is_active")), None)
    return {"models": models, "active_id": active}


@router.post("/ai-models", dependencies=[Depends(_require_admin)])
async def add_model(payload: AIModelPayload) -> dict:
    try:
        await ai.validate_key(payload.provider, payload.model, payload.api_key)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        return await ai_config.add_model(payload.name, payload.provider, payload.model, payload.api_key)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/ai-models/{model_id}", dependencies=[Depends(_require_admin)])
async def update_model(model_id: str, payload: AIModelUpdatePayload) -> dict:
    if payload.api_key:
        try:
            await ai.validate_key(payload.provider, payload.model, payload.api_key)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    try:
        return await ai_config.update_model(model_id, payload.name, payload.provider, payload.model, payload.api_key or None)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/ai-models/{model_id}", dependencies=[Depends(_require_admin)])
async def delete_model(model_id: str) -> dict:
    await ai_config.delete_model(model_id)
    return {"status": "ok"}


@router.put("/ai-models/{model_id}/activate", dependencies=[Depends(_require_admin)])
async def activate_model(model_id: str) -> dict:
    try:
        await ai_config.activate_model(model_id)
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
    return {"phones": await phone_auth.list_phones()}


@router.post("/phones", dependencies=[Depends(_require_admin)])
async def add_phone(payload: PhonePayload) -> dict:
    try:
        return await phone_auth.add_phone(payload.phone, payload.name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/phones/{phone_id}", dependencies=[Depends(_require_admin)])
async def update_phone(phone_id: str, payload: PhonePayload) -> dict:
    try:
        return await phone_auth.update_phone(phone_id, payload.phone, payload.name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/phones/{phone_id}", dependencies=[Depends(_require_admin)])
async def delete_phone(phone_id: str) -> dict:
    await phone_auth.delete_phone(phone_id)
    return {"status": "ok"}


# --- Systems ---

class SystemPayload(BaseModel):
    name: str
    description: str = ""
    base_url: str
    environment: str = "production"
    notes: str = ""


@router.get("/systems", dependencies=[Depends(_require_admin)])
async def list_systems() -> dict:
    return {"systems": await systems_svc.list_systems()}


@router.get("/systems/{system_id}", dependencies=[Depends(_require_admin)])
async def get_system(system_id: str) -> dict:
    system = await systems_svc.get_system(system_id)
    if not system:
        raise HTTPException(status_code=404, detail="Sistema não encontrado.")
    return system


@router.post("/systems", dependencies=[Depends(_require_admin)])
async def create_system(payload: SystemPayload) -> dict:
    return await systems_svc.create_system(
        payload.name, payload.description, payload.base_url,
        payload.environment, payload.notes,
    )


@router.put("/systems/{system_id}", dependencies=[Depends(_require_admin)])
async def update_system(system_id: str, payload: SystemPayload) -> dict:
    try:
        return await systems_svc.update_system(
            system_id, payload.name, payload.description, payload.base_url,
            payload.environment, payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/systems/{system_id}", dependencies=[Depends(_require_admin)])
async def delete_system(system_id: str) -> dict:
    await systems_svc.delete_system(system_id)
    return {"status": "ok"}


# --- Auth Methods ---

class AuthMethodPayload(BaseModel):
    system_id: str | None = None
    name: str
    type: str
    config: str = "{}"
    description: str = ""


@router.get("/auth-methods", dependencies=[Depends(_require_admin)])
async def list_auth_methods(system_id: str | None = None) -> dict:
    return {"auth_methods": await auth_methods_svc.list_auth_methods(system_id)}


@router.get("/auth-methods/{method_id}", dependencies=[Depends(_require_admin)])
async def get_auth_method(method_id: str) -> dict:
    method = await auth_methods_svc.get_auth_method(method_id)
    if not method:
        raise HTTPException(status_code=404, detail="Método de autenticação não encontrado.")
    return method


@router.post("/auth-methods", dependencies=[Depends(_require_admin)])
async def create_auth_method(payload: AuthMethodPayload) -> dict:
    try:
        return await auth_methods_svc.create_auth_method(
            payload.system_id, payload.name, payload.type, payload.config, payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/auth-methods/{method_id}", dependencies=[Depends(_require_admin)])
async def update_auth_method(method_id: str, payload: AuthMethodPayload) -> dict:
    try:
        return await auth_methods_svc.update_auth_method(
            method_id, payload.system_id, payload.name, payload.type, payload.config, payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/auth-methods/{method_id}", dependencies=[Depends(_require_admin)])
async def delete_auth_method(method_id: str) -> dict:
    await auth_methods_svc.delete_auth_method(method_id)
    return {"status": "ok"}


# --- Endpoints ---

class EndpointPayload(BaseModel):
    system_id: str
    auth_method_id: str | None = None
    name: str
    description: str = ""
    method: str = "GET"
    path: str
    headers: str = "{}"
    query_params: str = "{}"
    body_template: str = "{}"
    response_example: str = ""


@router.get("/endpoints", dependencies=[Depends(_require_admin)])
async def list_endpoints(system_id: str | None = None) -> dict:
    return {"endpoints": await endpoints_svc.list_endpoints(system_id)}


@router.get("/endpoints/{endpoint_id}", dependencies=[Depends(_require_admin)])
async def get_endpoint(endpoint_id: str) -> dict:
    ep = await endpoints_svc.get_endpoint(endpoint_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint não encontrado.")
    return ep


@router.post("/endpoints", dependencies=[Depends(_require_admin)])
async def create_endpoint(payload: EndpointPayload) -> dict:
    try:
        return await endpoints_svc.create_endpoint(
            payload.system_id, payload.auth_method_id, payload.name, payload.description,
            payload.method, payload.path, payload.headers, payload.query_params,
            payload.body_template, payload.response_example,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/endpoints/{endpoint_id}", dependencies=[Depends(_require_admin)])
async def update_endpoint(endpoint_id: str, payload: EndpointPayload) -> dict:
    try:
        return await endpoints_svc.update_endpoint(
            endpoint_id, payload.system_id, payload.auth_method_id, payload.name,
            payload.description, payload.method, payload.path, payload.headers,
            payload.query_params, payload.body_template, payload.response_example,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/endpoints/{endpoint_id}", dependencies=[Depends(_require_admin)])
async def delete_endpoint(endpoint_id: str) -> dict:
    await endpoints_svc.delete_endpoint(endpoint_id)
    return {"status": "ok"}


# --- Agents ---

class AgentPayload(BaseModel):
    name: str
    description: str = ""
    type: str = "internal"
    ai_model_id: str | None = None
    system_prompt: str = ""
    is_active: bool = True


class AgentEndpointsPayload(BaseModel):
    endpoint_ids: list[str]


@router.get("/agents", dependencies=[Depends(_require_admin)])
async def list_agents() -> dict:
    return {"agents": await agents_svc.list_agents()}


@router.get("/agents/{agent_id}", dependencies=[Depends(_require_admin)])
async def get_agent(agent_id: str) -> dict:
    agent = await agents_svc.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")
    return agent


@router.post("/agents", dependencies=[Depends(_require_admin)])
async def create_agent(payload: AgentPayload) -> dict:
    try:
        return await agents_svc.create_agent(
            payload.name, payload.description, payload.type,
            payload.ai_model_id, payload.system_prompt, payload.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/agents/{agent_id}", dependencies=[Depends(_require_admin)])
async def update_agent(agent_id: str, payload: AgentPayload) -> dict:
    try:
        return await agents_svc.update_agent(
            agent_id, payload.name, payload.description, payload.type,
            payload.ai_model_id, payload.system_prompt, payload.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/agents/{agent_id}", dependencies=[Depends(_require_admin)])
async def delete_agent(agent_id: str) -> dict:
    await agents_svc.delete_agent(agent_id)
    return {"status": "ok"}


@router.put("/agents/{agent_id}/endpoints", dependencies=[Depends(_require_admin)])
async def set_agent_endpoints(agent_id: str, payload: AgentEndpointsPayload) -> dict:
    return await agents_svc.set_agent_endpoints(agent_id, payload.endpoint_ids)


# --- Executor e Simulador de APIs ---

class ExecutePayload(BaseModel):
    params: dict = {}


class RawRequestPayload(BaseModel):
    method: str = "GET"
    url: str
    headers: dict = {}
    query_params: dict = {}
    body: dict | None = None
    auth_method_id: str | None = None


@router.post("/endpoints/{endpoint_id}/execute", dependencies=[Depends(_require_admin)])
async def execute_endpoint(endpoint_id: str, payload: ExecutePayload) -> dict:
    try:
        return await executor.execute_endpoint(endpoint_id, payload.params)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("[admin] execute_endpoint error: %s", e)
        raise HTTPException(status_code=502, detail=f"Erro ao executar endpoint: {e}")


@router.post("/endpoints/{endpoint_id}/simulate", dependencies=[Depends(_require_admin)])
async def simulate_endpoint(endpoint_id: str, payload: ExecutePayload) -> dict:
    """Dry-run: retorna a requisição resolvida sem executar."""
    try:
        return await executor.simulate_endpoint(endpoint_id, payload.params)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("[admin] simulate_endpoint error: %s", e)
        raise HTTPException(status_code=502, detail=f"Erro ao simular: {e}")


@router.post("/simulate/raw", dependencies=[Depends(_require_admin)])
async def simulate_raw(payload: RawRequestPayload) -> dict:
    """Executa uma requisição HTTP arbitrária (sem precisar salvar no catálogo)."""
    try:
        return await executor.execute_raw(
            payload.method, payload.url, payload.headers,
            payload.query_params, payload.body, payload.auth_method_id,
        )
    except Exception as e:
        logger.error("[admin] simulate_raw error: %s", e)
        raise HTTPException(status_code=502, detail=f"Erro ao executar: {e}")


# --- Motor de Agentes ---

class RunAgentPayload(BaseModel):
    message: str


@router.post("/agents/{agent_id}/run", dependencies=[Depends(_require_admin)])
async def run_agent(agent_id: str, payload: RunAgentPayload) -> dict:
    try:
        response = await agent_runner.run_agent(agent_id, payload.message)
        return {"response": response}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("[admin] run_agent error: %s", e)
        raise HTTPException(status_code=502, detail=f"Erro ao executar agente: {e}")


# --- Import de APIs ---

class ImportPostmanPayload(BaseModel):
    system_id: str
    collection: dict


class ImportOpenAPIPayload(BaseModel):
    system_id: str
    spec: dict


class ImportCurlPayload(BaseModel):
    system_id: str
    name: str = ""
    curl: str


@router.post("/import/postman", dependencies=[Depends(_require_admin)])
async def import_postman(payload: ImportPostmanPayload) -> dict:
    try:
        return await importer.import_postman(payload.system_id, payload.collection)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("[admin] import_postman error: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro ao importar: {e}")


@router.post("/import/openapi", dependencies=[Depends(_require_admin)])
async def import_openapi(payload: ImportOpenAPIPayload) -> dict:
    try:
        return await importer.import_openapi(payload.system_id, payload.spec)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("[admin] import_openapi error: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro ao importar: {e}")


@router.post("/import/curl", dependencies=[Depends(_require_admin)])
async def import_curl(payload: ImportCurlPayload) -> dict:
    try:
        return await importer.import_curl(payload.system_id, payload.name, payload.curl)
    except Exception as e:
        logger.error("[admin] import_curl error: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro ao importar: {e}")


@router.post("/import/curl/preview", dependencies=[Depends(_require_admin)])
async def preview_curl(payload: ImportCurlPayload) -> dict:
    """Parseia o CURL e retorna os campos sem persistir no banco."""
    return importer.parse_curl(payload.curl)

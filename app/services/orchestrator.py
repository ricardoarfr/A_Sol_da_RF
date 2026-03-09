"""
Agente Orquestrador (Etapa 8).

Fluxo:
  1. Carrega todos os agentes ativos do DB
  2. Se não há agentes → resposta de fallback
  3. Se há apenas 1 agente → delega diretamente
  4. Se há vários → usa AI para selecionar o mais adequado
  5. Executa o agente selecionado via agent_runner.run_agent
  6. Retorna o texto final para envio no WhatsApp
"""

import json
import logging
import time
import uuid
from datetime import date

import httpx

from app.services import agent_runner
from app.services.ai_config import get_active_model
from app.services.database import get_pool

logger = logging.getLogger(__name__)

_FALLBACK_RESPONSE = (
    "Olá! Sou o assistente A Sol da RF.\n"
    "No momento não há agentes configurados. Fale com o administrador."
)

_SELECTION_SYSTEM = (
    "Você é o despachante de um assistente WhatsApp. "
    "Analise a mensagem e escolha o agente mais adequado da lista. "
    "Responda APENAS com JSON válido, sem texto adicional: "
    '{"agent_id": "<id>"} '
    'ou {"agent_id": null} se nenhum for adequado.'
)


async def _load_active_agents() -> list[dict]:
    rows = await get_pool().fetch(
        "SELECT id, name, description FROM agents WHERE is_active = TRUE ORDER BY name"
    )
    return [dict(r) for r in rows]


async def _select_agent(user_message: str, agents: list[dict]) -> str | None:
    """Usa o modelo ativo para escolher qual agente invocar. Retorna agent_id ou None."""
    model_cfg = await get_active_model()
    if not model_cfg:
        # Sem modelo: delega ao primeiro agente
        return agents[0]["id"] if agents else None

    agents_desc = json.dumps(
        [{"id": a["id"], "name": a["name"], "description": a.get("description") or ""} for a in agents],
        ensure_ascii=False,
    )
    today = date.today().isoformat()
    user_prompt = (
        f"Data atual: {today}\n"
        f"Agentes disponíveis: {agents_desc}\n\n"
        f"Mensagem do usuário: \"{user_message}\""
    )

    provider = model_cfg.get("provider", "").lower()
    try:
        if provider == "anthropic":
            raw = await _call_anthropic_select(user_prompt, model_cfg)
        elif provider == "google":
            raw = await _call_google_select(user_prompt, model_cfg)
        else:
            raw = await _call_openai_select(user_prompt, model_cfg)
        data = json.loads(raw.strip())
        return data.get("agent_id")
    except Exception as e:
        logger.warning("[orchestrator] falha ao selecionar agente: %s — delegando ao primeiro", e)
        return agents[0]["id"] if agents else None


async def _call_anthropic_select(user_prompt: str, model_cfg: dict) -> str:
    headers = {
        "x-api-key": model_cfg["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_cfg["model"],
        "system": _SELECTION_SYSTEM,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 64,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
        r.raise_for_status()
        return r.json()["content"][0]["text"]


async def _call_openai_select(user_prompt: str, model_cfg: dict) -> str:
    provider = model_cfg.get("provider", "openai").lower()
    if provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
    elif provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
    else:
        url = "https://api.openai.com/v1/chat/completions"
    req_headers = {
        "Authorization": f"Bearer {model_cfg['api_key']}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        req_headers["HTTP-Referer"] = "https://a-sol-da-rf.onrender.com"
        req_headers["X-Title"] = "A Sol da RF"
    body = {
        "model": model_cfg["model"],
        "messages": [
            {"role": "system", "content": _SELECTION_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 64,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=body, headers=req_headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _call_google_select(user_prompt: str, model_cfg: dict) -> str:
    api_key = model_cfg["api_key"]
    model   = model_cfg["model"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": f"{_SELECTION_SYSTEM}\n\n{user_prompt}"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 64},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def dispatch(phone: str, user_message: str) -> str:
    """
    Ponto de entrada do orquestrador.
    Recebe mensagem do WhatsApp e retorna a resposta a enviar.
    """
    agents = await _load_active_agents()
    logger.info("[orchestrator] phone=%s agentes_ativos=%d", phone, len(agents))

    if not agents:
        logger.warning("[orchestrator] nenhum agente ativo configurado")
        return _FALLBACK_RESPONSE

    # Com apenas 1 agente, delega direto sem chamada extra de roteamento
    if len(agents) == 1:
        agent_id = agents[0]["id"]
        logger.info("[orchestrator] agente único → %s (%s)", agent_id, agents[0]["name"])
    else:
        agent_id = await _select_agent(user_message, agents)
        if not agent_id:
            logger.info("[orchestrator] nenhum agente selecionado para: %r", user_message)
            return (
                "Não entendi o que você precisa. Pode reformular a pergunta?"
            )
        logger.info("[orchestrator] agente selecionado: %s", agent_id)

    agent_name = next((a["name"] for a in agents if a["id"] == agent_id), None)
    t0 = time.monotonic()
    try:
        response, tool_calls_log = await agent_runner.run_agent(agent_id, user_message)
    except ValueError as e:
        logger.error("[orchestrator] agente inválido %s: %s", agent_id, e)
        return "Serviço temporariamente indisponível. Tente novamente."
    except Exception as e:
        logger.error("[orchestrator] erro ao executar agente %s: %s", agent_id, e)
        return "Não consegui processar sua solicitação agora. Tente novamente em instantes."

    duration_ms = int((time.monotonic() - t0) * 1000)
    try:
        pool = get_pool()
        await pool.execute(
            """INSERT INTO conversation_logs
               (id, phone, user_message, agent_id, agent_name, tool_calls, final_response, duration_ms)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            str(uuid.uuid4()),
            phone,
            user_message,
            agent_id,
            agent_name,
            json.dumps(tool_calls_log, ensure_ascii=False, default=str),
            response,
            duration_ms,
        )
    except Exception as e:
        logger.warning("[orchestrator] falha ao salvar log: %s", e)

    return response

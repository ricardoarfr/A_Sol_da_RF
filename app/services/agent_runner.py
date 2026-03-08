"""
Motor de Agentes Internos (Etapa 7).

Fluxo:
  1. Carrega agente + endpoints associados do DB
  2. Constrói definições de tools (cada endpoint = uma tool)
  3. Loop de AI com tool use:
     - Envia mensagem do usuário + system_prompt para o modelo
     - Se o modelo chamar uma tool → executa via executor.execute_endpoint
     - Alimenta o resultado de volta ao modelo
     - Repete até resposta final em texto
  4. Retorna texto da resposta final

Provedores suportados para tool use: anthropic, openai, openrouter, groq
Google (gemini): sem tool use nativo → descrições dos endpoints injetadas no system_prompt
"""

import json
import logging
import re

import httpx

from app.services import executor as executor_svc
from app.services.ai_config import get_active_model
from app.services.database import get_pool

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 10
_OPENAI_COMPAT_PROVIDERS = {"openai", "openrouter", "groq"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Converte nome legível em slug válido para nome de tool (max 64 chars)."""
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug[:64] or "endpoint"


async def _load_agent_and_model(agent_id: str) -> tuple[dict, dict]:
    """Carrega agente + modelo de IA configurado (específico ou ativo da plataforma)."""
    pool = get_pool()
    agent_row = await pool.fetchrow(
        "SELECT id, name, type, system_prompt, ai_model_id FROM agents WHERE id = $1 AND is_active = TRUE",
        agent_id,
    )
    if not agent_row:
        raise ValueError(f"Agente não encontrado ou inativo: {agent_id}")

    agent = dict(agent_row)

    # Modelo específico do agente ou modelo ativo da plataforma
    if agent["ai_model_id"]:
        model_row = await pool.fetchrow(
            "SELECT id, provider, model, api_key FROM ai_models WHERE id = $1",
            agent["ai_model_id"],
        )
        model_cfg = dict(model_row) if model_row else None
    else:
        model_cfg = await get_active_model()

    if not model_cfg:
        raise ValueError("Nenhum modelo de IA configurado.")

    return agent, model_cfg


async def _load_endpoints(agent_id: str) -> list[dict]:
    """Carrega endpoints associados ao agente."""
    pool = get_pool()
    rows = await pool.fetch(
        """SELECT e.id, e.name, e.description, e.method, e.path
           FROM endpoints e
           JOIN agent_endpoints ae ON ae.endpoint_id = e.id
           WHERE ae.agent_id = $1
           ORDER BY e.name""",
        agent_id,
    )
    return [dict(r) for r in rows]


def _build_tool_map(endpoints: list[dict]) -> dict[str, str]:
    """Retorna mapa slug → endpoint_id para despacho de tool calls."""
    return {_slugify(ep["name"]): ep["id"] for ep in endpoints}


def _tool_description(ep: dict) -> str:
    base = ep.get("description") or ""
    method_path = f'{ep["method"]} {ep["path"]}'
    return f"{base} [{method_path}]".strip() if base else method_path


# ---------------------------------------------------------------------------
# Chamadas por provedor — com tool use
# ---------------------------------------------------------------------------

async def _call_anthropic(
    messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    model_cfg: dict,
) -> dict:
    headers = {
        "x-api-key": model_cfg["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body: dict = {
        "model": model_cfg["model"],
        "system": system_prompt,
        "messages": messages,
        "max_tokens": 1024,
    }
    if tools:
        body["tools"] = tools

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
        response.raise_for_status()
        return response.json()


async def _call_openai_compat(
    messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    model_cfg: dict,
) -> dict:
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

    full_messages = [{"role": "system", "content": system_prompt}, *messages]
    body: dict = {
        "model": model_cfg["model"],
        "messages": full_messages,
        "temperature": 0,
        "max_tokens": 1024,
    }
    if tools:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        body["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=body, headers=req_headers)
        response.raise_for_status()
        return response.json()


async def _call_google_no_tools(
    user_message: str,
    system_prompt: str,
    endpoints: list[dict],
    model_cfg: dict,
) -> str:
    """Google Gemini: sem tool use — injeta descrições dos endpoints no system_prompt."""
    tools_desc = "\n".join(
        f'- {_slugify(ep["name"])}: {_tool_description(ep)}'
        for ep in endpoints
    )
    full_system = f"{system_prompt}\n\nFerramentas disponíveis (não podem ser chamadas diretamente):\n{tools_desc}"
    api_key = model_cfg["api_key"]
    model   = model_cfg["model"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": f"{full_system}\n\nUsuário: {user_message}"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

async def run_agent(agent_id: str, user_message: str) -> str:
    """
    Executa um agente e retorna a resposta final em texto.
    """
    agent, model_cfg = await _load_agent_and_model(agent_id)
    endpoints = await _load_endpoints(agent_id)
    provider  = model_cfg.get("provider", "").lower()
    system_prompt = agent.get("system_prompt") or "Você é um assistente útil."

    logger.info("[agent_runner] agente=%s provider=%s endpoints=%d", agent_id, provider, len(endpoints))

    # --- Google: sem tool use nativo ---
    if provider == "google":
        return await _call_google_no_tools(user_message, system_prompt, endpoints, model_cfg)

    # --- Anthropic / OpenAI compat: loop com tool use ---
    tool_map = _build_tool_map(endpoints)

    # Definições de tools no formato Anthropic
    tools = [
        {
            "name": _slugify(ep["name"]),
            "description": _tool_description(ep),
            "input_schema": {
                "type": "object",
                "properties": {
                    "params": {
                        "type": "object",
                        "description": "Parâmetros para substituir nas variáveis {chave} do endpoint (path, query, body, headers).",
                    }
                },
            },
        }
        for ep in endpoints
    ]

    messages: list[dict] = [{"role": "user", "content": user_message}]

    for iteration in range(_MAX_ITERATIONS):
        # Chama o modelo
        if provider == "anthropic":
            raw = await _call_anthropic(messages, system_prompt, tools, model_cfg)
            stop_reason = raw.get("stop_reason")
            content_blocks = raw.get("content", [])

            # Coleta tool_use calls
            tool_calls = [b for b in content_blocks if b.get("type") == "tool_use"]

            if stop_reason == "end_turn" or not tool_calls:
                # Resposta final
                text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
                return "\n".join(text_parts).strip() or "(sem resposta)"

            # Executa tools e alimenta resultados
            messages.append({"role": "assistant", "content": content_blocks})
            tool_results = []
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                ep_id = tool_map.get(tool_name)
                params = tc.get("input", {}).get("params", {})
                logger.info("[agent_runner] tool_call tool=%s ep_id=%s params=%s", tool_name, ep_id, params)
                if ep_id:
                    try:
                        result = await executor_svc.execute_endpoint(ep_id, params)
                        content = json.dumps(result, ensure_ascii=False, default=str)
                    except Exception as e:
                        content = f"Erro ao executar endpoint: {e}"
                else:
                    content = f"Tool desconhecida: {tool_name}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": content,
                })
            messages.append({"role": "user", "content": tool_results})

        else:
            # OpenAI compat
            raw = await _call_openai_compat(messages, system_prompt, tools, model_cfg)
            choice = raw["choices"][0]
            finish_reason = choice.get("finish_reason")
            msg = choice["message"]

            tool_calls_oai = msg.get("tool_calls") or []

            if finish_reason == "stop" or not tool_calls_oai:
                return msg.get("content") or "(sem resposta)"

            # Adiciona resposta do assistente
            messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": tool_calls_oai})

            for tc in tool_calls_oai:
                fn = tc["function"]
                tool_name = fn["name"]
                ep_id = tool_map.get(tool_name)
                try:
                    params = json.loads(fn.get("arguments", "{}")).get("params", {})
                except Exception:
                    params = {}
                logger.info("[agent_runner] tool_call tool=%s ep_id=%s params=%s", tool_name, ep_id, params)
                if ep_id:
                    try:
                        result = await executor_svc.execute_endpoint(ep_id, params)
                        content = json.dumps(result, ensure_ascii=False, default=str)
                    except Exception as e:
                        content = f"Erro ao executar endpoint: {e}"
                else:
                    content = f"Tool desconhecida: {tool_name}"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": content,
                })

    logger.warning("[agent_runner] limite de iterações atingido para agente %s", agent_id)
    return "Não consegui concluir a tarefa. Tente novamente."

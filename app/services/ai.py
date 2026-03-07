import json
import logging
import httpx
from app.services.ai_config import get_active_model

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é um assistente de campo da empresa RF.
Sua função é interpretar mensagens de técnicos, supervisores e gestores e decidir qual ação tomar.

Responda APENAS com JSON válido, sem texto adicional, no formato:
{"action": "<ação>", "params": {<parâmetros>}}

Ações disponíveis:
- "greeting"     — saudação ou mensagem genérica. params: {}
- "activities"   — listar atividades/OS/agenda. params: {"date": "today|tomorrow|yesterday", "status": "pending|completed|overdue"} (status é opcional)
- "technicians"  — listar técnicos da equipe. params: {}
- "unknown"      — não foi possível identificar. params: {}

Exemplos:
- "oi tudo bem"                    → {"action": "greeting", "params": {}}
- "atividades de hoje"             → {"action": "activities", "params": {"date": "today"}}
- "quais as OS de amanhã?"         → {"action": "activities", "params": {"date": "tomorrow"}}
- "me mostra as pendentes de hoje" → {"action": "activities", "params": {"date": "today", "status": "pending"}}
- "lista os técnicos"              → {"action": "technicians", "params": {}}
"""

_OPENAI_COMPAT_PROVIDERS = {"openai", "openrouter", "groq"}


async def validate_key(provider: str, model: str, api_key: str) -> None:
    """Test API key with a minimal call. Raises ValueError with user-friendly message on failure."""
    provider = provider.lower()
    cfg = {"provider": provider, "model": model, "api_key": api_key}
    probe = "teste"
    try:
        if provider in _OPENAI_COMPAT_PROVIDERS:
            await _call_openai_compat(probe, cfg, max_tokens=1)
        elif provider == "anthropic":
            await _call_anthropic(probe, cfg, max_tokens=1)
        elif provider == "google":
            await _call_google(probe, cfg, max_tokens=1)
        else:
            raise ValueError(f"Provedor desconhecido: {provider}")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in (401, 403):
            raise ValueError("Chave de API inválida ou sem permissão.")
        if status == 429:
            raise ValueError("Limite de requisições atingido. Aguarde e tente novamente.")
        raise ValueError(f"Erro ao validar chave ({status}). Verifique o provedor e o modelo.")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Não foi possível validar a chave: {e}")


async def classify_message(text: str) -> dict:
    """Use active AI model to classify user intent. Returns {"action": str, "params": dict} or {"action": None} if no model active."""
    model_cfg = get_active_model()
    if not model_cfg:
        return {"action": None, "params": {}}

    provider = model_cfg.get("provider", "").lower()

    try:
        if provider in _OPENAI_COMPAT_PROVIDERS:
            return await _call_openai_compat(text, model_cfg)
        elif provider == "anthropic":
            return await _call_anthropic(text, model_cfg)
        elif provider == "google":
            return await _call_google(text, model_cfg)
        else:
            logger.warning(f"Unknown AI provider: {provider}")
            return {"action": None, "params": {}}
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        return {"action": None, "params": {}}


def _openai_compat_base_url(provider: str) -> str:
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1/chat/completions"
    if provider == "groq":
        return "https://api.groq.com/openai/v1/chat/completions"
    return "https://api.openai.com/v1/chat/completions"


async def _call_openai_compat(text: str, model_cfg: dict, max_tokens: int = 100) -> dict:
    provider = model_cfg.get("provider", "openai").lower()
    headers = {
        "Authorization": f"Bearer {model_cfg['api_key']}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://a-sol-da-rf.onrender.com"
        headers["X-Title"] = "A Sol da RF"
    body = {
        "model": model_cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(_openai_compat_base_url(provider), json=body, headers=headers)
        response.raise_for_status()
        if max_tokens == 1:
            return {"action": None, "params": {}}
        content = response.json()["choices"][0]["message"]["content"]
        return _parse(content)


async def _call_anthropic(text: str, model_cfg: dict, max_tokens: int = 100) -> dict:
    headers = {
        "x-api-key": model_cfg["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_cfg["model"],
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
        response.raise_for_status()
        if max_tokens == 1:
            return {"action": None, "params": {}}
        content = response.json()["content"][0]["text"]
        return _parse(content)


async def _call_google(text: str, model_cfg: dict, max_tokens: int = 100) -> dict:
    api_key = model_cfg["api_key"]
    model = model_cfg["model"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\n{text}"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()
        if max_tokens == 1:
            return {"action": None, "params": {}}
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _parse(content)


def _parse(content: str) -> dict:
    try:
        text = content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        if "action" in data:
            return data
    except Exception as e:
        logger.warning(f"Failed to parse AI response: {e} | raw: {content!r}")
    return {"action": None, "params": {}}

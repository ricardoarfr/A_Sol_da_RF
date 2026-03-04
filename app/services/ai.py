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


async def classify_message(text: str) -> dict:
    """Use active AI model to classify user intent. Returns {"action": str, "params": dict} or {"action": None} if no model active."""
    model_cfg = get_active_model()
    if not model_cfg:
        return {"action": None, "params": {}}

    provider = model_cfg.get("provider", "").lower()

    try:
        if provider == "openai":
            return await _call_openai(text, model_cfg)
        elif provider == "anthropic":
            return await _call_anthropic(text, model_cfg)
        else:
            logger.warning(f"Unknown AI provider: {provider}")
            return {"action": None, "params": {}}
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        return {"action": None, "params": {}}


async def _call_openai(text: str, model_cfg: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {model_cfg['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": 100,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=body,
            headers=headers,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse(content)


async def _call_anthropic(text: str, model_cfg: dict) -> dict:
    headers = {
        "x-api-key": model_cfg["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_cfg["model"],
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": 100,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=body,
            headers=headers,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
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

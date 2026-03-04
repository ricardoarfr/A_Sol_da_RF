import logging
from datetime import date, timedelta
from fastapi import APIRouter, Request, HTTPException
from app.models.webhook import ZAPIWebhookPayload
from app.services.zapi import send_text_message
from app.services import produttivo, phone_auth, ai

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook/zapi")
async def zapi_webhook(request: Request):
    """Receive and process incoming WhatsApp messages from Z-API."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info(f"Webhook received: {body}")

    payload = ZAPIWebhookPayload(**body)

    if payload.is_from_me():
        return {"status": "ignored", "reason": "fromMe"}

    text = payload.get_text()
    phone = payload.phone

    if not phone or not text:
        return {"status": "ignored", "reason": "no_text_or_phone"}

    logger.info(f"Message from {phone}: {text}")

    if not phone_auth.is_authorized(phone):
        logger.info(f"Unauthorized phone: {phone}")
        await send_text_message(phone, "Você não tem acesso ao assistente, fale com Ricardo.")
        return {"status": "unauthorized"}

    reply = await handle_message(phone, text)

    await send_text_message(phone, reply)
    return {"status": "ok"}


# --- Intent detection: AI first, keyword fallback ---

async def _detect_intent(text: str) -> tuple[str, dict]:
    """Returns (intent, params). Uses AI if available, falls back to keywords."""
    result = await ai.classify_message(text)

    if result.get("action"):
        logger.info(f"AI classified intent: {result}")
        return result["action"], result.get("params", {})

    # Keyword fallback
    logger.info("No active AI model, using keyword detection")
    t = text.strip().lower()
    if any(w in t for w in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return "greeting", {}
    if any(w in t for w in ["atividade", "atividades", "os", "agenda", "tarefa", "tarefas", "serviço", "servicos"]):
        return "activities", _keyword_activity_params(t)
    if any(w in t for w in ["técnico", "tecnicos", "tecnico", "equipe", "time"]):
        return "technicians", {}
    return "unknown", {}


def _keyword_activity_params(t: str) -> dict:
    today = date.today()
    params: dict = {}
    if "amanhã" in t or "amanha" in t:
        params["date"] = "tomorrow"
    elif "ontem" in t:
        params["date"] = "yesterday"
    else:
        params["date"] = "today"
    if "pendente" in t or "aberta" in t or "abertas" in t:
        params["status"] = "pending"
    elif "concluída" in t or "concluida" in t or "feita" in t or "feitas" in t:
        params["status"] = "completed"
    elif "atrasada" in t or "atrasadas" in t:
        params["status"] = "overdue"
    return params


def _resolve_date(date_param: str) -> str:
    today = date.today()
    if date_param == "tomorrow":
        return str(today + timedelta(days=1))
    if date_param == "yesterday":
        return str(today - timedelta(days=1))
    if date_param == "today":
        return str(today)
    # Allow ISO date strings passed directly
    return date_param or str(today)


# --- Response formatters ---

def _format_activities(activities: list, date_str: str) -> str:
    if not activities:
        return f"Nenhuma atividade encontrada para *{date_str}*."

    lines = [f"*Atividades — {date_str}* ({len(activities)} encontradas)\n"]
    for act in activities[:10]:
        name = act.get("title") or act.get("name") or act.get("description") or "Sem título"
        status = act.get("status") or ""
        technician = act.get("user", {}).get("name") or act.get("technician") or ""
        address = act.get("address") or act.get("local") or ""

        line = f"• *{name}*"
        if status:
            line += f" [{status}]"
        if technician:
            line += f"\n  _Técnico:_ {technician}"
        if address:
            line += f"\n  _Local:_ {address}"
        lines.append(line)

    if len(activities) > 10:
        lines.append(f"\n_...e mais {len(activities) - 10} atividades._")

    return "\n".join(lines)


def _format_technicians(technicians: list) -> str:
    if not technicians:
        return "Nenhum técnico encontrado."

    lines = [f"*Técnicos cadastrados* ({len(technicians)})\n"]
    for tech in technicians:
        name = tech.get("name") or tech.get("full_name") or "Sem nome"
        role = tech.get("role") or tech.get("profile") or ""
        line = f"• {name}"
        if role:
            line += f" _({role})_"
        lines.append(line)

    return "\n".join(lines)


# --- Main handler ---

async def handle_message(phone: str, text: str) -> str:
    intent, params = await _detect_intent(text)

    if intent == "greeting":
        return (
            "Olá! Sou o assistente da RF. Posso te ajudar com:\n"
            "• *atividades* — listar atividades (hoje, amanhã, ontem)\n"
            "• *técnicos* — ver técnicos da equipe\n\n"
            "O que você precisa?"
        )

    if intent == "activities":
        try:
            date_str = _resolve_date(params.get("date", "today"))
            filters: dict = {"date": date_str}
            if params.get("status"):
                filters["status"] = params["status"]
            logger.info(f"Fetching activities with filters: {filters}")
            activities = await produttivo.get_activities(filters)
            return _format_activities(activities, date_str)
        except Exception as e:
            logger.error(f"Error fetching activities: {e}")
            return "Não consegui buscar as atividades agora. Tente novamente em instantes."

    if intent == "technicians":
        try:
            logger.info("Fetching technicians")
            technicians = await produttivo.get_technicians()
            return _format_technicians(technicians)
        except Exception as e:
            logger.error(f"Error fetching technicians: {e}")
            return "Não consegui buscar os técnicos agora. Tente novamente em instantes."

    return (
        "Não entendi o que você precisa. Tente:\n"
        "• *atividades de hoje*\n"
        "• *atividades de amanhã*\n"
        "• *técnicos*"
    )

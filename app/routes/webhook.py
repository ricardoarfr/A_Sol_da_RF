import logging
from fastapi import APIRouter, Request, HTTPException
from app.models.webhook import ZAPIWebhookPayload
from app.services.zapi import send_text_message

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

    # Ignore messages sent by the bot itself
    if payload.is_from_me():
        return {"status": "ignored", "reason": "fromMe"}

    text = payload.get_text()
    phone = payload.phone

    if not phone or not text:
        return {"status": "ignored", "reason": "no_text_or_phone"}

    logger.info(f"Message from {phone}: {text}")

    # TODO: process with AI and route to appropriate handler
    reply = await handle_message(phone, text)

    await send_text_message(phone, reply)
    return {"status": "ok"}


async def handle_message(phone: str, text: str) -> str:
    """Route incoming message to the correct handler. Placeholder for AI integration."""
    text_lower = text.strip().lower()

    if any(word in text_lower for word in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return (
            "Olá! Sou o assistente da RF. Posso te ajudar com:\n"
            "• *atividades* — listar atividades do dia\n"
            "• *técnicos* — ver técnicos disponíveis\n\n"
            "O que você precisa?"
        )

    return "Recebi sua mensagem. Em breve terei mais funcionalidades disponíveis!"

import logging
import uuid

from app.services.database import get_pool

logger = logging.getLogger(__name__)


async def list_models() -> list[dict]:
    rows = await get_pool().fetch("SELECT id, name, provider, model, is_active FROM ai_models ORDER BY name")
    return [dict(r) for r in rows]


async def get_active_model() -> dict | None:
    row = await get_pool().fetchrow(
        "SELECT id, name, provider, model, api_key FROM ai_models WHERE is_active = TRUE LIMIT 1"
    )
    return dict(row) if row else None


async def add_model(name: str, provider: str, model: str, api_key: str) -> dict:
    existing = await get_pool().fetchval(
        "SELECT id FROM ai_models WHERE provider = $1 AND model = $2", provider, model
    )
    if existing:
        raise ValueError(f"Modelo '{provider}/{model}' já está cadastrado.")
    entry_id = str(uuid.uuid4())
    await get_pool().execute(
        "INSERT INTO ai_models (id, name, provider, model, api_key) VALUES ($1, $2, $3, $4, $5)",
        entry_id, name, provider, model, api_key,
    )
    logger.info(f"AI model added: {name} ({provider}/{model})")
    return {"id": entry_id, "name": name, "provider": provider, "model": model, "api_key": "***", "is_active": False}


async def update_model(model_id: str, name: str, provider: str, model: str, api_key: str | None) -> dict:
    conflict = await get_pool().fetchval(
        "SELECT id FROM ai_models WHERE provider = $1 AND model = $2 AND id != $3", provider, model, model_id
    )
    if conflict:
        raise ValueError(f"Modelo '{provider}/{model}' já está cadastrado.")

    if api_key:
        row = await get_pool().fetchrow(
            "UPDATE ai_models SET name=$1, provider=$2, model=$3, api_key=$4 WHERE id=$5 "
            "RETURNING id, name, provider, model, is_active",
            name, provider, model, api_key, model_id,
        )
    else:
        row = await get_pool().fetchrow(
            "UPDATE ai_models SET name=$1, provider=$2, model=$3 WHERE id=$4 "
            "RETURNING id, name, provider, model, is_active",
            name, provider, model, model_id,
        )
    if not row:
        raise ValueError("Modelo não encontrado.")
    logger.info(f"AI model updated: {model_id}")
    return {**dict(row), "api_key": "***"}


async def delete_model(model_id: str) -> None:
    await get_pool().execute("DELETE FROM ai_models WHERE id = $1", model_id)
    logger.info(f"AI model deleted: {model_id}")


async def activate_model(model_id: str) -> None:
    exists = await get_pool().fetchval("SELECT id FROM ai_models WHERE id = $1", model_id)
    if not exists:
        raise ValueError("Modelo não encontrado.")
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE ai_models SET is_active = FALSE")
            await conn.execute("UPDATE ai_models SET is_active = TRUE WHERE id = $1", model_id)
    logger.info(f"AI model activated: {model_id}")

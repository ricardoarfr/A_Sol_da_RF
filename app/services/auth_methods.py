import logging
import uuid

from app.services.database import get_pool

logger = logging.getLogger(__name__)

# Tipos suportados de autenticação
AUTH_TYPES = {
    "api_key", "bearer", "basic", "oauth",
    "custom_header", "cookie_session", "reverse_engineering",
}


async def list_auth_methods(system_id: str | None = None) -> list[dict]:
    if system_id:
        rows = await get_pool().fetch(
            "SELECT id, system_id, name, type, config, description, created_at, updated_at"
            " FROM auth_methods WHERE system_id = $1 ORDER BY name",
            system_id,
        )
    else:
        rows = await get_pool().fetch(
            "SELECT id, system_id, name, type, config, description, created_at, updated_at"
            " FROM auth_methods ORDER BY name"
        )
    return [dict(r) for r in rows]


async def get_auth_method(auth_method_id: str) -> dict | None:
    row = await get_pool().fetchrow(
        "SELECT id, system_id, name, type, config, description, created_at, updated_at"
        " FROM auth_methods WHERE id = $1",
        auth_method_id,
    )
    return dict(row) if row else None


async def create_auth_method(
    system_id: str | None,
    name: str,
    auth_type: str,
    config: str,
    description: str,
) -> dict:
    if auth_type not in AUTH_TYPES:
        raise ValueError(f"Tipo inválido: {auth_type}. Válidos: {sorted(AUTH_TYPES)}")
    method_id = str(uuid.uuid4())
    row = await get_pool().fetchrow(
        """INSERT INTO auth_methods (id, system_id, name, type, config, description)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id, system_id, name, type, config, description, created_at, updated_at""",
        method_id, system_id, name, auth_type, config, description,
    )
    logger.info(f"AuthMethod created: {method_id} ({name}, type={auth_type})")
    return dict(row)


async def update_auth_method(
    auth_method_id: str,
    system_id: str | None,
    name: str,
    auth_type: str,
    config: str,
    description: str,
) -> dict:
    if auth_type not in AUTH_TYPES:
        raise ValueError(f"Tipo inválido: {auth_type}. Válidos: {sorted(AUTH_TYPES)}")
    row = await get_pool().fetchrow(
        """UPDATE auth_methods
           SET system_id=$1, name=$2, type=$3, config=$4, description=$5, updated_at=NOW()
           WHERE id=$6
           RETURNING id, system_id, name, type, config, description, created_at, updated_at""",
        system_id, name, auth_type, config, description, auth_method_id,
    )
    if not row:
        raise ValueError("Método de autenticação não encontrado.")
    logger.info(f"AuthMethod updated: {auth_method_id}")
    return dict(row)


async def delete_auth_method(auth_method_id: str) -> None:
    await get_pool().execute("DELETE FROM auth_methods WHERE id = $1", auth_method_id)
    logger.info(f"AuthMethod deleted: {auth_method_id}")

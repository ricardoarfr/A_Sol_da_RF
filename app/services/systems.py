import logging
import uuid

from app.services.database import get_pool

logger = logging.getLogger(__name__)


async def list_systems() -> list[dict]:
    rows = await get_pool().fetch(
        "SELECT id, name, description, base_url, environment, notes, created_at, updated_at"
        " FROM systems ORDER BY name"
    )
    return [dict(r) for r in rows]


async def get_system(system_id: str) -> dict | None:
    row = await get_pool().fetchrow(
        "SELECT id, name, description, base_url, environment, notes, created_at, updated_at"
        " FROM systems WHERE id = $1",
        system_id,
    )
    return dict(row) if row else None


async def create_system(
    name: str,
    description: str,
    base_url: str,
    environment: str,
    notes: str,
) -> dict:
    system_id = str(uuid.uuid4())
    row = await get_pool().fetchrow(
        """INSERT INTO systems (id, name, description, base_url, environment, notes)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id, name, description, base_url, environment, notes, created_at, updated_at""",
        system_id, name, description, base_url, environment, notes,
    )
    logger.info(f"System created: {system_id} ({name})")
    return dict(row)


async def update_system(
    system_id: str,
    name: str,
    description: str,
    base_url: str,
    environment: str,
    notes: str,
) -> dict:
    row = await get_pool().fetchrow(
        """UPDATE systems
           SET name=$1, description=$2, base_url=$3, environment=$4, notes=$5, updated_at=NOW()
           WHERE id=$6
           RETURNING id, name, description, base_url, environment, notes, created_at, updated_at""",
        name, description, base_url, environment, notes, system_id,
    )
    if not row:
        raise ValueError("Sistema não encontrado.")
    logger.info(f"System updated: {system_id}")
    return dict(row)


async def delete_system(system_id: str) -> None:
    await get_pool().execute("DELETE FROM systems WHERE id = $1", system_id)
    logger.info(f"System deleted: {system_id}")

import logging
import uuid

from app.services.database import get_pool

logger = logging.getLogger(__name__)

AGENT_TYPES = {"internal", "external", "orchestrator"}


async def list_agents() -> list[dict]:
    rows = await get_pool().fetch(
        "SELECT id, name, description, type, ai_model_id, system_prompt, is_active, created_at, updated_at"
        " FROM agents ORDER BY name"
    )
    return [dict(r) for r in rows]


async def get_agent(agent_id: str) -> dict | None:
    row = await get_pool().fetchrow(
        "SELECT id, name, description, type, ai_model_id, system_prompt, is_active, created_at, updated_at"
        " FROM agents WHERE id = $1",
        agent_id,
    )
    if not row:
        return None
    agent = dict(row)
    ep_rows = await get_pool().fetch(
        "SELECT endpoint_id FROM agent_endpoints WHERE agent_id = $1", agent_id
    )
    agent["endpoint_ids"] = [r["endpoint_id"] for r in ep_rows]
    return agent


async def create_agent(
    name: str,
    description: str,
    agent_type: str,
    ai_model_id: str | None,
    system_prompt: str,
    is_active: bool,
) -> dict:
    if agent_type not in AGENT_TYPES:
        raise ValueError(f"Tipo inválido: {agent_type}. Válidos: {sorted(AGENT_TYPES)}")
    agent_id = str(uuid.uuid4())
    row = await get_pool().fetchrow(
        """INSERT INTO agents (id, name, description, type, ai_model_id, system_prompt, is_active)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING id, name, description, type, ai_model_id, system_prompt, is_active, created_at, updated_at""",
        agent_id, name, description, agent_type, ai_model_id, system_prompt, is_active,
    )
    logger.info(f"Agent created: {agent_id} ({name}, type={agent_type})")
    agent = dict(row)
    agent["endpoint_ids"] = []
    return agent


async def update_agent(
    agent_id: str,
    name: str,
    description: str,
    agent_type: str,
    ai_model_id: str | None,
    system_prompt: str,
    is_active: bool,
) -> dict:
    if agent_type not in AGENT_TYPES:
        raise ValueError(f"Tipo inválido: {agent_type}. Válidos: {sorted(AGENT_TYPES)}")
    row = await get_pool().fetchrow(
        """UPDATE agents
           SET name=$1, description=$2, type=$3, ai_model_id=$4, system_prompt=$5, is_active=$6, updated_at=NOW()
           WHERE id=$7
           RETURNING id, name, description, type, ai_model_id, system_prompt, is_active, created_at, updated_at""",
        name, description, agent_type, ai_model_id, system_prompt, is_active, agent_id,
    )
    if not row:
        raise ValueError("Agente não encontrado.")
    logger.info(f"Agent updated: {agent_id}")
    agent = dict(row)
    ep_rows = await get_pool().fetch(
        "SELECT endpoint_id FROM agent_endpoints WHERE agent_id = $1", agent_id
    )
    agent["endpoint_ids"] = [r["endpoint_id"] for r in ep_rows]
    return agent


async def delete_agent(agent_id: str) -> None:
    await get_pool().execute("DELETE FROM agents WHERE id = $1", agent_id)
    logger.info(f"Agent deleted: {agent_id}")


async def set_agent_endpoints(agent_id: str, endpoint_ids: list[str]) -> dict:
    """Substitui todas as associações agent→endpoint."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM agent_endpoints WHERE agent_id = $1", agent_id)
            if endpoint_ids:
                await conn.executemany(
                    "INSERT INTO agent_endpoints (agent_id, endpoint_id) VALUES ($1, $2)"
                    " ON CONFLICT DO NOTHING",
                    [(agent_id, ep_id) for ep_id in endpoint_ids],
                )
    logger.info(f"Agent {agent_id} endpoints updated: {endpoint_ids}")
    return {"agent_id": agent_id, "endpoint_ids": endpoint_ids}

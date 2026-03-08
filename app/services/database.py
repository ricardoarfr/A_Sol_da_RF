import logging
import asyncpg
from app.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_models (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    provider  TEXT NOT NULL,
    model     TEXT NOT NULL,
    api_key   TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS authorized_phones (
    id    TEXT PRIMARY KEY,
    phone TEXT NOT NULL UNIQUE,
    name  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS whatsapp_session (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ─── Orquestração de Agentes ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS systems (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    base_url    TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'production',
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_methods (
    id          TEXT PRIMARY KEY,
    system_id   TEXT REFERENCES systems(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,
    config      TEXT NOT NULL DEFAULT '{}',
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS endpoints (
    id               TEXT PRIMARY KEY,
    system_id        TEXT NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
    auth_method_id   TEXT REFERENCES auth_methods(id) ON DELETE SET NULL,
    name             TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    method           TEXT NOT NULL DEFAULT 'GET',
    path             TEXT NOT NULL,
    headers          TEXT NOT NULL DEFAULT '{}',
    query_params     TEXT NOT NULL DEFAULT '{}',
    body_template    TEXT NOT NULL DEFAULT '{}',
    response_example TEXT NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agents (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    type          TEXT NOT NULL DEFAULT 'internal',
    ai_model_id   TEXT REFERENCES ai_models(id) ON DELETE SET NULL,
    system_prompt TEXT NOT NULL DEFAULT '',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_endpoints (
    agent_id    TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    endpoint_id TEXT NOT NULL REFERENCES endpoints(id) ON DELETE CASCADE,
    PRIMARY KEY (agent_id, endpoint_id)
);
"""


async def init() -> None:
    global _pool
    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL não configurado — banco de dados desabilitado")
        return
    try:
        _pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(_SCHEMA)
        logger.info("Banco de dados inicializado")
    except Exception as e:
        logger.error(f"Falha ao conectar ao banco de dados: {e} — continuando sem banco")
        _pool = None


async def close() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Banco de dados não disponível — configure DATABASE_URL")
    return _pool

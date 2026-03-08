import logging
import asyncpg
from app.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_models (
    id       TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    provider TEXT NOT NULL,
    model    TEXT NOT NULL,
    api_key  TEXT NOT NULL,
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

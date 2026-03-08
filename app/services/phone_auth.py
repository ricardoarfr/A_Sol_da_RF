import logging
import re
import uuid

from app.services.database import get_pool

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Strip non-digits, ensure DDI 55, and remove the 9th digit from mobile numbers (BR normalization)."""
    digits = re.sub(r"\D", "", phone)
    if not digits.startswith("55"):
        digits = "55" + digits
    # 55 + DD(2) + 9 + number(8) = 13 digits → strip the leading 9 of the local number
    if len(digits) == 13 and digits[4] == "9":
        digits = digits[:4] + digits[5:]
    return digits


async def is_authorized(phone: str) -> bool:
    normalized = normalize_phone(phone)
    row = await get_pool().fetchval("SELECT id FROM authorized_phones WHERE phone = $1", normalized)
    return row is not None


async def list_phones() -> list[dict]:
    rows = await get_pool().fetch("SELECT id, phone, name FROM authorized_phones ORDER BY name")
    return [dict(r) for r in rows]


async def add_phone(phone: str, name: str = "") -> dict:
    normalized = normalize_phone(phone)
    existing = await get_pool().fetchval("SELECT id FROM authorized_phones WHERE phone = $1", normalized)
    if existing:
        raise ValueError(f"Número {normalized} já está cadastrado.")
    entry_id = str(uuid.uuid4())
    await get_pool().execute(
        "INSERT INTO authorized_phones (id, phone, name) VALUES ($1, $2, $3)",
        entry_id, normalized, name,
    )
    logger.info(f"Phone authorized: {normalized} ({name})")
    return {"id": entry_id, "phone": normalized, "name": name}


async def update_phone(phone_id: str, phone: str, name: str = "") -> dict:
    normalized = normalize_phone(phone)
    conflict = await get_pool().fetchval(
        "SELECT id FROM authorized_phones WHERE phone = $1 AND id != $2", normalized, phone_id
    )
    if conflict:
        raise ValueError(f"Número {normalized} já está cadastrado.")
    row = await get_pool().fetchrow(
        "UPDATE authorized_phones SET phone=$1, name=$2 WHERE id=$3 RETURNING id, phone, name",
        normalized, name, phone_id,
    )
    if not row:
        raise ValueError("Número não encontrado.")
    logger.info(f"Phone updated: {phone_id} -> {normalized}")
    return dict(row)


async def delete_phone(phone_id: str) -> None:
    await get_pool().execute("DELETE FROM authorized_phones WHERE id = $1", phone_id)
    logger.info(f"Phone removed: {phone_id}")

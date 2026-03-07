import json
import logging
import re
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("data/authorized_phones.json")


def normalize_phone(phone: str) -> str:
    """Strip non-digits, ensure DDI 55, and remove the 9th digit from mobile numbers (BR normalization)."""
    digits = re.sub(r"\D", "", phone)
    if not digits.startswith("55"):
        digits = "55" + digits
    # 55 + DD(2) + 9 + number(8) = 13 digits → strip the leading 9 of the local number
    if len(digits) == 13 and digits[4] == "9":
        digits = digits[:4] + digits[5:]
    return digits


def _load() -> list[dict]:
    if not CONFIG_PATH.exists():
        return []
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception as e:
        logger.error(f"Error reading authorized phones: {e}")
        return []


def _save(data: list[dict]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def is_authorized(phone: str) -> bool:
    """Return False if list is empty or phone is not in it."""
    phones = _load()
    if not phones:
        return False
    normalized = normalize_phone(phone)
    return any(p["phone"] == normalized for p in phones)


def list_phones() -> list[dict]:
    return _load()


def add_phone(phone: str, name: str = "") -> dict:
    phones = _load()
    normalized = normalize_phone(phone)
    if any(p["phone"] == normalized for p in phones):
        raise ValueError(f"Número {normalized} já está cadastrado.")
    entry = {"id": str(uuid.uuid4()), "phone": normalized, "name": name}
    phones.append(entry)
    _save(phones)
    logger.info(f"Phone authorized: {normalized} ({name})")
    return entry


def update_phone(phone_id: str, phone: str, name: str = "") -> dict:
    phones = _load()
    normalized = normalize_phone(phone)
    for p in phones:
        if p["id"] == phone_id:
            continue
        if p["phone"] == normalized:
            raise ValueError(f"Número {normalized} já está cadastrado.")
    for p in phones:
        if p["id"] == phone_id:
            p["phone"] = normalized
            p["name"] = name
            _save(phones)
            logger.info(f"Phone updated: {phone_id} -> {normalized}")
            return p
    raise ValueError("Número não encontrado.")


def delete_phone(phone_id: str) -> None:
    phones = _load()
    phones = [p for p in phones if p["id"] != phone_id]
    _save(phones)
    logger.info(f"Phone removed: {phone_id}")

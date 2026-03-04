import json
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("data/ai_models.json")


def _load() -> dict:
    if not CONFIG_PATH.exists():
        return {"models": [], "active_id": None}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception as e:
        logger.error(f"Error reading AI models config: {e}")
        return {"models": [], "active_id": None}


def _save(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def list_models() -> list[dict]:
    data = _load()
    return [
        {**m, "api_key": "***" if m.get("api_key") else ""}
        for m in data["models"]
    ]


def get_active_model() -> dict | None:
    data = _load()
    active_id = data.get("active_id")
    for m in data["models"]:
        if m["id"] == active_id:
            return m
    return None


def add_model(name: str, provider: str, model: str, api_key: str) -> dict:
    data = _load()
    for m in data["models"]:
        if m["provider"] == provider and m["model"] == model:
            raise ValueError(f"Modelo '{provider}/{model}' já está cadastrado.")
    entry = {"id": str(uuid.uuid4()), "name": name, "provider": provider, "model": model, "api_key": api_key}
    data["models"].append(entry)
    _save(data)
    logger.info(f"AI model added: {name} ({provider}/{model})")
    return {**entry, "api_key": "***"}


def update_model(model_id: str, name: str, provider: str, model: str, api_key: str | None) -> dict:
    data = _load()
    for m in data["models"]:
        if m["id"] == model_id:
            continue
        if m["provider"] == provider and m["model"] == model:
            raise ValueError(f"Modelo '{provider}/{model}' já está cadastrado.")

    for m in data["models"]:
        if m["id"] == model_id:
            m["name"] = name
            m["provider"] = provider
            m["model"] = model
            if api_key:
                m["api_key"] = api_key
            _save(data)
            logger.info(f"AI model updated: {model_id}")
            return {**m, "api_key": "***"}

    raise ValueError("Modelo não encontrado.")


def delete_model(model_id: str) -> None:
    data = _load()
    data["models"] = [m for m in data["models"] if m["id"] != model_id]
    if data.get("active_id") == model_id:
        data["active_id"] = None
    _save(data)
    logger.info(f"AI model deleted: {model_id}")


def activate_model(model_id: str) -> None:
    data = _load()
    ids = [m["id"] for m in data["models"]]
    if model_id not in ids:
        raise ValueError("Modelo não encontrado.")
    data["active_id"] = model_id
    _save(data)
    logger.info(f"AI model activated: {model_id}")

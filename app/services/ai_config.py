import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("data/ai_config.json")
DEFAULT_CONFIG: dict = {"provider": "", "model": "", "api_key": ""}


def read_config() -> dict:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception as e:
        logger.error(f"Error reading AI config: {e}")
        return DEFAULT_CONFIG.copy()


def write_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    logger.info(f"AI config saved: provider={config.get('provider')}, model={config.get('model')}")

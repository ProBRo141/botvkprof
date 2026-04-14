import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)
BASE = Path("/home/container" if os.path.exists("/home/container") else ".")
FILE = BASE / "results.json"


def _load() -> dict:
    if FILE.exists():
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Results load error: %s", e)
    return {}


def _save(data: dict):
    try:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Results save error: %s", e)


def save_result(user_id: int, result: dict):
    data = _load()
    data[str(user_id)] = result
    _save(data)


def get_last_result(user_id: int) -> dict | None:
    data = _load()
    return data.get(str(user_id))

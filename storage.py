import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)
BASE = Path("/home/container" if os.path.exists("/home/container") else ".")
FILE = BASE / "vk_fsm_state.json"


class JsonStorage:
    """Состояние VK-пользователя: { user_id: { state, data } }."""

    def __init__(self):
        self._data: dict = {}
        self._load()

    def _load(self):
        if FILE.exists():
            try:
                self._data = json.loads(FILE.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Storage load: %s", e)

    def _save(self):
        try:
            FILE.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning("Storage save: %s", e)

    def get_user(self, user_id: int) -> dict:
        return self._data.get(str(user_id), {"state": None, "data": {}}).copy()

    def set_user(self, user_id: int, state: str | None, data: dict):
        self._data[str(user_id)] = {"state": state, "data": dict(data)}
        self._save()

    def set_state(self, user_id: int, state: str | None):
        u = self.get_user(user_id)
        self.set_user(user_id, state, u.get("data", {}))

    def update_data(self, user_id: int, **kwargs):
        u = self.get_user(user_id)
        d = u.get("data", {})
        d.update(kwargs)
        self.set_user(user_id, u.get("state"), d)

    def clear_data(self, user_id: int):
        self.set_user(user_id, None, {})

    def pop_data_keys(self, user_id: int, keys: list[str]):
        u = self.get_user(user_id)
        d = u.get("data", {})
        for k in keys:
            d.pop(k, None)
        self.set_user(user_id, u.get("state"), d)

"""
Сохранение строк в CSV на Яндекс Диске (открыть файл → «В Яндекс Таблицах»).
Столбцы совместимы с бывшим Google Sheets (sheets.py).
"""
import csv
import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HEADERS_RU = [
    "Дата",
    "VK",
    "ID",
    "Возраст",
    "Город",
    "Образование",
    "Часов/нед",
    "Интересы",
    "Не нравится",
    "Формат работы",
    "Навыки",
    "Опыт",
    "Коммуникация",
    "Цель",
    "Ограничения",
    "Приоритет",
    "Рекомендации",
    "План 14 дней",
    "К консультации",
    "Телефон",
]

ROW_KEYS = [
    "timestamp",
    "vk_profile",
    "vk_id",
    "age",
    "city",
    "education",
    "hours",
    "interests",
    "dislikes",
    "work_format",
    "skills",
    "experience",
    "communication",
    "goal",
    "limits",
    "priority",
    "top_directions",
    "plan_14_days",
    "ready_for_consultation",
    "phone",
]


def _safe_cell(value: str) -> str:
    s = str(value).strip()
    if s and s[0] in "+=-@":
        return "'" + s
    return s


class YandexDiskCsv:
    def __init__(self, oauth_token: str, remote_path: str):
        self.token = oauth_token
        self.remote_path = remote_path
        self.base = "https://cloud-api.yandex.net/v1/disk"
        self._headers = {"Authorization": f"OAuth {oauth_token}"}

    async def _download(self, client: httpx.AsyncClient) -> bytes | None:
        r = await client.get(
            f"{self.base}/resources/download",
            headers=self._headers,
            params={"path": self.remote_path},
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        href = r.json().get("href")
        if not href:
            return None
        r2 = await client.get(href)
        if r2.status_code != 200:
            return None
        return r2.content

    async def _upload(self, client: httpx.AsyncClient, body: bytes) -> None:
        r = await client.get(
            f"{self.base}/resources/upload",
            headers=self._headers,
            params={"path": self.remote_path, "overwrite": "true"},
        )
        r.raise_for_status()
        href = r.json()["href"]
        up = await client.put(href, content=body)
        if up.status_code not in (200, 201, 202):
            raise RuntimeError(f"Upload {up.status_code}: {up.text[:200]}")

    async def append_row(self, data: dict[str, Any]) -> None:
        line = [_safe_cell(str(data.get(k, ""))) for k in ROW_KEYS]
        async with httpx.AsyncClient(timeout=90.0, trust_env=True) as client:
            raw = await self._download(client)
            rows = []
            if raw:
                rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", errors="replace"))))
            if not rows:
                out = [HEADERS_RU, line]
            elif rows[0] and rows[0][0] == HEADERS_RU[0]:
                out = rows + [line]
            else:
                out = [HEADERS_RU] + rows + [line]
            buf = io.StringIO()
            w = csv.writer(buf)
            for row in out:
                w.writerow(row)
            await self._upload(client, buf.getvalue().encode("utf-8-sig"))
        logger.info("Yandex Disk CSV updated: %s", self.remote_path)


async def save_result_disk(token: str, path: str, data: dict[str, Any]) -> bool:
    if not token:
        logger.warning("YANDEX_DISK_TOKEN не задан — пропуск записи на Диск")
        return False
    try:
        await YandexDiskCsv(token, path).append_row(data)
        return True
    except Exception as e:
        logger.exception("Yandex Disk: %s", e)
        return False

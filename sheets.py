"""
Запись строки в Google Таблицу (gspread + сервисный аккаунт).
Порядок столбцов совместим с прежним CSV / Яндекс-вариантом.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import gspread

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


def _append_sync(credentials_path: str, spreadsheet_id: str, worksheet_title: str | None, data: dict[str, Any]) -> None:
    path = Path(credentials_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Нет файла ключей: {path}")

    gc = gspread.service_account(filename=str(path))
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_title) if worksheet_title else sh.sheet1

    values = [str(data.get(k, "")) for k in ROW_KEYS]
    rows = ws.get_all_values()
    if not rows:
        ws.append_row(HEADERS_RU, value_input_option="USER_ENTERED")
    ws.append_row(values, value_input_option="USER_ENTERED")


async def save_result_sheets(
    credentials_path: str,
    spreadsheet_id: str,
    worksheet_title: str | None,
    data: dict[str, Any],
) -> bool:
    if not spreadsheet_id:
        logger.warning("GOOGLE_SPREADSHEET_ID не задан — пропуск записи в Google Таблицу")
        return False
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: _append_sync(credentials_path, spreadsheet_id, worksheet_title, data),
        )
        logger.info("Google Sheets: строка добавлена в %s", spreadsheet_id)
        return True
    except Exception as e:
        logger.exception("Google Sheets: %s", e)
        return False

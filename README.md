# Профориентация — VK + Google Таблицы + Ollama

Бот для **ВКонтакте** (сообщество): анкета, рекомендации через **Ollama Cloud**, сохранение строк в **Google Таблицу** ([gspread](https://github.com/burnash/gspread) + сервисный аккаунт).

---

## Документация для начинающих

**[INSTALLATION_RU.md](INSTALLATION_RU.md)** — установка на Windows, VK, Ollama, Google Sheets, запуск локально и подробно **Pterodactyl** (переменные яйца, startup command).

---

## Быстрый старт

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# положи credentials.json (ключ сервисного аккаунта Google) в корень проекта
# заполни .env (см. INSTALLATION_RU.md)
python main.py
```

**Pterodactyl:** образ **Python 3.11**, **App py file** — `app.py`, **Requirements file** — `requirements.txt`, **Git Repo** — например `https://github.com/ProBRo141/career_bot_pterodactyl.git`. В корень сервера загрузи **`credentials.json`** и создай **`.env`**. Подробности — в [INSTALLATION_RU.md](INSTALLATION_RU.md#шаг-7-pterodactyl-панель-яйцо-python).

---

## Репозитории

- Основной (пример для Pterodactyl): [github.com/ProBRo141/career_bot_pterodactyl](https://github.com/ProBRo141/career_bot_pterodactyl)
- Зеркало/копия: [github.com/ProBRo141/botvkprof](https://github.com/ProBRo141/botvkprof)

---

## Переменные окружения

См. [INSTALLATION_RU.md](INSTALLATION_RU.md#переменные-env-шпаргалка) и `.env.example`.

---

## Стек

- [vkbottle](https://github.com/vkbottle/vkbottle) — Long Poll, кнопки
- `httpx` — Ollama
- `gspread` — Google Sheets

Локально на сервере: `vk_fsm_state.json`, `results.json` (в `.gitignore`).

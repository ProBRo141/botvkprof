# Профориентация — VK + Яндекс Таблицы (через Диск) + Ollama

Бот для **ВКонтакте** (сообщество): анкета, рекомендации через **Ollama Cloud**, сохранение ответов в **CSV на Яндекс Диске** (файл открывается в **Яндекс Таблицах**).

> У Яндекс Таблиц нет публичного REST API для ячеек; используется [API Яндекс Диска](https://yandex.ru/dev/disk/rest/) — бот дописывает строки в CSV.

---

## Документация для начинающих

**[INSTALLATION_RU.md](INSTALLATION_RU.md)** — пошаговая установка на Windows, настройка VK, Ollama, Яндекс Диска, запуск локально и на **Pterodactyl**.

---

## Быстрый старт

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# заполни .env (см. INSTALLATION_RU.md)
python main.py
```

На хостинге Pterodactyl: **App py file** — `app.py`, **Requirements** — `requirements.txt`, в корне сервера — файл `.env`.

---

## Репозиторий

https://github.com/ProBRo141/botvkprof

---

## Переменные окружения

См. таблицу в [INSTALLATION_RU.md](INSTALLATION_RU.md#переменные-env-шпаргалка) и файл `.env.example`.

---

## Стек

- [vkbottle](https://github.com/vkbottle/vkbottle) — Long Poll, кнопки
- `httpx` — Ollama и Яндекс Диск
- Логика анкеты: `questions.py`, `validation.py`, `llm_service.py`

Локальные файлы состояния: `vk_fsm_state.json`, `results.json` (в `.gitignore`).

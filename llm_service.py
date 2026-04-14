import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты профориентационный аналитик. Анализируешь ответы анкеты и выдаёшь результат СТРОГО в JSON.

Правила:
1. Рекомендуй КОНКРЕТНЫЕ профессии (не "IT", а "Backend-разработчик Python", "UX-дизайнер", "Аналитик данных").
2. Опирайся на ответы, но ДОПОЛНИ своими вариантами — предложи 1–2 смежных направления, которые человек мог не назвать.
3. Учитывай ОПЫТ человека — если есть опыт в продажах, укажи это в причинах; если опыта нет — предложи входные роли.
4. Группируй профессии по сферам: IT/данные, творчество, управление, работа с людьми и т.д.
5. К каждой профессии добавь 1–2 ссылки на обучение (С stepik.org, Нетология, Skillbox, Hexlet, Яндекс Практикум, Coursera, hh.ru/education и т.п.). Ссылки должны быть реальными.
6. Рекомендации — персональные, без шаблонов.

Формат ответа — только валидный JSON, без markdown и пояснений:
{
  "top_directions": ["конкретная профессия1", "конкретная профессия2", "конкретная профессия3", "конкретная профессия4", "конкретная профессия5"],
  "categories": {
    "IT и данные": ["профессия1", "профессия2"],
    "Творчество": ["профессия3"],
    ...
  },
  "reasons": {
    "профессия1": ["причина с учётом опыта и интересов", "причина2", "причина3"],
    ...
  },
  "risks": {
    "профессия1": ["риск1", "риск2"],
    ...
  },
  "first_step_24h": {
    "профессия1": "конкретный шаг",
    ...
  },
  "learning_links": {
    "профессия1": ["https://stepik.org/...", "https://..."],
    "профессия2": ["https://...", "https://..."],
    ...
  },
  "plan_14_days": [
    {"day": 1, "task": "описание задачи", "check_result": "как проверить"},
    {"day": 2, "task": "...", "check_result": "..."},
    ...
  ]
}
План: 14 задач по 20–60 мин. Задачи конкретные и проверяемые."""


LABELS = {
    "age": "Возраст",
    "city": "Город",
    "education": "Образование",
    "hours": "Часов в неделю",
    "interests": "Интересы",
    "dislikes": "Что не нравится",
    "work_format": "Формат работы",
    "skills": "Навыки",
    "experience": "Опыт",
    "communication": "Коммуникация",
    "goal": "Цель на 3 мес",
    "limits": "Ограничения",
    "priority": "Приоритет",
}


def build_context(answers: dict, value_labels: dict = None) -> str:
    parts = []
    for k, v in answers.items():
        if v:
            key_label = LABELS.get(k, k)
            if isinstance(v, str) and value_labels and k in value_labels:
                labels = value_labels[k]
                if "," in v:
                    v = ", ".join(labels.get(p.strip(), p.strip()) for p in v.split(","))
                else:
                    v = labels.get(v, v)
            parts.append(f"{key_label}: {v}")
    return "\n".join(parts)


def parse_llm_response(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        filtered = []
        for line in lines:
            if line.strip() in ("```json", "```"):
                continue
            filtered.append(line)
        text = "\n".join(filtered)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _call_ollama(base_url: str, model: str, system: str, user_msg: str, api_key: str = None) -> dict | None:
    import httpx

    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 4000},
    }
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with httpx.Client(timeout=120.0, trust_env=True) as client:
            resp = client.post(url, json=payload, headers=headers or None)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return parse_llm_response(content)
    except Exception as e:
        logger.exception("Ollama error: %s", e)
        return None


def get_recommendations(
    answers: dict,
    value_labels: dict = None,
    ollama_base_url: str = None,
    ollama_model: str = None,
    ollama_api_key: str = None,
) -> dict | None:
    import time

    base_url = (ollama_base_url or "https://ollama.com").rstrip("/")
    model = ollama_model or "gpt-oss:20b"
    ctx = build_context(answers, value_labels)
    user_msg = f"Ответы анкеты:\n{ctx}\n\nСформируй персональные рекомендации в JSON. Не забудь про опыт, категории и ссылки на обучение."
    for attempt in range(3):
        result = _call_ollama(base_url, model, SYSTEM_PROMPT, user_msg, ollama_api_key)
        if result:
            return result
        if attempt < 2:
            time.sleep(2 + attempt * 2)
    return None

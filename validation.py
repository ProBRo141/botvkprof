MIN_LENGTH = 10
CLARIFY_TEMPLATES = {
    "age": "Формат: 25",
    "city": "Напиши название города",
    "interests": "Формат: программирование, психология, маркетинг",
    "dislikes": "Формат: бухгалтерия, холодные звонки, рутина",
    "skills": "Формат: Python, Excel, презентации, работа в команде, аналитика",
    "experience": "Формат: продажи в магазине, вожатый в лагере, курсовой проект",
    "limits": "Формат: мало времени, нужен доход, помогаю семье",
    "work_format": "Формат: 5 1 4 3 2 (5 — важнее всего, повторы можно)",
}


def is_too_short(key: str, text: str) -> bool:
    if key in ("age", "education", "hours", "communication", "goal", "priority"):
        return False
    if key == "city":
        return len(text.strip()) < 3
    return len(text.strip()) < MIN_LENGTH


def validate_work_format(text: str) -> bool:
    import re
    nums = [int(m) for m in re.findall(r"\b([1-5])\b", text)]
    # 5 чисел от 1 до 5, повторы разрешены (можно поставить 1 двум категориям)
    return len(nums) == 5 and all(1 <= n <= 5 for n in nums)


def normalize_work_format(text: str) -> str:
    import re
    nums = [int(m) for m in re.findall(r"\b([1-5])\b", text)]
    if len(nums) != 5 or not all(1 <= n <= 5 for n in nums):
        return text
    order = ["люди", "данные", "техника", "творчество", "управление"]
    inverted = [6 - n for n in nums]
    return " ".join(f"{k}:{n}" for k, n in zip(order, inverted))


def get_clarify_message(key: str) -> str | None:
    return CLARIFY_TEMPLATES.get(key)

"""Клавиатуры VK (vkbottle). Вопросы и варианты — из questions.py."""

from vkbottle.tools import Callback, Keyboard, KeyboardButtonColor, Text

from questions import COMMUNICATION, EDUCATION, GOAL_3M, HOURS, PRIORITY


def _go(step: str) -> dict:
    """Вернуться к шагу step (имя из QUESTION_ORDER / priority / consultation / phone)."""
    return {"t": "b", "g": step}


def _ans(step: str, val: str) -> dict:
    return {"t": "a", "s": step, "v": val}


def main_menu_kb() -> Keyboard:
    kb = Keyboard(one_time=False, inline=False)
    kb.add(Text("🚀 Старт"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("🔄 Перезапуск"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("❓ Помощь"))
    kb.add(Text("📋 Мой результат"))
    kb.row()
    kb.add(Text("⬇ Скрыть меню"))
    return kb


def empty_keyboard() -> Keyboard:
    return Keyboard()


def education_kb(step: str) -> Keyboard:
    kb = Keyboard(inline=True)
    for val, txt in EDUCATION:
        kb.add(Callback(txt, payload=_ans(step, val)))
        kb.row()
    kb.add(Callback("← Назад", payload=_go("city")))
    return kb


def hours_kb(step: str) -> Keyboard:
    kb = Keyboard(inline=True)
    for val, txt in HOURS:
        kb.add(Callback(txt, payload=_ans(step, val)))
        kb.row()
    kb.add(Callback("← Назад", payload=_go("education")))
    return kb


def communication_kb(step: str) -> Keyboard:
    kb = Keyboard(inline=True)
    for val, txt in COMMUNICATION:
        kb.add(Callback(txt, payload=_ans(step, val)))
        kb.row()
    kb.add(Callback("← Назад", payload=_go("experience")))
    return kb


def goal_kb(step: str) -> Keyboard:
    kb = Keyboard(inline=True)
    for val, txt in GOAL_3M:
        kb.add(Callback(txt, payload=_ans(step, val)))
        kb.row()
    kb.add(Callback("← Назад", payload=_go("communication")))
    return kb


def _prio(val: str) -> dict:
    """Отдельный payload от _ans: иначе t:a на шаге priority считается «последний вопрос» и сразу запускает LLM."""
    return {"t": "p", "v": val}


def priority_kb(step: str) -> Keyboard:
    kb = Keyboard(inline=True)
    for val, txt in PRIORITY:
        kb.add(Callback(txt, payload=_prio(val)))
        kb.row()
    kb.add(Callback("← Назад", payload=_go("limits")))
    return kb


def priority_with_done_kb(step: str) -> Keyboard:
    kb = Keyboard(inline=True)
    for val, txt in PRIORITY:
        kb.add(Callback(txt, payload=_prio(val)))
        kb.row()
    kb.add(Callback("Готово", payload={"t": "pd"}))
    kb.add(Callback("← Назад", payload=_go("limits")))
    return kb


def consultation_kb() -> Keyboard:
    kb = Keyboard(inline=True)
    kb.add(Callback("Да", payload={"t": "cy"}))
    kb.row()
    kb.add(Callback("Нет", payload={"t": "cn"}))
    kb.row()
    kb.add(Callback("← Назад", payload=_go("priority")))
    return kb


def phone_back_kb() -> Keyboard:
    kb = Keyboard(inline=True)
    kb.add(Callback("← Назад", payload=_go("consultation")))
    return kb


def text_step_back_kb(prev_step: str) -> Keyboard:
    kb = Keyboard(inline=True)
    kb.add(Callback("← Назад", payload=_go(prev_step)))
    return kb


def label_map():
    return {
        "education": dict(EDUCATION),
        "hours": dict(HOURS),
        "communication": dict(COMMUNICATION),
        "goal": dict(GOAL_3M),
        "priority": dict(PRIORITY),
    }

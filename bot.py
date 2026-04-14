"""
VK-версия профориентационного бота (логика перенесена с Telegram / aiogram).
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime

from vkbottle import GroupEventType
from vkbottle.bot import Bot, Message, MessageEvent

from config import (
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_SHEET_WORKSHEET,
    GOOGLE_SPREADSHEET_ID,
    OLLAMA_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    VK_GROUP_TOKEN,
)
from keyboards_vk import (
    communication_kb,
    consultation_kb,
    education_kb,
    empty_keyboard,
    goal_kb,
    hours_kb,
    main_menu_kb,
    phone_back_kb,
    priority_kb,
    priority_with_done_kb,
    text_step_back_kb,
)
from keyboards_vk import label_map
from llm_service import get_recommendations
from questions import QUESTIONS, QUESTION_ORDER
from results_store import get_last_result, save_result as save_to_store
from storage import JsonStorage
from validation import get_clarify_message, is_too_short, normalize_work_format, validate_work_format
from sheets import save_result_sheets

_log_path = "/home/container/bot.log" if os.path.exists("/home/container") else "bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_log_path, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

st = JsonStorage()


def _is_outgoing(message: Message) -> bool:
    """Сообщения, отправленные от имени сообщества (ответы бота), не обрабатываем — иначе путаница и лишние ответы."""
    o = getattr(message, "out", 0)
    return bool(o) if isinstance(o, int) else bool(o)


def _storage_user_id(message: Message) -> int:
    """
    ID пользователя для FSM и results_store.
    В личке «пользователь → сообщество» обычно from_id > 0; если VK отдаёт иначе — берём положительный peer_id.
    """
    fid = int(message.from_id or 0)
    if fid > 0:
        return fid
    pid = int(message.peer_id or 0)
    # ЛС (не беседа 2e9+): peer_id совпадает с id собеседника-пользователя
    if 0 < pid < 2_000_000_000:
        return pid
    return fid or pid


def _log_incoming(message: Message, where: str) -> None:
    try:
        logger.info(
            "incoming[%s] peer=%s from=%s out=%s text=%r",
            where,
            message.peer_id,
            message.from_id,
            getattr(message, "out", None),
            (message.text or "")[:120],
        )
    except Exception:
        pass


def _callback_user_id(event: MessageEvent) -> int:
    uid = int(getattr(event, "user_id", None) or 0)
    if uid > 0:
        return uid
    obj = getattr(event, "object", None)
    if isinstance(obj, dict):
        return int(obj.get("user_id") or 0)
    if obj is not None:
        v = getattr(obj, "user_id", None)
        if v is not None:
            return int(v)
    return 0

KEYBOARD_MAP = {
    "education": education_kb,
    "hours": hours_kb,
    "communication": communication_kb,
    "goal": goal_kb,
    "priority": priority_kb,
}

# vkbottle 4.8+: только token; group_id в конструкторе Bot больше не передаётся
bot = Bot(token=VK_GROUP_TOKEN or "")


def _parse_payload(event: MessageEvent) -> dict:
    p = getattr(event, "payload", None)
    if isinstance(p, str):
        try:
            return json.loads(p)
        except json.JSONDecodeError:
            return {}
    return p if isinstance(p, dict) else {}


def data_after_back(data: dict, target_step: str) -> dict:
    """Данные после «Назад» к шагу target_step (ответы этого шага сбрасываются — ввод заново)."""
    meta = {k: v for k, v in data.items() if str(k).startswith("_")}
    if target_step == "consultation":
        out = {k: data[k] for k in QUESTION_ORDER if k in data}
        if "priority" in data:
            out["priority"] = data["priority"]
        out.pop("phone", None)
        out.pop("consultation_ready", None)
        out.update(meta)
        return out
    if target_step == "priority":
        out = {k: data[k] for k in QUESTION_ORDER if k in data}
        out.pop("consultation_ready", None)
        out.pop("phone", None)
        out.update(meta)
        return out
    try:
        idx = QUESTION_ORDER.index(target_step)
        out = {k: data[k] for k in QUESTION_ORDER[:idx] if k in data}
        out.update(meta)
        return out
    except ValueError:
        return dict(meta)


def format_result(rec: dict, answers: dict) -> str:
    labels = label_map()
    top = rec.get("top_directions", [])[:5]
    categories = rec.get("categories", {})
    reasons = rec.get("reasons", {})
    risks = rec.get("risks", {})
    first = rec.get("first_step_24h", {})
    links = rec.get("learning_links", {})
    plan = rec.get("plan_14_days", [])

    def strip_md(s: str) -> str:
        return (s or "").replace("*", "")

    parts = [strip_md("*РЕКОМЕНДАЦИИ*\n")]
    if categories and isinstance(categories, dict):
        for cat, profs in categories.items():
            if isinstance(profs, list):
                parts.append(strip_md(f"*{cat}*"))
                for p in profs[:3]:
                    parts.append(f"  • {strip_md(str(p))}")
                parts.append("")
    for i, d in enumerate(top, 1):
        parts.append(strip_md(f"*{i}. {d}*"))
        for r in reasons.get(d, [])[:3]:
            parts.append(f"  • {strip_md(str(r))}")
        for r in risks.get(d, [])[:2]:
            parts.append(f"  ⚠ {strip_md(str(r))}")
        fs = first.get(d, "")
        if fs:
            parts.append(f"  Первый шаг за 24ч: {strip_md(str(fs))}")
        ll = links.get(d, [])
        if ll:
            parts.append("  Обучение:")
            for url in ll[:3]:
                parts.append(f"    {url}")
        parts.append("")

    parts.append(strip_md("*ПЛАН НА 14 ДНЕЙ*\n"))
    for p in plan[:14]:
        day = p.get("day", "?")
        task = p.get("task", "")
        check = p.get("check_result", "")
        parts.append(f"День {day}: {task}")
        if check:
            parts.append(f"  Проверка: {check}")
        parts.append("")

    return "\n".join(parts)


async def send_long_message(api, peer_id: int, text: str, keyboard=None):
    MAX_LEN = 3800
    chunk = text or ""
    first = True
    while chunk:
        part = chunk[:MAX_LEN] if len(chunk) > MAX_LEN else chunk
        if len(chunk) > MAX_LEN:
            cut = chunk.rfind("\n", 0, MAX_LEN + 1)
            if cut > 0:
                part, chunk = chunk[:cut].strip(), chunk[cut:].strip()
            else:
                part, chunk = chunk[:MAX_LEN], chunk[MAX_LEN:]
        else:
            chunk = ""
        if not part.strip():
            continue
        kw = dict(peer_id=peer_id, random_id=0, message=part)
        if first and keyboard is not None:
            kw["keyboard"] = keyboard
            first = False
        await api.messages.send(**kw)


async def ask_question(api, peer_id: int, user_id: int, step: str):
    text, key, has_kb = QUESTIONS[step]
    st.set_state(user_id, step)
    u = st.get_user(user_id)
    data = u.get("data", {})
    if has_kb:
        if step == "priority":
            kb = priority_with_done_kb(key)
        else:
            kb = KEYBOARD_MAP[step](key)
    else:
        try:
            idx = QUESTION_ORDER.index(step)
            prev = QUESTION_ORDER[idx - 1] if idx > 0 else None
        except ValueError:
            prev = None
        kb = text_step_back_kb(prev) if prev else main_menu_kb()
    await api.messages.send(peer_id=peer_id, random_id=0, message=text, keyboard=kb)


async def _vk_profile_link(api, user_id: int) -> str:
    try:
        users = await api.users.get(user_ids=[user_id])
        if users:
            u = users[0]
            un = getattr(u, "domain", None) or ""
            if un:
                return f"vk.com/{un}"
    except Exception:
        pass
    return f"vk.com/id{user_id}"


async def send_result_and_save_impl(api, peer_id: int, user_id: int, data: dict, rec: dict):
    answers = {k: v for k, v in data.items() if k in QUESTION_ORDER}
    labs = label_map()
    display = {}
    for k, v in answers.items():
        if k in labs and isinstance(v, str):
            if "," in v:
                parts = [labs[k].get(p.strip(), p.strip()) for p in v.split(",")]
                display[k] = ", ".join(parts)
            else:
                display[k] = labs[k].get(v, v)
        else:
            display[k] = v
    if data.get("priority"):
        pv = data["priority"]
        pl = labs.get("priority", {})
        if "," in str(pv):
            display["priority"] = ", ".join(
                pl.get(p.strip(), p.strip()) for p in str(pv).split(",") if p.strip()
            )
        else:
            display["priority"] = pl.get(str(pv), pv)

    reasons = rec.get("reasons", {})
    risks = rec.get("risks", {})
    first = rec.get("first_step_24h", {})
    top_lines = []
    for i, d in enumerate(rec.get("top_directions", [])[:5], 1):
        r = "; ".join(reasons.get(d, [])[:3])
        k = "; ".join(risks.get(d, [])[:2])
        fs = first.get(d, "")
        line = f"{i}. {d}"
        if r:
            line += f"\n   Причины: {r}"
        if k:
            line += f"\n   Риски: {k}"
        if fs:
            line += f"\n   Шаг 24ч: {fs}"
        top_lines.append(line)
    top_str = "\n\n".join(top_lines)

    plan_parts = []
    for p in rec.get("plan_14_days", [])[:14]:
        day = p.get("day", "?")
        task = p.get("task", "")
        check = p.get("check_result", "")
        s = f"День {day}: {task}"
        if check:
            s += f"\n   ✓ {check}"
        plan_parts.append(s)
    plan_str = "\n\n".join(plan_parts)

    ts = datetime.utcnow()
    ts_str = ts.strftime("%d.%m.%Y %H:%M")
    consultation = data.get("consultation_ready", "")
    vk_link = await _vk_profile_link(api, user_id)
    row = {
        "timestamp": ts_str,
        "vk_profile": vk_link,
        "vk_id": str(user_id),
        "age": str(display.get("age", "")),
        "city": str(display.get("city", "")),
        "education": str(display.get("education", "")),
        "hours": str(display.get("hours", "")),
        "interests": str(display.get("interests", "")),
        "dislikes": str(display.get("dislikes", "")),
        "work_format": str(display.get("work_format", "")),
        "skills": str(display.get("skills", "")),
        "experience": str(display.get("experience", "")),
        "communication": str(display.get("communication", "")),
        "goal": str(display.get("goal", "")),
        "limits": str(display.get("limits", "")),
        "priority": str(display.get("priority", "")),
        "top_directions": top_str,
        "plan_14_days": plan_str,
        "ready_for_consultation": "да" if consultation == "yes" else "нет",
        "phone": data.get("phone", ""),
    }
    if GOOGLE_SPREADSHEET_ID:
        try:
            await save_result_sheets(
                str(GOOGLE_CREDENTIALS_PATH),
                GOOGLE_SPREADSHEET_ID,
                GOOGLE_SHEET_WORKSHEET,
                row,
            )
        except Exception as e:
            logger.error("Google Sheets save: %s", e)
    save_to_store(
        user_id,
        {
            "answers": display,
            "recommendations": rec,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
    st.set_state(user_id, "done")
    out = format_result(rec, answers)
    try:
        await send_long_message(api, peer_id, out, main_menu_kb())
    except Exception as e:
        logger.exception("Send result: %s", e)
        await api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message="Результат сохранён. Напиши «Мой результат».",
            keyboard=main_menu_kb(),
        )


async def _do_generate(api, peer_id: int, user_id: int):
    await api.messages.send(peer_id=peer_id, random_id=0, message="Генерирую рекомендации...")
    u = st.get_user(user_id)
    data = u.get("data", {})
    rec = get_recommendations(data, label_map(), OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_API_KEY)
    if rec:
        await send_result_and_save_impl(api, peer_id, user_id, data, rec)
    else:
        await api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message="Сервис временно недоступен. Попробуй «Перезапуск» через минуту. "
            "Проверь OLLAMA_API_KEY на ollama.com/settings/keys",
            keyboard=main_menu_kb(),
        )


@bot.on.message(text=["Старт", "старт", "/start", "Начать", "начать", "🚀 Старт"])
async def cmd_start(message: Message):
    if _is_outgoing(message):
        return
    _log_incoming(message, "start")
    uid = _storage_user_id(message)
    if not uid:
        logger.warning("cmd_start: uid=0 peer=%s from=%s", message.peer_id, message.from_id)
        await message.answer(
            "Не получилось определить твой id ВК. Напиши в этот диалог с личной страницы (не из-под другого сообщества).",
            keyboard=main_menu_kb(),
        )
        return
    st.clear_data(uid)
    await message.answer(
        "Привет! Я помогу с профориентацией. Пройди анкету — получишь рекомендации и план на 14 дней.\n\n"
        "Команды в сообщениях: /restart — заново, /help — помощь, /myresult — последний результат.",
        keyboard=main_menu_kb(),
    )
    await ask_question(message.ctx_api, message.peer_id, uid, "age")


@bot.on.message(text=["Перезапуск", "перезапуск", "/restart", "🔄 Перезапуск"])
async def cmd_restart(message: Message):
    if _is_outgoing(message):
        return
    await cmd_start(message)


@bot.on.message(text=["Помощь", "помощь", "/help", "❓ Помощь"])
async def cmd_help(message: Message):
    if _is_outgoing(message):
        return
    _log_incoming(message, "help")
    await message.answer(
        "Бот проводит профориентационную диагностику.\n"
        "Отвечай на вопросы — в конце получишь направления, причины, риски, первый шаг и план на 14 дней.\n"
        "Есть кнопка «Назад».\n\n"
        "Кнопки внизу: Старт, Перезапуск, Мой результат.",
        keyboard=main_menu_kb(),
    )


@bot.on.message(text=["Мой результат", "мой результат", "/myresult", "📋 Мой результат"])
async def cmd_myresult(message: Message):
    if _is_outgoing(message):
        return
    _log_incoming(message, "myresult")
    uid = _storage_user_id(message)
    if not uid:
        await message.answer("Не удалось определить профиль.", keyboard=main_menu_kb())
        return
    res = get_last_result(uid)
    if not res:
        await message.answer("Результатов пока нет. Нажми «Старт».", keyboard=main_menu_kb())
        return
    rec = res.get("recommendations", {})
    answers = res.get("answers", {})
    out = format_result(rec, answers)
    await send_long_message(message.ctx_api, message.peer_id, out, main_menu_kb())


@bot.on.message(text=["⬇ Скрыть меню", "Скрыть меню"])
async def cmd_hide(message: Message):
    if _is_outgoing(message):
        return
    _log_incoming(message, "hide")
    await message.answer("Меню скрыто. Напиши «Старт».", keyboard=empty_keyboard())


@bot.on.message()
async def on_text(message: Message):
    if _is_outgoing(message):
        return
    _log_incoming(message, "text")
    uid = _storage_user_id(message)
    if not uid:
        logger.warning("on_text: uid=0 peer=%s from=%s", message.peer_id, message.from_id)
        await message.answer(
            "Не получилось определить твой id ВК. Открой диалог с сообществом с личной страницы ВК.",
            keyboard=main_menu_kb(),
        )
        return
    raw = message.text
    if not raw or not str(raw).strip():
        await message.answer(
            "Я понимаю текст и кнопки под полем ввода. Напиши сообщение текстом или нажми «Старт» на клавиатуре.",
            keyboard=main_menu_kb(),
        )
        return
    text = str(raw).strip()
    tl = text.lower()
    # Те же команды без учёта регистра (если не сработал точный text= у других хендлеров)
    if tl in ("старт", "начать", "/start"):
        await cmd_start(message)
        return
    if tl in ("перезапуск", "/restart"):
        await cmd_start(message)
        return
    if tl in ("помощь", "/help"):
        await cmd_help(message)
        return
    if tl in ("мой результат", "/myresult"):
        await cmd_myresult(message)
        return
    if text.startswith("/"):
        if text not in ("/start", "/restart", "/help", "/myresult"):
            await message.answer("Используй кнопки или /help", keyboard=main_menu_kb())
        return
    if text in (
        "Старт",
        "старт",
        "Перезапуск",
        "перезапуск",
        "Помощь",
        "помощь",
        "Мой результат",
        "мой результат",
        "🚀 Старт",
        "🔄 Перезапуск",
        "❓ Помощь",
        "📋 Мой результат",
        "⬇ Скрыть меню",
        "Скрыть меню",
    ):
        return
    u = st.get_user(uid)
    step = u.get("state")
    if not step:
        await message.answer(
            "Чтобы начать анкету, нажми кнопку «Старт» внизу экрана или напиши слово «Старт». "
            "Если кнопок нет — открой клавиатуру: значок ⋮ у поля ввода → «Открыть клавиатуру».",
            keyboard=main_menu_kb(),
        )
        return
    if step == "done":
        await message.answer("Анкета завершена. «Перезапуск» — заново.", keyboard=main_menu_kb())
        return
    if step == "consultation_ready":
        await message.answer("Выбери «Да» или «Нет» кнопкой.", keyboard=consultation_kb())
        return
    if step == "phone":
        digits = re.sub(r"\D", "", text)
        if len(digits) < 10:
            await message.answer(
                "Укажи корректный номер (минимум 10 цифр). Пример: +7 999 123-45-67",
                keyboard=phone_back_kb(),
            )
            return
        st.update_data(uid, phone=text)
        await _do_generate(message.ctx_api, message.peer_id, uid)
        return
    if step == "education":
        await message.answer("Выбери вариант кнопкой.", keyboard=education_kb("education"))
        return
    if step == "hours":
        await message.answer("Выбери вариант кнопкой.", keyboard=hours_kb("hours"))
        return
    if step == "communication":
        await message.answer("Выбери вариант кнопкой.", keyboard=communication_kb("communication"))
        return
    if step == "goal":
        await message.answer("Выбери вариант кнопкой.", keyboard=goal_kb("goal"))
        return
    if step == "priority":
        await message.answer("Выбери кнопками.", keyboard=priority_with_done_kb("priority"))
        return
    if step == "age":
        t = text
        if not t.isdigit() or int(t) < 10 or int(t) > 100:
            await message.answer("Формат: 25")
            return
        st.update_data(uid, age=t)
        await ask_question(message.ctx_api, message.peer_id, uid, "city")
        return
    if step == "city":
        if is_too_short("city", text):
            await message.answer(get_clarify_message("city") or "Напиши город")
            return
        st.update_data(uid, city=text)
        await ask_question(message.ctx_api, message.peer_id, uid, "education")
        return
    if step == "interests":
        if is_too_short("interests", text):
            await message.answer(get_clarify_message("interests") or "")
            return
        st.update_data(uid, interests=text)
        await ask_question(message.ctx_api, message.peer_id, uid, "dislikes")
        return
    if step == "dislikes":
        if is_too_short("dislikes", text):
            await message.answer(get_clarify_message("dislikes") or "")
            return
        st.update_data(uid, dislikes=text)
        await ask_question(message.ctx_api, message.peer_id, uid, "work_format")
        return
    if step == "work_format":
        if not validate_work_format(text):
            await message.answer(get_clarify_message("work_format") or "")
            return
        st.update_data(uid, work_format=normalize_work_format(text))
        await ask_question(message.ctx_api, message.peer_id, uid, "skills")
        return
    if step == "skills":
        if is_too_short("skills", text):
            await message.answer(get_clarify_message("skills") or "")
            return
        st.update_data(uid, skills=text)
        await ask_question(message.ctx_api, message.peer_id, uid, "experience")
        return
    if step == "experience":
        if is_too_short("experience", text):
            await message.answer(get_clarify_message("experience") or "")
            return
        st.update_data(uid, experience=text)
        await ask_question(message.ctx_api, message.peer_id, uid, "communication")
        return
    if step == "limits":
        if is_too_short("limits", text):
            await message.answer(get_clarify_message("limits") or "")
            return
        st.update_data(uid, limits=text, priority="", consultation_ready="", phone="")
        await ask_question(message.ctx_api, message.peer_id, uid, "priority")
        return


@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=MessageEvent)
async def on_callback(event: MessageEvent):
    pl = _parse_payload(event)
    t = pl.get("t")
    api = event.ctx_api
    peer = event.peer_id
    uid = _callback_user_id(event)
    if not uid:
        logger.warning("callback: uid=0 peer=%s payload=%s", peer, _parse_payload(event))
        try:
            await event.show_snackbar("Ошибка: не определён пользователь")
        except Exception:
            pass
        return

    async def snack(x: str):
        try:
            await event.show_snackbar(x)
        except Exception:
            pass

    if t == "a":
        step, val = pl.get("s"), pl.get("v")
        if not step or val is None:
            await snack("Ошибка")
            return
        st.update_data(uid, **{str(step): str(val)})
        try:
            idx = QUESTION_ORDER.index(str(step))
        except ValueError:
            await snack("?")
            return
        if idx + 1 >= len(QUESTION_ORDER):
            await api.messages.send(peer_id=peer, random_id=0, message="Генерирую рекомендации...")
            u = st.get_user(uid)
            data = u.get("data", {})
            rec = get_recommendations(data, label_map(), OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_API_KEY)
            if rec:
                await send_result_and_save_impl(api, peer, uid, data, rec)
            else:
                await api.messages.send(
                    peer_id=peer,
                    random_id=0,
                    message="Сервис временно недоступен. Попробуй «Перезапуск».",
                    keyboard=main_menu_kb(),
                )
            await snack("Готово")
            return
        nxt = QUESTION_ORDER[idx + 1]
        await ask_question(api, peer, uid, nxt)
        await snack("Сохранено")
        return

    if t == "p":
        val = pl.get("v")
        if not val:
            await snack("?")
            return
        u = st.get_user(uid)
        data = dict(u.get("data", {}))
        cur = data.get("priority", "")
        parts = [p.strip() for p in cur.split(",") if p.strip()] if cur else []
        if val in parts:
            parts.remove(val)
        else:
            parts.append(val)
        if len(parts) > 3:
            parts = parts[-3:]
        st.update_data(uid, priority=",".join(parts))
        data = st.get_user(uid).get("data", {})
        labs = label_map().get("priority", {})
        names = [labs.get(p, p) for p in parts]
        msg = f"Выбрано: {', '.join(names) or '—'}. Выбери 2–3 или нажми Готово."
        cmid = getattr(event, "conversation_message_id", None)
        if cmid is None and hasattr(event, "object"):
            o = event.object
            if isinstance(o, dict):
                cmid = o.get("conversation_message_id")
        try:
            if cmid:
                await api.messages.edit(
                    peer_id=peer,
                    conversation_message_id=cmid,
                    message=msg,
                    keyboard=priority_with_done_kb("priority"),
                )
            else:
                await api.messages.send(peer_id=peer, random_id=0, message=msg, keyboard=priority_with_done_kb("priority"))
        except Exception:
            await api.messages.send(peer_id=peer, random_id=0, message=msg, keyboard=priority_with_done_kb("priority"))
        await snack("Ок")
        return

    if t == "pd":
        u = st.get_user(uid)
        cur = u.get("data", {}).get("priority", "")
        parts = [p.strip() for p in cur.split(",") if p.strip()] if cur else []
        if len(parts) < 2:
            await snack("Выбери минимум 2 приоритета")
            return
        st.set_state(uid, "consultation_ready")
        await api.messages.send(
            peer_id=peer,
            random_id=0,
            message="Готов ли ты к консультации с специалистом?",
            keyboard=consultation_kb(),
        )
        await snack("Дальше")
        return

    if t == "cn":
        st.update_data(uid, consultation_ready="no")
        await _do_generate(api, peer, uid)
        await snack("Ок")
        return
    if t == "cy":
        st.update_data(uid, consultation_ready="yes")
        st.set_state(uid, "phone")
        await api.messages.send(
            peer_id=peer,
            random_id=0,
            message="Укажи номер телефона для связи:",
            keyboard=phone_back_kb(),
        )
        await snack("Ок")
        return

    if t == "b":
        target = pl.get("g")
        if not target:
            await snack("?")
            return
        u = st.get_user(uid)
        data = data_after_back(u.get("data", {}), str(target))
        if target == "consultation":
            st.set_user(uid, "consultation_ready", data)
            await api.messages.send(
                peer_id=peer,
                random_id=0,
                message="Готов ли ты к консультации с специалистом?",
                keyboard=consultation_kb(),
            )
        elif target == "priority":
            st.set_user(uid, "priority", data)
            cur = data.get("priority", "")
            labs = label_map().get("priority", {})
            names = [labs.get(p.strip(), p) for p in cur.split(",") if p.strip()]
            txt = (
                f"Выбрано: {', '.join(names) or '—'}. Выбери 2–3 или нажми Готово."
                if names
                else QUESTIONS["priority"][0]
            )
            await api.messages.send(peer_id=peer, random_id=0, message=txt, keyboard=priority_with_done_kb("priority"))
        else:
            st.set_user(uid, str(target), data)
            await ask_question(api, peer, uid, str(target))
        await snack("Назад")
        return

    await snack("?")


def main():
    if not VK_GROUP_TOKEN:
        logger.error("Задай VK_GROUP_TOKEN в .env")
        return
    if "ollama.com" in (OLLAMA_BASE_URL or "") and not OLLAMA_API_KEY:
        logger.error("Нужен OLLAMA_API_KEY для Ollama Cloud")
        return
    logger.info("VK bot, Ollama model=%s", OLLAMA_MODEL)
    bot.run_forever()


if __name__ == "__main__":
    main()

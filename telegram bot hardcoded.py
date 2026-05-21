"""
Telegram-бот «Мебель на заказ» — квиз + расчёт стоимости в 3 вариантах
Установка: pip install pyTelegramBotAPI
Запуск:    python telegram_bot.py
"""

import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─── НАСТРОЙКИ (берутся из переменных окружения Railway) ──────────────────────
BOT_TOKEN        = "8763681922:AAFR_L2AnOnXjlj_SIIloSxuCh2py3BZIl8"                        # обязательно
MANAGER_CHAT_ID  = "1378269466"         # необязательно
# ──────────────────────────────────────────────────────────────────────────────

bot = telebot.TeleBot(BOT_TOKEN)

# ─── ВОПРОСЫ КВИЗА ────────────────────────────────────────────────────────────
QUESTIONS = [
    {
        "text": "🛋 Какую мебель вы хотите заказать?",
        "options": [
            ("Кухня", "kitchen"),
            ("Шкаф / гардеробная", "wardrobe"),
            ("Прихожая", "hallway"),
            ("Спальня / кровать", "bedroom"),
            ("Детская комната", "kids"),
            ("Другое", "other"),
        ],
    },
    {
        "text": "📐 Какой размер (примерно)?",
        "options": [
            ("До 2 м", "small"),
            ("2–4 м", "medium"),
            ("Более 4 м", "large"),
        ],
    },
    {
        "text": "🪵 Какой материал предпочитаете?",
        "options": [
            ("ЛДСП (бюджет)", "ldsp"),
            ("МДФ + эмаль", "mdf"),
            ("Массив дерева", "wood"),
            ("Затрудняюсь ответить", "unknown"),
        ],
    },
    {
        "text": "✨ Нужна ли фурнитура премиум-класса (Blum, Hettich)?",
        "options": [
            ("Да, только качественная", "premium"),
            ("Стандартная подойдёт", "standard"),
            ("Не знаю, посоветуйте", "advice"),
        ],
    },
    {
        "text": "📅 Когда планируете сделать заказ?",
        "options": [
            ("Как можно скорее", "asap"),
            ("В течение месяца", "month"),
            ("Просто считаю бюджет", "planning"),
        ],
    },
]

# ─── КОЭФФИЦИЕНТЫ ДЛЯ РАСЧЁТА ─────────────────────────────────────────────────
BASE_PRICE = {
    "kitchen": 45000,
    "wardrobe": 25000,
    "hallway": 20000,
    "bedroom": 30000,
    "kids": 28000,
    "other": 20000,
}
SIZE_MULT = {"small": 1.0, "medium": 1.6, "large": 2.4}
MATERIAL_MULT = {"ldsp": 1.0, "mdf": 1.4, "wood": 2.0, "unknown": 1.2}
FITTINGS_ADD = {"premium": 15000, "standard": 0, "advice": 5000}

# ─── ХРАНИЛИЩЕ СЕССИЙ ─────────────────────────────────────────────────────────
sessions: dict[int, dict] = {}


def new_session():
    return {"step": 0, "answers": [], "name": None, "phone": None}


# ─── КЛАВИАТУРЫ ───────────────────────────────────────────────────────────────
def quiz_keyboard(step: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    for label, data in QUESTIONS[step]["options"]:
        kb.add(InlineKeyboardButton(label, callback_data=f"q_{step}_{data}"))
    return kb


def restart_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔄 Пройти заново", callback_data="restart"))
    return kb


# ─── РАСЧЁТ СТОИМОСТИ ─────────────────────────────────────────────────────────
def calculate_price(answers: list[str]) -> tuple[int, int, int]:
    """Возвращает (эконом, стандарт, премиум)"""
    furniture = answers[0] if len(answers) > 0 else "other"
    size      = answers[1] if len(answers) > 1 else "medium"
    material  = answers[2] if len(answers) > 2 else "ldsp"
    fittings  = answers[3] if len(answers) > 3 else "standard"

    base  = BASE_PRICE.get(furniture, 20000)
    mult  = SIZE_MULT.get(size, 1.0) * MATERIAL_MULT.get(material, 1.0)
    extra = FITTINGS_ADD.get(fittings, 0)

    standard = int(base * mult + extra)
    econom   = int(standard * 0.75)
    premium  = int(standard * 1.35)
    return econom, standard, premium


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# ─── ХЕНДЛЕРЫ ─────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.chat.id
    sessions[uid] = new_session()
    bot.send_message(
        uid,
        "👋 Привет! Я помогу узнать *точную стоимость мебели на заказ* в трёх вариантах всего за 1 минуту.\n\n"
        "Отвечайте на 5 простых вопросов — и получите расчёт прямо здесь 👇",
        parse_mode="Markdown",
    )
    send_question(uid, 0)


@bot.callback_query_handler(func=lambda c: c.data == "restart")
def cb_restart(call):
    uid = call.message.chat.id
    sessions[uid] = new_session()
    bot.answer_callback_query(call.id)
    bot.send_message(uid, "🔄 Начинаем заново!")
    send_question(uid, 0)


@bot.callback_query_handler(func=lambda c: c.data.startswith("q_"))
def cb_answer(call):
    uid = call.message.chat.id
    _, step_str, value = call.data.split("_", 2)
    step = int(step_str)

    if uid not in sessions:
        sessions[uid] = new_session()

    sess = sessions[uid]

    # защита от повторного нажатия
    if sess["step"] != step:
        bot.answer_callback_query(call.id, "Уже записано ✅")
        return

    sess["answers"].append(value)
    sess["step"] += 1
    bot.answer_callback_query(call.id, "✅ Записано")

    if sess["step"] < len(QUESTIONS):
        send_question(uid, sess["step"])
    else:
        # все вопросы пройдены — спрашиваем имя
        bot.send_message(uid, "📝 Отлично! Почти готово.\n\nКак вас зовут?")
        bot.register_next_step_handler_by_chat_id(uid, ask_phone)


def send_question(uid: int, step: int):
    q = QUESTIONS[step]
    bot.send_message(
        uid,
        f"*Вопрос {step + 1} из {len(QUESTIONS)}*\n\n{q['text']}",
        parse_mode="Markdown",
        reply_markup=quiz_keyboard(step),
    )


def ask_phone(message):
    uid = message.chat.id
    sessions[uid]["name"] = message.text.strip()
    bot.send_message(uid, f"Приятно познакомиться, {sessions[uid]['name']}! 😊\n\nВведите ваш номер телефона для связи:")
    bot.register_next_step_handler_by_chat_id(uid, finish_quiz)


def finish_quiz(message):
    uid = message.chat.id
    sess = sessions[uid]
    sess["phone"] = message.text.strip()

    econom, standard, premium = calculate_price(sess["answers"])
    name  = sess["name"]
    phone = sess["phone"]

    # результат пользователю
    result_text = (
        f"🎉 *{name}, вот ваш расчёт!*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💚 *Эконом-вариант*\n"
        f"    от {fmt(econom)} ₽\n"
        f"    _(базовые материалы, стандартная фурнитура)_\n\n"
        f"💛 *Стандарт-вариант*\n"
        f"    от {fmt(standard)} ₽\n"
        f"    _(материалы среднего класса, хорошая фурнитура)_\n\n"
        f"❤️ *Премиум-вариант*\n"
        f"    от {fmt(premium)} ₽\n"
        f"    _(лучшие материалы, премиум-фурнитура Blum/Hettich)_\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📞 Наш менеджер свяжется с вами в течение 30 минут для уточнения деталей и точного замера!\n\n"
        f"_Цены указаны ориентировочно и могут меняться после замера._"
    )
    bot.send_message(uid, result_text, parse_mode="Markdown", reply_markup=restart_keyboard())

    # уведомление менеджеру
    if MANAGER_CHAT_ID and MANAGER_CHAT_ID != "ВСТАВЬТЕ_CHAT_ID_МЕНЕДЖЕРА":
        answers_map = [QUESTIONS[i]["options"] for i in range(len(QUESTIONS))]
        answers_text = ""
        for i, ans_val in enumerate(sess["answers"]):
            label = next((lbl for lbl, val in answers_map[i] if val == ans_val), ans_val)
            answers_text += f"  {i+1}. {QUESTIONS[i]['text'].split()[1]} → {label}\n"

        manager_text = (
            f"🔔 *Новая заявка на мебель!*\n\n"
            f"👤 Имя: {name}\n"
            f"📱 Телефон: {phone}\n\n"
            f"*Ответы:*\n{answers_text}\n"
            f"💰 Расчёт: {fmt(econom)} / {fmt(standard)} / {fmt(premium)} ₽"
        )
        try:
            bot.send_message(MANAGER_CHAT_ID, manager_text, parse_mode="Markdown")
        except Exception as e:
            print(f"Не удалось отправить менеджеру: {e}")


# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("✅ Telegram-бот запущен...")
    bot.infinity_polling()

"""Обработчик inline-кнопок."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import Database, get_db_pool
from utils.auditory_names import get_russian_name

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на inline-кнопки."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    await Database.update_user_last_active(user_id)
    
    if data == "list_auditories":
        await show_auditories(query)
    elif data == "schedule_menu":
        await show_schedule_menu(query)
    elif data == "today_schedule":
        await show_today_schedule(query)
    elif data == "tomorrow_schedule":
        await show_tomorrow_schedule(query)
    elif data == "week_schedule":
        await show_week_schedule(query)
    elif data.startswith("aud_"):
        auditory_id = data[4:]
        await show_status_buttons(query, auditory_id, context)
    elif data.startswith("set_"):
        parts = data.split("_")
        if len(parts) >= 3:
            auditory_id = parts[1]
            status = parts[2]
            # Зелёный статус — сразу сохраняем
            if status == "green":
                await set_status_from_button(query, context, user_id, auditory_id, status, None)
            else:
                # Жёлтый/красный — запрашиваем комментарий
                context.user_data["waiting_for"] = {
                    "type": "status_comment",
                    "auditory_id": auditory_id,
                    "status": status,
                    "query": query  # сохраняем query для возврата
                }
                await query.edit_message_text(
                    f"📝 Опишите проблему для статуса **{status.upper()}**:\n\n"
                    "(отправьте текстовое сообщение или /cancel для отмены)",
                    parse_mode="Markdown"
                )
    elif data == "back_to_main":
        await show_main_menu(query)
    elif data == "help":
        await show_help(query)
    else:
        await query.edit_message_text("Неизвестная команда")


async def show_main_menu(query):
    """Показывает главное меню."""
    keyboard = [
        [InlineKeyboardButton("📋 Список аудиторий", callback_data="list_auditories")],
        [InlineKeyboardButton("📅 Расписание", callback_data="schedule_menu")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )


async def show_help(query):
    """Показывает справку."""
    keyboard = [
        [InlineKeyboardButton("📋 Список аудиторий", callback_data="list_auditories")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📌 **Доступные команды:**\n"
        "/start — главное меню\n"
        "/status <аудитория> <статус> — быстро отметить статус\n\n"
        "**Статусы:**\n"
        "🟢 green — всё работает\n"
        "🟡 yellow — есть проблемы\n"
        "🔴 red — не работает\n\n"
        "Используйте кнопки для навигации.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_schedule_menu(query):
    """Показывает расписание мероприятий."""
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="today_schedule")],
        [InlineKeyboardButton("📆 Завтра", callback_data="tomorrow_schedule")],
        [InlineKeyboardButton("📅 Эта неделя", callback_data="week_schedule")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 **Расписание мероприятий**\n\n"
        "Выберите период:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_today_schedule(query):
    """Показывает расписание на сегодня."""
    keyboard = [
        [InlineKeyboardButton("« К выбору периода", callback_data="schedule_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 **Сегодня**\n\n"
        "На сегодня мероприятий нет.\n\n"
        "Функция появится после интеграции с Google Calendar.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_tomorrow_schedule(query):
    """Показывает расписание на завтра."""
    keyboard = [
        [InlineKeyboardButton("« К выбору периода", callback_data="schedule_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📆 **Завтра**\n\n"
        "На завтра мероприятий нет.\n\n"
        "Функция появится после интеграции с Google Calendar.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_week_schedule(query):
    """Показывает расписание на неделю."""
    keyboard = [
        [InlineKeyboardButton("« К выбору периода", callback_data="schedule_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 **Эта неделя**\n\n"
        "На эту неделю мероприятий нет.\n\n"
        "Функция появится после интеграции с Google Calendar.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_auditories(query):
    """Показывает список аудиторий с русскими названиями на кнопках."""
    pool = get_db_pool()
    rows = await pool.fetch("SELECT id, name FROM auditories WHERE is_active = true ORDER BY name")
    
    if not rows:
        await query.edit_message_text("В базе нет аудиторий")
        return
    
    keyboard = []
    row_buttons = []
    for i, row_data in enumerate(rows):
        aud_id = row_data["id"]
        eng_name = row_data["name"]
        rus_name = get_russian_name(eng_name)
        
        row_buttons.append(InlineKeyboardButton(rus_name, callback_data=f"aud_{aud_id}"))
        
        if len(row_buttons) == 2 or i == len(rows) - 1:
            keyboard.append(row_buttons)
            row_buttons = []
    
    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Выберите аудиторию:",
        reply_markup=reply_markup
    )


async def show_status_buttons(query, auditory_id, context):
    """Показывает кнопки выбора статуса и текущее состояние аудитории."""
    pool = get_db_pool()
    
    row = await pool.fetchrow("SELECT name FROM auditories WHERE id = $1", int(auditory_id))
    if not row:
        await query.edit_message_text("Аудитория не найдена")
        return
    
    eng_name = row["name"]
    rus_name = get_russian_name(eng_name)
    
    # Получаем последний статус
    last_status = await Database.get_latest_status(int(auditory_id))
    
    status_text = ""
    if last_status:
        status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(last_status["status"], "⚪")
        status_time = last_status["created_at"].strftime("%d.%m.%Y %H:%M")
        status_text = f"\n\n**Текущий статус:** {status_emoji} {last_status['status'].upper()}\n_Обновлено: {status_time}_"
        if last_status.get("comment"):
            status_text += f"\n_Комментарий: {last_status['comment']}_"
    
    keyboard = [
        [
            InlineKeyboardButton("🟢 Работает", callback_data=f"set_{auditory_id}_green"),
            InlineKeyboardButton("🟡 Проблемы", callback_data=f"set_{auditory_id}_yellow"),
        ],
        [
            InlineKeyboardButton("🔴 Не работает", callback_data=f"set_{auditory_id}_red"),
        ],
        [InlineKeyboardButton("🔄 Обновить статус", callback_data=f"aud_{auditory_id}")],
        [InlineKeyboardButton("« Назад к списку", callback_data="list_auditories")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Аудитория: **{rus_name}**{status_text}\n\n"
        f"Выберите новый статус:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def set_status_from_button(query, context, user_id, auditory_id, status, comment):
    """Устанавливает статус через кнопку."""
    pool = get_db_pool()
    row = await pool.fetchrow("SELECT name FROM auditories WHERE id = $1", int(auditory_id))
    if not row:
        await query.edit_message_text("Аудитория не найдена")
        return
    
    eng_name = row["name"]
    rus_name = get_russian_name(eng_name)
    full_name = query.from_user.full_name or query.from_user.first_name or "Пользователь"
    
    await Database.add_user(telegram_id=user_id, full_name=full_name, username=query.from_user.username)
    
    success = await Database.add_status(
        telegram_id=user_id,
        auditory_name=eng_name,
        status=status,
        comment=comment
    )
    
    if success:
        status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(status, "")
        
        from config import config
        if config.GROUP_CHAT_ID:
            try:
                message = f"🔄 {full_name} обновил статус {rus_name}: {status_emoji} {status.upper()}"
                if comment:
                    message += f"\n📝 Комментарий: {comment}"
                await context.bot.send_message(
                    config.GROUP_CHAT_ID,
                    message
                )
            except Exception as e:
                logger.error("Не удалось отправить уведомление в группу: %s", e)
        
        # Возвращаемся к меню аудитории
        await show_status_buttons(query, auditory_id, context)
    else:
        await query.edit_message_text(
            "❌ Не удалось добавить статус",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад", callback_data=f"aud_{auditory_id}")]
            ])
        )
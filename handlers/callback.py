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
    
    if data == "status_green":
        await query.edit_message_text(
            "🟢 Введите /status <аудитория> green\n\n"
            "Например: /status 118 green"
        )
    elif data == "status_yellow":
        await query.edit_message_text(
            "🟡 Введите /status <аудитория> yellow [комментарий]\n\n"
            "Например: /status G3.56 yellow Проектор моргает"
        )
    elif data == "status_red":
        await query.edit_message_text(
            "🔴 Введите /status <аудитория> red [комментарий]\n\n"
            "Например: /status 335 red Нет звука"
        )
    elif data == "list_auditories":
        await show_auditories(query)
    elif data.startswith("aud_"):
        auditory_id = data[4:]
        await show_status_buttons(query, auditory_id)
    elif data.startswith("set_"):
        parts = data.split("_")
        if len(parts) >= 3:
            auditory_id = parts[1]
            status = parts[2]
            await set_status_from_button(query, context, user_id, auditory_id, status)
    elif data == "back_to_main":
        await show_main_menu(query)
    elif data == "help":
        await query.edit_message_text(
            "Доступные команды:\n"
            "/status — отметить статус аудитории\n"
            "/today — мероприятия на сегодня\n"
            "/start — приветствие\n\n"
            "Используйте кнопки для быстрого выбора."
        )
    else:
        await query.edit_message_text("Неизвестная команда")


async def show_auditories(query):
    """Показывает список аудиторий с русскими названиями на кнопках."""
    pool = get_db_pool()
    rows = await pool.fetch("SELECT id, name FROM auditories WHERE is_active = true ORDER BY name")
    
    if not rows:
        await query.edit_message_text("В базе нет аудиторий")
        return
    
    # Создаём кнопки с русскими названиями
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


async def show_status_buttons(query, auditory_id):
    """Показывает кнопки выбора статуса с русским названием аудитории."""
    pool = get_db_pool()
    row = await pool.fetchrow("SELECT name FROM auditories WHERE id = $1", int(auditory_id))
    if not row:
        await query.edit_message_text("Аудитория не найдена")
        return
    
    eng_name = row["name"]
    rus_name = get_russian_name(eng_name)
    
    keyboard = [
        [
            InlineKeyboardButton("🟢 Работает", callback_data=f"set_{auditory_id}_green"),
            InlineKeyboardButton("🟡 Проблемы", callback_data=f"set_{auditory_id}_yellow"),
        ],
        [
            InlineKeyboardButton("🔴 Не работает", callback_data=f"set_{auditory_id}_red"),
        ],
        [InlineKeyboardButton("« Назад к списку", callback_data="list_auditories")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Аудитория: {rus_name}\nВыберите статус:",
        reply_markup=reply_markup
    )


async def set_status_from_button(query, context, user_id, auditory_id, status):
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
        auditory_name=eng_name,  # в БД сохраняем английское название
        status=status,
        comment=None
    )
    
    if success:
        status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(status, "")
        
        from config import config
        if config.GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    config.GROUP_CHAT_ID,
                    f"🔄 {full_name} обновил статус {rus_name}: {status_emoji} {status.upper()}"
                )
            except Exception as e:
                logger.error("Не удалось отправить уведомление в группу: %s", e)
        
        await query.edit_message_text(
            f"✅ Статус аудитории {rus_name}: {status_emoji} {status.upper()}\n\n"
            "Что дальше?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 К списку аудиторий", callback_data="list_auditories")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ])
        )
    else:
        await query.edit_message_text(
            f"❌ Не удалось добавить статус. Проверьте, что аудитория существует.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад", callback_data="list_auditories")]
            ])
        )


async def show_main_menu(query):
    """Показывает главное меню."""
    keyboard = [
        [
            InlineKeyboardButton("🟢 Всё ок", callback_data="status_green"),
            InlineKeyboardButton("🟡 Проблемы", callback_data="status_yellow"),
            InlineKeyboardButton("🔴 Не работает", callback_data="status_red"),
        ],
        [InlineKeyboardButton("📋 Список аудиторий", callback_data="list_auditories")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )
"""Обработчики для работы с расписанием."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def show_schedule_menu(message):
    """
    Показывает меню выбора периода для расписания.
    
    Args:
        message: сообщение Telegram, в которое нужно отправить меню
    """
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="today_schedule")],
        [InlineKeyboardButton("📆 Завтра", callback_data="tomorrow_schedule")],
        [InlineKeyboardButton("📅 Неделя", callback_data="week_schedule")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "📅 **Расписание мероприятий**\n\n"
        "Выберите период:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
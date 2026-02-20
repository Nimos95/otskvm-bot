"""Обработчик для справки."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def show_help(message):
    """
    Показывает справочную информацию.
    
    Args:
        message: сообщение Telegram, в которое нужно отправить справку
    """
    keyboard = [
        [InlineKeyboardButton("📋 Список аудиторий", callback_data="list_auditories")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "📌 **Доступные команды:**\n"
        "/start — главное меню\n"
        "/status <аудитория> <статус> — быстро отметить статус\n\n"
        "**Статусы:**\n"
        "🟢 green — всё работает\n"
        "🟡 yellow — есть проблемы\n"
        "🔴 red — не работает\n\n"
        "**Навигация:**\n"
        "Используйте постоянное меню внизу экрана для быстрого доступа.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
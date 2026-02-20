"""Обработчики для работы с аудиториями."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import Database, get_db_pool
from utils.auditory_names import get_russian_name

logger = logging.getLogger(__name__)


async def show_auditories(message):
    """
    Показывает список аудиторий с кнопками для выбора.
    
    Args:
        message: сообщение Telegram, в которое нужно отправить список
    """
    pool = get_db_pool()
    rows = await pool.fetch("SELECT id, name FROM auditories WHERE is_active = true ORDER BY name")
    
    if not rows:
        await message.reply_text("В базе нет аудиторий")
        return
    
    # Создаём кнопки для каждой аудитории (по 2 в ряд)
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
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "Выберите аудиторию:",
        reply_markup=reply_markup
    )
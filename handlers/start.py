"""Обработчик команды /start."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import Database

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start.

    Регистрирует пользователя в БД и отправляет приветственное сообщение с кнопками.
    """
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    telegram_id = user.id
    full_name = user.full_name or user.first_name or "Пользователь"
    username = user.username

    success = await Database.add_user(telegram_id=telegram_id, full_name=full_name, username=username)
    if not success:
        logger.warning("Не удалось добавить пользователя %s", telegram_id)
    
    await Database.update_user_last_active(telegram_id)

    # Создаём inline-кнопки
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

    await update.message.reply_text(
        f"Привет, {full_name}!\n\n"
        "Я бот для управления аудиториями и статусами.\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )
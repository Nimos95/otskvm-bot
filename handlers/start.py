"""Обработчик команды /start."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import Database

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start.

    Регистрирует пользователя в БД и отправляет приветственное сообщение.
    """
    # Проверяем, что есть и пользователь, и сообщение
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    telegram_id = user.id
    full_name = user.full_name or user.first_name or "Пользователь"
    username = user.username

    success = await Database.add_user(telegram_id=telegram_id, full_name=full_name, username=username)
    if not success:
        logger.warning("Не удалось добавить пользователя %s", telegram_id)

    await update.message.reply_text(
        f"Привет, {full_name}!\n\n"
        "Я бот для управления аудиториями и статусами.\n\n"
        "Доступные команды:\n"
        "/start — начать работу\n"
        "/status — отметить статус аудитории\n"
        "/today — мероприятия на сегодня"
    )
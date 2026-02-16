"""Обработчик команды /status."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import Database

logger = logging.getLogger(__name__)

VALID_STATUSES = ("green", "yellow", "red")


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /status.

    Ожидает аргументы: /status <аудитория> <статус> [комментарий]
    Пример: /status 501 green
    Пример: /status 315 yellow Нет проектора
    """
    if not update.effective_user or not update.message:
        return

    text = (update.message.text or "").strip()
    parts = text.split(maxsplit=3)

    if len(parts) < 3:
        await update.message.reply_text(
            "Использование: /status <аудитория> <статус> [комментарий]\n\n"
            "Статусы: green, yellow, red\n"
            "Пример: /status 130 green\n"
            "Пример: /status 118 yellow Нет проектора"
        )
        return

    _, auditory_name, status_arg = parts[:3]
    comment = parts[3] if len(parts) > 3 else None

    telegram_id = update.effective_user.id
    full_name = update.effective_user.full_name or update.effective_user.first_name or "Пользователь"

    # Убеждаемся, что пользователь есть в БД
    await Database.add_user(telegram_id=telegram_id, full_name=full_name, username=update.effective_user.username)
    await Database.update_user_last_active(telegram_id)

    success = await Database.add_status(
        telegram_id=telegram_id,
        auditory_name=auditory_name,
        status=status_arg,
        comment=comment,
    )

    if success:
        status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(status_arg.lower(), "")
        await update.message.reply_text(
            f"Статус аудитории {auditory_name}: {status_emoji} {status_arg.upper()}"
            + (f"\nКомментарий: {comment}" if comment else "")
        )
    else:
        await update.message.reply_text(
            "Не удалось добавить статус. Проверьте название аудитории и что статус один из: green, yellow, red."
        )

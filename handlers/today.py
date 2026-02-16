"""Обработчик команды /today."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import Database

logger = logging.getLogger(__name__)


async def today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /today.

    Показывает мероприятия на сегодня (пока заглушка).
    """
    if not update.effective_user or not update.message:
        return

    telegram_id = update.effective_user.id
    full_name = update.effective_user.full_name or update.effective_user.first_name or "Пользователь"

    await Database.add_user(telegram_id=telegram_id, full_name=full_name, username=update.effective_user.username)
    await Database.update_user_last_active(telegram_id)

    events = await Database.get_today_events()

    if not events:
        await update.message.reply_text("На сегодня мероприятий нет.")
        return

    lines = ["📅 Мероприятия на сегодня:\n"]
    for i, event in enumerate(events, 1):
        title = event.get("title", "Без названия")
        start = event.get("start_time", "")
        auditory = event.get("auditory_id", "")
        lines.append(f"{i}. {title} — {start} (ауд. {auditory})")

    await update.message.reply_text("\n".join(lines))

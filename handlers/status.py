"""Обработчик команды /status."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.constants import AUDITORY_STATUSES
from database import Database
from utils.auditory_names import get_russian_name, get_english_name

logger = logging.getLogger(__name__)

VALID_STATUSES = AUDITORY_STATUSES


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /status.

    Ожидает аргументы: /status <аудитория> <статус> [комментарий]
    Пример: /status 118 green
    Пример: /status G3.56 yellow Проектор моргает
    """
    if not update.effective_user or not update.message:
        return

    text = (update.message.text or "").strip()
    parts = text.split(maxsplit=3)

    if len(parts) < 3:
        await update.message.reply_text(
            "Использование: /status <аудитория> <статус> [комментарий]\n\n"
            "Статусы: green, yellow, red\n"
            "Пример: /status 118 green\n"
            "Пример: /status G3.56 yellow Проектор моргает"
        )
        return

    _, auditory_name, status_arg = parts[:3]
    status_arg = status_arg.lower()
    comment = parts[3] if len(parts) > 3 else None

    telegram_id = update.effective_user.id
    full_name = update.effective_user.full_name or update.effective_user.first_name or "Пользователь"

    db_auditory_name = get_english_name(auditory_name)
    if db_auditory_name == auditory_name:
        db_auditory_name = auditory_name

    await Database.add_user(telegram_id=telegram_id, full_name=full_name, username=update.effective_user.username)
    await Database.update_user_last_active(telegram_id)

    success = await Database.add_status(
        telegram_id=telegram_id,
        auditory_name=db_auditory_name,
        status=status_arg,
        comment=comment,
    )

    if success:
        display_name = get_russian_name(db_auditory_name)
        status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(status_arg, "")
        
        from config import config
        if config.GROUP_CHAT_ID and config.TOPIC_ID:
            try:
                await context.bot.send_message(
                    chat_id=config.GROUP_CHAT_ID,
                    message_thread_id=config.TOPIC_ID,
                    text=f"🔄 {full_name} обновил статус {display_name}: {status_emoji} {status_arg.upper()}"
                         + (f"\n📝 Комментарий: {comment}" if comment else "")
                )
            except Exception as e:
                logger.error("Не удалось отправить уведомление в топик: %s", e)
        
        keyboard = [
            [
                InlineKeyboardButton("🟢 Всё ок", callback_data="status_green"),
                InlineKeyboardButton("🟡 Проблемы", callback_data="status_yellow"),
                InlineKeyboardButton("🔴 Не работает", callback_data="status_red"),
            ],
            [InlineKeyboardButton("📋 Список аудиторий", callback_data="list_auditories")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Статус аудитории {display_name}: {status_emoji} {status_arg.upper()}\n\n"
            "Что делаем дальше?",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Не удалось добавить статус. Проверьте название аудитории и что статус один из: green, yellow, red."
        )
"""Обработчик команды /start и первого запуска."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import Database, get_db_pool  # ← добавили get_db_pool!
from handlers.menu import show_persistent_menu

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start.
    
    Если пользователь новый — показываем кнопку запуска.
    Если уже зарегистрирован — сразу постоянное меню.
    """
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    telegram_id = user.id
    full_name = user.full_name or user.first_name or "Пользователь"
    username = user.username

    # Регистрируем пользователя в БД
    success = await Database.add_user(telegram_id=telegram_id, full_name=full_name, username=username)
    if not success:
        logger.warning("Не удалось добавить пользователя %s", telegram_id)
    
    await Database.update_user_last_active(telegram_id)

    # Проверяем, новый это пользователь (по наличию статусов)
    pool = get_db_pool()  # ← исправлено!
    row = await pool.fetchrow(
        "SELECT COUNT(*) FROM status_log WHERE reported_by = $1",
        telegram_id
    )
    is_new = row["count"] == 0 if row else True
    
    if is_new:
        # Показываем приветствие с кнопкой запуска
        keyboard = [
            [InlineKeyboardButton("🚀 Запустить бота", callback_data="first_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"👋 Привет, {full_name}!\n\n"
            "Я бот для учёта состояния аудиторий.\n"
            "Нажмите кнопку ниже, чтобы начать работу:",
            reply_markup=reply_markup
        )
    else:
        # Сразу показываем постоянное меню
        await show_persistent_menu(update)


async def first_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки 'Запустить бота'.
    """
    query = update.callback_query
    await query.answer()
    
    logger.info(f"Пользователь {query.from_user.id} нажал кнопку запуска")
    
    # Показываем постоянное меню
    await show_persistent_menu(query)


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отменяет текущее действие."""
    if context.user_data.get("waiting_for"):
        context.user_data["waiting_for"] = None
        await update.message.reply_text("❌ Действие отменено")
    else:
        await update.message.reply_text("Нет активного действия для отмены")
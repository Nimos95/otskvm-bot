"""Обработчики команды /start и первого запуска бота.

Задачи модуля:
- регистрировать нового пользователя в БД при первом взаимодействии;
- различать «совсем нового» пользователя и уже работавшего с ботом
  (по наличию записей в `status_log`);
- показывать приветствие с кнопкой запуска или сразу постоянное меню.
"""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import Database, get_db_pool  # ← добавили get_db_pool!
from handlers.menu import show_persistent_menu

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду `/start` от пользователя.

    Сценарий:
        1. Регистрирует пользователя или обновляет его данные в таблице `users`.
        2. Обновляет поле `last_active`.
        3. По наличию записей в `status_log` определяет, новый это пользователь
           или уже работал с ботом.
        4. Новому пользователю показывает приветствие с кнопкой «Запустить бота»,
           существующему — сразу постоянное меню.

    Аргументы:
        update: объект `Update` с командой `/start`.
        context: контекст бота (в этой функции почти не используется).

    Возможные ошибки:
        ⚠️ ВНИМАНИЕ: при недоступности БД пользователь по‑прежнему увидит ответ,
        но логи сохранят информацию о том, что регистрация не удалась.
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

    # 🔥 ВАЖНО: «новизна» пользователя определяется не по факту наличия записи
    # в `users`, а по активности в `status_log`. Это позволяет отличать тех,
    # кто уже что‑то отмечал по аудиториям, от тех, кто только запускает бота.
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
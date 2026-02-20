"""Точка входа Telegram-бота."""

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ChatMemberHandler, ContextTypes
)

from config import config
from database import close_db_pool, init_db_pool
from handlers import start, status, today
from handlers.callback import callback_handler
from handlers.message import message_handler
from handlers.menu import menu_button_handler
from services.sync_scheduler import sync_loop
from handlers.assign import assign_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)


async def new_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Приветствие при добавлении бота в группу/топик.
    """
    if update.my_chat_member.new_chat_member.status == "member":
        from handlers.menu import show_persistent_menu
        await show_persistent_menu(update)


async def main() -> None:
    """
    Главная асинхронная функция.
    """
    # Инициализация пула БД
    try:
        await init_db_pool()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.critical("Ошибка инициализации БД: %s", e, exc_info=True)
        return

    # Создание приложения бота
    application = Application.builder().token(config.BOT_TOKEN).build()

    # ============================================
    # РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ (ВАЖЕН ПОРЯДОК!)
    # ============================================

    # 1. Команды (самый высокий приоритет)
    application.add_handler(CommandHandler("start", start.start_handler))
    application.add_handler(CommandHandler("cancel", start.cancel_handler))
    application.add_handler(CommandHandler("status", status.status_handler))
    application.add_handler(CommandHandler("today", today.today_handler))
    application.add_handler(CommandHandler("assign", assign_handler))
    
    # 2. Inline-кнопки
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # 3. Постоянное меню (текстовые кнопки) - ДО общего обработчика!
    application.add_handler(MessageHandler(
        filters.Text(["📋 Аудитории", "📅 Расписание", "👥 Назначения", "❓ Помощь"]), 
        menu_button_handler
        ))
    
    # 4. Общий обработчик текстовых сообщений (для комментариев)
    #    ВСЕ текстовые сообщения, которые НЕ являются командами и НЕ попали в пункт 3
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # 5. Обработчик новых участников (для группы)
    application.add_handler(ChatMemberHandler(
        new_chat_member_handler, 
        ChatMemberHandler.MY_CHAT_MEMBER
    ))

    # Запуск фоновой синхронизации календаря
    asyncio.create_task(sync_loop())
    logger.info("Фоновая синхронизация календаря запущена")

    try:
        logger.info("Бот запущен")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt, останавливаем бота...")
    except Exception as e:
        logger.critical("Ошибка при запуске бота: %s", e, exc_info=True)
    finally:
        if application.updater.running:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await close_db_pool()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
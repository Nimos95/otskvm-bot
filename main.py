"""Точка входа Telegram-бота."""

import asyncio
import logging

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import config
from database import close_db_pool, init_db_pool
from handlers import start, status, today
from handlers.callback import callback_handler
from handlers.message import message_handler
from services.sync_scheduler import sync_loop  # ← импортируем синхронизацию

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Главная асинхронная функция: инициализирует БД, создаёт приложение,
    регистрирует обработчики и запускает бота. Обеспечивает graceful shutdown.
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

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start.start_handler))
    application.add_handler(CommandHandler("cancel", start.cancel_handler))
    application.add_handler(CommandHandler("status", status.status_handler))
    application.add_handler(CommandHandler("today", today.today_handler))
    
    # Регистрация обработчика inline-кнопок
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Регистрация обработчика текстовых сообщений (для комментариев)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Запуск фоновой задачи синхронизации календаря
    asyncio.create_task(sync_loop())
    logger.info("Фоновая синхронизация календаря запущена")  # ← теперь это появится в логах

    try:
        logger.info("Бот запущен")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Держим бота запущенным
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt, останавливаем бота...")
    except Exception as e:
        logger.critical("Ошибка при запуске бота: %s", e, exc_info=True)
    finally:
        # Корректная остановка бота
        if application.updater.running:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        
        # Закрываем пул БД
        await close_db_pool()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    # Создаём и устанавливаем event loop вручную
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
"""Точка входа Telegram-бота."""

import asyncio
import logging

from telegram.ext import Application, CommandHandler

from config import Config, config
from database import close_db_pool, init_db_pool
from handlers import start, status, today

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
    try:
        await init_db_pool()
    except Exception as e:
        logger.critical("Ошибка инициализации БД: %s", e, exc_info=True)
        return

    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start.start_handler))
    application.add_handler(CommandHandler("status", status.status_handler))
    application.add_handler(CommandHandler("today", today.today_handler))

    try:
        logger.info("Бот запущен")
        await application.run_polling()
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt, останавливаем бота...")
    except Exception as e:
        logger.critical("Ошибка при запуске бота: %s", e, exc_info=True)
        return
    finally:
        await close_db_pool()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())

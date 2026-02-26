"""Точка входа Telegram-бота."""

import asyncio
import logging
from datetime import datetime, timedelta

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
from handlers.assign import assign_handler
from services.sync_scheduler import sync_loop
from services.reminder import (
    find_upcoming_events, 
    send_reminder, 
    auto_complete_events,
    find_completed_events,      # ← новая функция
    send_completion_reminder,    # ← новая функция (опционально)
    log_notification
)
from handlers.admin import admin_panel_handler, manage_roles_handler

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


async def reminder_loop(application: Application):
    """Бесконечный цикл проверки событий."""
    while True:
        try:
            # 1. Напоминания о предстоящих событиях
            upcoming_events = await find_upcoming_events(minutes_before=35)
            for event in upcoming_events:
                if event.get('telegram_id'):
                    await send_reminder(event, application.bot)
                    await asyncio.sleep(1)
            
            # 2. Напоминания о завершении
            completed_events = await find_completed_events()
            for event in completed_events:
                if event.get('telegram_id'):
                    await send_completion_reminder(event, application.bot)
                    await asyncio.sleep(1)
            
            # 3. Автоматическое завершение
            auto_completed = await auto_complete_events()
            if auto_completed > 0:
                logger.info(f"Автоматически завершено {auto_completed} мероприятий")
            
        except Exception as e:
            logger.error(f"Ошибка в цикле напоминаний: {e}", exc_info=True)
        
        await asyncio.sleep(300)  # каждые 5 минут


async def morning_summary_loop(application: Application):
    """
    Цикл для утренней сводки.
    Запускается в 9:00 каждый день.
    """
    while True:
        try:
            now = datetime.now()
            # Вычисляем время до следующего 9:00
            next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Утренняя сводка запланирована через {wait_seconds/3600:.1f} часов")
            
            await asyncio.sleep(wait_seconds)
            
            # Отправляем сводку
            from services.reminder import send_morning_summary
            await send_morning_summary(application.bot)
            
        except Exception as e:
            logger.error(f"Ошибка в цикле утренней сводки: {e}", exc_info=True)


async def afternoon_report_loop(application: Application):
    """
    Цикл для дневного отчёта менеджеру.
    Запускается в 14:00 каждый день.
    """
    while True:
        try:
            now = datetime.now()
            # Вычисляем время до следующего 14:00
            next_run = now.replace(hour=14, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Дневной отчёт запланирован через {wait_seconds/3600:.1f} часов")
            
            await asyncio.sleep(wait_seconds)
            
            # Отправляем отчёт
            from services.reminder import send_afternoon_report
            await send_afternoon_report(application.bot)
            
        except Exception as e:
            logger.error(f"Ошибка в цикле дневного отчёта: {e}", exc_info=True)


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
    application.add_handler(CommandHandler("setrole", manage_roles_handler))
    
    # 2. Inline-кнопки
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # 3. Постоянное меню (текстовые кнопки) - ДО общего обработчика!
    application.add_handler(MessageHandler(
        filters.Text(["📋 Аудитории", "📅 Расписание", "👥 Назначения", 
                  "❓ Помощь", "📋 Мои мероприятия", "🛠 Админ-панель",
                  "🔄 Обновить меню"]),  # ← добавили
        menu_button_handler
    ))
    
    # 4. Общий обработчик текстовых сообщений (для комментариев)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # 5. Обработчик новых участников (для группы)
    application.add_handler(ChatMemberHandler(
        new_chat_member_handler, 
        ChatMemberHandler.MY_CHAT_MEMBER
    ))

    # ============================================
    # ЗАПУСК ФОНОВЫХ ЗАДАЧ
    # ============================================
    
    # Синхронизация календаря (каждые 6 часов)
    asyncio.create_task(sync_loop())
    logger.info("Фоновая синхронизация календаря запущена")
    
    # Напоминания о мероприятиях (каждые 5 минут)
    asyncio.create_task(reminder_loop(application))
    logger.info("Фоновая проверка напоминаний запущена")
    
    # Утренняя сводка (в 9:00)
    asyncio.create_task(morning_summary_loop(application))
    logger.info("Планировщик утренней сводки запущен")
    
    # Дневной отчёт (в 14:00)
    asyncio.create_task(afternoon_report_loop(application))
    logger.info("Планировщик дневного отчёта запущен")

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
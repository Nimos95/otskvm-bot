"""Точка входа Telegram‑бота OTSKVM.

Задачи модуля:
- инициализировать пул подключений к БД и приложение Telegram‑бота;
- зарегистрировать все обработчики команд, сообщений и callback‑кнопок
  в правильном порядке (от более специфичных к более общим);
- запустить фоновые циклы (синхронизация календаря, напоминания, отчёты);
- корректно завершить работу бота и освободить ресурсы при остановке.

Используемые компоненты:
- `telegram.ext.Application` и хендлеры команд/сообщений;
- инфраструктурные модули `database`, `services.reminder`, `services.sync_scheduler`;
- обработчики из `handlers.*` для прикладной логики.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ChatMemberHandler, ContextTypes
)

from handlers.engineer_tasks import register_handlers as register_engineer_tasks
from handlers.admin import admin_sync_handler
from handlers.admin import admin_callbacks

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
    """
    Бесконечный цикл проверки событий для отправки напоминаний и авто‑завершения.

    Сценарий:
        1. Периодически ищет предстоящие мероприятия и отправляет напоминания.
        2. Ищет завершившиеся мероприятия и напоминает инженерам отметить выполнение.
        3. Автоматически завершает «подвисшие» мероприятия по истечении времени.

    Примечания:
        🔥 ВАЖНО: цикл обёрнут в try/except, чтобы единичные ошибки в БД или сети
        не останавливали фоновую задачу. Между итерациями выдерживается пауза 5 минут.
    """
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
    Фоновый цикл отправки утренней сводки в 9:00 каждый день.

    Логика:
        - вычисляет ближайшее время запуска (сдвигает на следующий день, если время ушло);
        - спит до нужного момента;
        - вызывает `services.reminder.send_morning_summary`.

    Примечания:
        ⚠️ ВНИМАНИЕ: цикл не использует cron, поэтому при долгих остановках
        бота сводка может прийти позже 9:00, но сам механизм сохраняется простым.
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
    Фоновый цикл отправки дневного отчёта менеджеру в 14:00 каждый день.

    Логика аналогична `morning_summary_loop`, но использует функцию
    `services.reminder.send_afternoon_report`.
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

async def evening_reminder_loop(application: Application):
    """
    Цикл для вечернего напоминания менеджеру о назначениях.
    Запускается в 18:00 каждый день.
    """
    while True:
        try:
            now = datetime.now()
            # Вычисляем время до следующего 18:00
            next_run = now.replace(hour=18, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Вечернее напоминание запланировано через {wait_seconds/3600:.1f} часов")
            
            await asyncio.sleep(wait_seconds)
            
            # Отправляем напоминание
            from services.reminder import send_manager_evening_reminder
            await send_manager_evening_reminder(application.bot)
            
        except Exception as e:
            logger.error(f"Ошибка в цикле вечернего напоминания: {e}", exc_info=True)


async def main() -> None:
    """
    Главная асинхронная функция запуска бота.

    Этапы:
        1. Инициализация пула БД (без него остальные модули работать не смогут).
        2. Создание приложения Telegram‑бота.
        3. Регистрация всех обработчиков и запуск фоновых циклов.
        4. Запуск polling‑механизма и удержание процесса в рабочем состоянии.
        5. Корректная остановка приложения и закрытие пула БД.
    """
    # Инициализация пула БД
    try:
        await init_db_pool()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.critical("Ошибка инициализации БД: %s", e, exc_info=True)
        return

    # Создание приложения бота (основной объект, на который вешаются все хендлеры).
    application = Application.builder().token(config.BOT_TOKEN).build()

    # ============================================
    # РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ (ВАЖЕН ПОРЯДОК!)
    # ============================================

    # 1. Команды (самый высокий приоритет).
   # 🔥 ВАЖНО: команды обрабатываются раньше обычных сообщений, поэтому их
    # регистрация должна выполняться до `MessageHandler` с фильтром TEXT.
    application.add_handler(CommandHandler("start", start.start_handler))
    application.add_handler(CommandHandler("cancel", start.cancel_handler))
    application.add_handler(CommandHandler("status", status.status_handler))
    application.add_handler(CommandHandler("today", today.today_handler))
    application.add_handler(CommandHandler("assign", assign_handler))
    application.add_handler(CommandHandler("setrole", manage_roles_handler))
    
    # 1.5 Специфичные CallbackHandler'ы (с конкретными pattern).
    # Регистрация обработчиков engineer_tasks (отмена и завершение мероприятий)
    register_engineer_tasks(application)
    logger.info("Обработчики engineer_tasks зарегистрированы")

    from handlers.assign import assign_list_handler
    application.add_handler(CallbackQueryHandler(assign_list_handler, pattern="^assign_list$"))
    
    # Регистрация обработчиков админ-панели (синхронизация, статистика, тесты)
    for pattern, handler in admin_callbacks.items():
        application.add_handler(CallbackQueryHandler(handler, pattern=f"^{pattern}$"))
    logger.info(f"Обработчики админ-панели зарегистрированы: {len(admin_callbacks)} шт.")
    
    # 2. Общий обработчик inline‑кнопок (для всех остальных callback).
    # ⚠️ ВНИМАНИЕ: этот хендлер должен регистрироваться после всех точечных
    # `CallbackQueryHandler` с pattern, иначе будет «перехватывать» их события.
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # 3. Постоянное меню (текстовые кнопки) — обычные сообщения с фиксированным текстом.
    application.add_handler(MessageHandler(
        filters.Text(["📋 Аудитории", "📅 Расписание", "👥 Назначения", 
                  "❓ Помощь", "📋 Мои мероприятия", "🛠 Админ-панель",
                  "🔄 Обновить меню"]),
        menu_button_handler
    ))
    
    # 4. Общий обработчик текстовых сообщений — самый широкий фильтр.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # 5. Обработчик изменения статуса бота в чате (например, добавление в группу).
    application.add_handler(ChatMemberHandler(
        new_chat_member_handler, 
        ChatMemberHandler.MY_CHAT_MEMBER
    ))

    # ============================================
    # ЗАПУСК ФОНОВЫХ ЗАДАЧ
    # ============================================
    
    # Синхронизация календаря (каждые 6 часов).
    asyncio.create_task(sync_loop())
    logger.info("Фоновая синхронизация календаря запущена")
    
    # Напоминания о мероприятиях (каждые 5 минут).
    asyncio.create_task(reminder_loop(application))
    logger.info("Фоновая проверка напоминаний запущена")
    
    # Утренняя сводка (в 9:00).
    asyncio.create_task(morning_summary_loop(application))
    logger.info("Планировщик утренней сводки запущен")
    
    # Дневной отчёт (в 14:00).
    asyncio.create_task(afternoon_report_loop(application))
    logger.info("Планировщик дневного отчёта запущен")

    # Вечернее напоминание менеджеру (в 18:00)
    asyncio.create_task(evening_reminder_loop(application))
    logger.info("Планировщик вечернего напоминания запущен")

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
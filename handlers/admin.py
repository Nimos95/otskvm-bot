"""Административные функции для тестирования и отладки бота.

Доступные роли:
- superadmin: полный доступ ко всем функциям
- manager: доступ к синхронизации и базовым функциям
"""

import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.roles import require_roles, check_permission, ROLE_NAMES, set_user_role
from database import get_db_pool
from services.reminder import (
    find_upcoming_events, 
    send_reminder, 
    auto_complete_events,
    send_morning_summary,
    send_afternoon_report
)
from services.google_calendar import sync_calendar
from config import config

logger = logging.getLogger(__name__)


# ============================================
# АДМИН-ПАНЕЛЬ (доступна manager и superadmin)
# ============================================

@require_roles(['manager', 'superadmin'])
async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает панель администратора.
    Доступно для manager и superadmin.
    """
    # Проверяем, откуда пришёл вызов
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        message = query.message
    else:
        # Вызов из текстовой кнопки меню
        user_id = update.effective_user.id
        message = update.message
    
    # Определяем роль пользователя
    from utils.roles import get_user_role
    role = await get_user_role(user_id)
    
    # Базовые кнопки для всех (manager и superadmin)
    keyboard = [
        [InlineKeyboardButton("🔄 Принудительная синхронизация", callback_data="admin_sync")],
        [InlineKeyboardButton("📋 Проверка БД", callback_data="admin_db_stats")],
    ]
    
    # Для superadmin добавляем тестовые функции
    if role == 'superadmin':
        keyboard.extend([
            [InlineKeyboardButton("📅 Тест напоминаний", callback_data="admin_test_reminders")],
            [InlineKeyboardButton("✅ Тест завершения", callback_data="admin_test_completion")],
            [InlineKeyboardButton("🌅 Тест утренней сводки", callback_data="admin_test_morning")],
            [InlineKeyboardButton("📊 Тест дневного отчёта", callback_data="admin_test_afternoon")],
            [InlineKeyboardButton("🔄 Тест синхронизации", callback_data="admin_test_sync")],
        ])
    
    # Кнопка возврата
    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем/редактируем сообщение в зависимости от источника
    if update.callback_query:
        await query.edit_message_text(
            "🛠 **Панель управления**\n\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await message.reply_text(
            "🛠 **Панель управления**\n\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


# ============================================
# ПРИНУДИТЕЛЬНАЯ СИНХРОНИЗАЦИЯ (manager и superadmin)
# ============================================

@require_roles(['manager', 'superadmin'])
async def admin_sync_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Принудительная синхронизация с Google Calendar.
    Доступно для manager и superadmin.
    """
    query = update.callback_query
    await query.answer()
    
    # Отправляем сообщение о начале
    await query.edit_message_text(
        "🔄 **Синхронизация с Google Calendar...**\n\n"
        "Пожалуйста, подождите. Это может занять до минуты.",
        parse_mode="Markdown"
    )
    
    try:
        start_time = datetime.now()
        
        # Запускаем синхронизацию
        await sync_calendar(days=30)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Получаем статистику после синхронизации
        pool = get_db_pool()
        stats = await pool.fetchrow(
            """
            SELECT 
                COUNT(*) as total_events,
                COUNT(*) FILTER (WHERE start_time > NOW()) as upcoming
            FROM calendar_events
            """
        )
        
        # Успешное завершение
        await query.edit_message_text(
            f"✅ **Синхронизация завершена!**\n\n"
            f"📊 **Результат:**\n"
            f"• Всего событий в БД: {stats['total_events']}\n"
            f"• Предстоящих: {stats['upcoming']}\n"
            f"• Время выполнения: {duration:.1f} сек.\n\n"
            f"🕐 {end_time.strftime('%d.%m.%Y %H:%M:%S')}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад в админ-панель", callback_data="admin_panel")
            ]]),
            parse_mode="Markdown"
        )
        
        logger.info(f"Принудительная синхронизация выполнена пользователем {query.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ **Ошибка синхронизации**\n\n"
            f"```\n{str(e)[:200]}\n```",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад в админ-панель", callback_data="admin_panel")
            ]]),
            parse_mode="Markdown"
        )


# ============================================
# СТАТИСТИКА БД (manager и superadmin)
# ============================================

@require_roles(['manager', 'superadmin'])
async def admin_db_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает агрегированную статистику по ключевым таблицам БД.

    Доступ:
        Доступно для ролей `manager` и `superadmin`.

    Примечания:
        🔥 ВАЖНО (SQL): используется один запрос с несколькими подзапросами
        `SELECT COUNT(*)`, чтобы минимизировать время round‑trip к базе и
        получить срез по пользователям, аудиториям, статусам и назначениям.
    """
    query = update.callback_query
    await query.answer()
    
    pool = get_db_pool()
    
    stats = await pool.fetchrow(
        """
        SELECT 
            (SELECT COUNT(*) FROM users) as users_count,
            (SELECT COUNT(*) FROM users WHERE role = 'engineer') as engineers_count,
            (SELECT COUNT(*) FROM auditories WHERE is_active = true) as auditories_count,
            (SELECT COUNT(*) FROM status_log WHERE created_at > NOW() - INTERVAL '7 days') as weekly_logs,
            (SELECT COUNT(*) FROM calendar_events WHERE start_time > NOW()) as upcoming_events,
            (SELECT COUNT(*) FROM event_assignments WHERE status = 'assigned') as pending_assignments,
            (SELECT COUNT(*) FROM event_assignments WHERE status = 'accepted') as active_assignments,
            (SELECT COUNT(*) FROM event_assignments WHERE status = 'cancelled') as cancelled_assignments,
            (SELECT COUNT(*) FROM cancellation_log WHERE cancelled_at > NOW() - INTERVAL '7 days') as weekly_cancellations
        """
    )
    
    text = "📊 **Статистика базы данных**\n\n"
    text += f"👥 **Пользователи:**\n"
    text += f"• Всего: {stats['users_count']}\n"
    text += f"• Инженеров: {stats['engineers_count']}\n\n"
    
    text += f"🏢 **Аудитории:**\n"
    text += f"• Активных: {stats['auditories_count']}\n\n"
    
    text += f"📝 **Статусы:**\n"
    text += f"• За 7 дней: {stats['weekly_logs']}\n\n"
    
    text += f"📅 **Мероприятия:**\n"
    text += f"• Предстоящих: {stats['upcoming_events']}\n\n"
    
    text += f"👤 **Назначения:**\n"
    text += f"• Ожидают: {stats['pending_assignments']}\n"
    text += f"• Активных: {stats['active_assignments']}\n"
    text += f"• Отменённых: {stats['cancelled_assignments']}\n\n"
    
    text += f"🚫 **Отмены за 7 дней:** {stats['weekly_cancellations']}"
    
    # Кнопка для возврата
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ============================================
# ТЕСТОВЫЕ ФУНКЦИИ (только superadmin)
# ============================================

@require_roles(['superadmin'])
async def admin_test_reminders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Тестирует систему напоминаний.
    Только для superadmin.
    """
    query = update.callback_query
    await query.answer()
    
    pool = get_db_pool()
    
    # Получаем ближайшие события
    events = await find_upcoming_events(minutes_before=35)
    
    if not events:
        await query.edit_message_text(
            "❌ Нет ближайших событий для тестирования.\n\n"
            "Создайте событие в календаре через 30-40 минут и назначьте ответственного."
        )
        return
    
    # Формируем список событий
    text = "📅 **Найденные события:**\n\n"
    for event in events:
        text += f"• {event['start_time'].strftime('%H:%M')} — {event['title']}\n"
        text += f"  Инженер: {event['engineer_name'] or 'не назначен'}\n\n"
    
    # Кнопка для отправки тестового напоминания
    keyboard = [
        [InlineKeyboardButton("🔔 Отправить тестовое напоминание", callback_data="admin_send_test_reminder")],
        [InlineKeyboardButton("« Назад", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


@require_roles(['superadmin'])
async def admin_send_test_reminder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет тестовое напоминание для первого найденного события.
    Только для superadmin.
    """
    query = update.callback_query
    await query.answer()
    
    events = await find_upcoming_events(minutes_before=35)
    
    if not events:
        await query.edit_message_text("❌ Нет событий для тестирования.")
        return
    
    event = events[0]
    await send_reminder(event, context.bot)
    
    await query.edit_message_text(
        f"✅ Тестовое напоминание отправлено!\n\n"
        f"Событие: {event['title']}\n"
        f"Инженер: {event['engineer_name']}"
    )


@require_roles(['superadmin'])
async def admin_test_completion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Тестирует автоматическое завершение мероприятий (`auto_complete_events`).

    Доступ:
        Только для `superadmin`.

    Сценарий:
        - запускает авто‑завершение;
        - показывает количество обновлённых записей;
        - дополнительно выбирает несколько последних завершённых мероприятий
          для быстрой визуальной проверки.
    """
    query = update.callback_query
    await query.answer()
    
    # Запускаем автоматическое завершение
    count = await auto_complete_events()
    
    # Проверяем, какие мероприятия должны были завершиться
    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT 
            ce.title,
            ce.end_time,
            ea.status,
            ea.completed_at
        FROM calendar_events ce
        JOIN event_assignments ea ON ce.id = ea.event_id
        WHERE ce.end_time < NOW() - INTERVAL '1 hour'
          AND ea.status = 'done'
        ORDER BY ce.end_time DESC
        LIMIT 5
        """
    )
    
    if rows:
        text = f"✅ Автоматически завершено {count} мероприятий.\n\n"
        text += "**Последние завершённые:**\n"
        for row in rows:
            text += f"• {row['title']} — {row['end_time'].strftime('%H:%M')}\n"
    else:
        text = f"❌ Нет мероприятий для автоматического завершения.\n\n"
        text += f"Запущена проверка, но ничего не найдено."
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)


@require_roles(['superadmin'])
async def admin_test_morning_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет тестовую утреннюю сводку.
    Только для superadmin.
    """
    query = update.callback_query
    await query.answer()
    
    await send_morning_summary(context.bot)
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🌅 Тестовая утренняя сводка отправлена!\n"
        "Проверьте топик с ботом.",
        reply_markup=reply_markup
    )


@require_roles(['superadmin'])
async def admin_test_afternoon_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет тестовый дневной отчёт.
    Только для superadmin.
    """
    query = update.callback_query
    await query.answer()
    
    await send_afternoon_report(context.bot)
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📊 Тестовый дневной отчёт отправлен!\n"
        "Проверьте топик с ботом.",
        reply_markup=reply_markup
    )


@require_roles(['superadmin'])
async def admin_test_sync_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Тест синхронизации с Google Calendar.
    Отличается от обычной синхронизации тем, что показывает подробный лог.
    Только для superadmin.
    """
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔄 Запускаю тестовую синхронизацию с подробным логированием..."
    )
    
    try:
        start_time = datetime.now()
        
        # Включаем подробное логирование для теста
        import logging
        old_level = logging.getLogger('services.google_calendar').level
        logging.getLogger('services.google_calendar').setLevel(logging.DEBUG)
        
        await sync_calendar(days=30)
        
        # Возвращаем уровень логирования
        logging.getLogger('services.google_calendar').setLevel(old_level)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        pool = get_db_pool()
        new_events = await pool.fetchval(
            "SELECT COUNT(*) FROM calendar_events WHERE last_sync > NOW() - INTERVAL '1 minute'"
        )
        
        await query.edit_message_text(
            f"✅ **Тестовая синхронизация завершена!**\n\n"
            f"📊 **Результат:**\n"
            f"• Новых/обновлённых событий: {new_events}\n"
            f"• Время выполнения: {duration:.1f} сек.\n\n"
            f"Подробности смотрите в логах.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад", callback_data="admin_panel")
            ]]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при тестовой синхронизации: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ **Ошибка синхронизации**\n\n"
            f"{str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Назад", callback_data="admin_panel")
            ]]),
            parse_mode="Markdown"
        )


# ============================================
# УПРАВЛЕНИЕ РОЛЯМИ (только superadmin)
# ============================================

@require_roles(['superadmin'])
async def manage_roles_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Управление ролями пользователей (только для superadmin).
    Использование: /setrole @username роль
    """
    if not context.args or len(context.args) < 2:
        roles_text = "\n".join([f"• {role} — {desc}" for role, desc in ROLE_NAMES.items()])
        await update.message.reply_text(
            f"❌ **Использование:** /setrole @username роль\n\n"
            f"**Доступные роли:**\n{roles_text}",
            parse_mode="Markdown"
        )
        return
    
    username = context.args[0].replace('@', '')
    new_role = context.args[1].lower()
    
    # Проверяем существование роли
    if new_role not in ROLE_NAMES:
        await update.message.reply_text(
            f"❌ Роль '{new_role}' не существует.\n\n"
            f"Доступные роли: {', '.join(ROLE_NAMES.keys())}"
        )
        return
    
    # Находим пользователя по username
    pool = get_db_pool()
    user = await pool.fetchrow(
        "SELECT telegram_id, full_name FROM users WHERE username = $1",
        username
    )
    
    if not user:
        await update.message.reply_text(f"❌ Пользователь @{username} не найден в базе данных")
        return
    
    # Устанавливаем роль
    success = await set_user_role(
        update.effective_user.id,
        user['telegram_id'],
        new_role
    )
    
    if success:
        await update.message.reply_text(
            f"✅ Роль для @{username} ({user['full_name']}) изменена на {ROLE_NAMES[new_role]}"
        )
    else:
        await update.message.reply_text("❌ Не удалось изменить роль")


# ============================================
# СЛОВАРЬ ДЛЯ МАППИНГА CALLBACK_DATA
# ============================================

# Основные обработчики (для manager и superadmin)
admin_callbacks = {
    "admin_panel": admin_panel_handler,
    "admin_sync": admin_sync_handler,
    "admin_db_stats": admin_db_stats_handler,
}

# Тестовые обработчики (только для superadmin)
admin_test_callbacks = {
    "admin_test_reminders": admin_test_reminders_handler,
    "admin_send_test_reminder": admin_send_test_reminder_handler,
    "admin_test_completion": admin_test_completion_handler,
    "admin_test_morning": admin_test_morning_handler,
    "admin_test_afternoon": admin_test_afternoon_handler,
    "admin_test_sync": admin_test_sync_handler,
}

# Объединяем словари
admin_callbacks.update(admin_test_callbacks)
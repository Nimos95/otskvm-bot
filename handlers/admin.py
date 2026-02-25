"""Административные функции для тестирования и отладки бота."""

import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.roles import require_roles, check_permission, ROLE_NAMES
from utils.roles import set_user_role, ROLE_NAMES, require_roles

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

@require_roles(['superadmin'])
async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает панель администратора с тестовыми функциями.
    Доступно только для superadmin.
    """
    # TODO: добавить проверку роли superadmin
    keyboard = [
        [InlineKeyboardButton("📅 Тест напоминаний", callback_data="test_reminders")],
        [InlineKeyboardButton("✅ Тест завершения", callback_data="test_completion")],
        [InlineKeyboardButton("🌅 Тест утренней сводки", callback_data="test_morning")],
        [InlineKeyboardButton("📊 Тест дневного отчёта", callback_data="test_afternoon")],
        [InlineKeyboardButton("🔄 Тест синхронизации", callback_data="test_sync")],
        [InlineKeyboardButton("📋 Проверка БД", callback_data="test_db")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛠 **Панель администратора**\n\n"
        "Выберите тестовую функцию:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@require_roles(['superadmin'])
async def test_reminders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Тестирует систему напоминаний.
    Показывает ближайшие события и отправляет тестовое напоминание.
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
        [InlineKeyboardButton("🔔 Отправить тестовое напоминание", callback_data="send_test_reminder")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@require_roles(['superadmin'])
async def send_test_reminder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет тестовое напоминание для первого найденного события.
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
async def test_completion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Тестирует автоматическое завершение мероприятий.
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
    
    await query.edit_message_text(text, parse_mode="Markdown")

@require_roles(['superadmin'])
async def test_morning_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет тестовую утреннюю сводку.
    """
    query = update.callback_query
    await query.answer()
    
    await send_morning_summary(context.bot)
    
    await query.edit_message_text(
        "🌅 Тестовая утренняя сводка отправлена!\n"
        "Проверьте топик с ботом."
    )

@require_roles(['superadmin'])
async def test_afternoon_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет тестовый дневной отчёт.
    """
    query = update.callback_query
    await query.answer()
    
    await send_afternoon_report(context.bot)
    
    await query.edit_message_text(
        "📊 Тестовый дневной отчёт отправлен!\n"
        "Проверьте топик с ботом."
    )

@require_roles(['superadmin'])
async def test_sync_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запускает принудительную синхронизацию с Google Calendar.
    """
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔄 Запускаю синхронизацию...")
    
    await sync_calendar(days=30)
    
    await query.edit_message_text(
        "✅ Синхронизация завершена!\n"
        "Проверьте таблицу calendar_events."
    )

@require_roles(['superadmin'])
async def test_db_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает статистику по таблицам БД.
    """
    query = update.callback_query
    await query.answer()
    
    pool = get_db_pool()
    
    stats = await pool.fetch(
        """
        SELECT 
            (SELECT COUNT(*) FROM users) as users_count,
            (SELECT COUNT(*) FROM auditories) as auditories_count,
            (SELECT COUNT(*) FROM status_log) as logs_count,
            (SELECT COUNT(*) FROM calendar_events) as events_count,
            (SELECT COUNT(*) FROM event_assignments) as assignments_count,
            (SELECT COUNT(*) FROM notifications) as notifications_count
        """
    )
    
    row = stats[0]
    
    text = "📋 **Статистика базы данных**\n\n"
    text += f"👥 Пользователи: {row['users_count']}\n"
    text += f"🏢 Аудитории: {row['auditories_count']}\n"
    text += f"📝 Записей статусов: {row['logs_count']}\n"
    text += f"📅 Событий календаря: {row['events_count']}\n"
    text += f"👤 Назначений: {row['assignments_count']}\n"
    text += f"🔔 Уведомлений: {row['notifications_count']}\n"
    
    # Кнопка для возврата
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

@require_roles(['superadmin'])
async def manage_roles_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Управление ролями пользователей (только для superadmin).
    """
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /setrole @username роль\n\n"
            "Доступные роли:\n"
            "👑 superadmin — полный доступ\n"
            "📊 admin — просмотр статистики\n"
            "📋 manager — управление\n"
            "🔧 engineer — базовый доступ\n"
            "👁️ viewer — только просмотр"
        )
        return
    
    username = context.args[0].replace('@', '')
    new_role = context.args[1].lower()
    
    # Находим пользователя по username
    pool = get_db_pool()
    user = await pool.fetchrow(
        "SELECT telegram_id FROM users WHERE username = $1",
        username
    )
    
    if not user:
        await update.message.reply_text(f"❌ Пользователь @{username} не найден")
        return
    
    # Устанавливаем роль
    success = await set_user_role(
        update.effective_user.id,
        user['telegram_id'],
        new_role
    )
    
    if success:
        await update.message.reply_text(
            f"✅ Роль для @{username} изменена на {ROLE_NAMES.get(new_role, new_role)}"
        )
    else:
        await update.message.reply_text("❌ Не удалось изменить роль")


# Словарь для маппинга callback_data
admin_callbacks = {
    "admin_panel": admin_panel_handler,
    "test_reminders": test_reminders_handler,
    "send_test_reminder": send_test_reminder_handler,
    "test_completion": test_completion_handler,
    "test_morning": test_morning_handler,
    "test_afternoon": test_afternoon_handler,
    "test_sync": test_sync_handler,
    "test_db": test_db_handler,
}
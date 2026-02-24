"""Модуль для отправки напоминаний о мероприятиях."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from database import get_db_pool
from utils.auditory_names import get_russian_name
import cyrtranslit

logger = logging.getLogger(__name__)


async def find_upcoming_events(minutes_before: int = 35) -> List[Dict[str, Any]]:
    """
    Находит события, которые начнутся через указанное количество минут.
    
    Args:
        minutes_before: количество минут до начала события
        
    Returns:
        Список событий с информацией об ответственных
    """
    pool = get_db_pool()
    
    # Вычисляем временной диапазон: от current_time+25 до current_time+35 минут
    now = datetime.now()
    time_from = now + timedelta(minutes=minutes_before - 10)  # ← было пропущено
    time_to = now + timedelta(minutes=minutes_before)        # ← было пропущено
    
    logger.info(f"Ищем события с {time_from} по {time_to}")
    
    rows = await pool.fetch(
        """
        SELECT 
            ce.id as event_id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            ea.assigned_to,
            u.full_name as engineer_name,
            u.telegram_id
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        LEFT JOIN event_assignments ea ON ce.id = ea.event_id 
            AND ea.status IN ('assigned', 'accepted')
        LEFT JOIN users u ON ea.assigned_to = u.telegram_id
        WHERE ce.start_time BETWEEN $1 AND $2
          AND ce.status = 'confirmed'
        ORDER BY ce.start_time
        """,
        time_from,
        time_to
    )
    
    logger.info(f"Найдено событий: {len(rows)}")
    return [dict(row) for row in rows]


async def send_reminder(event: Dict[str, Any], bot):
    """
    Отправляет напоминание ответственному инженеру.
    
    Args:
        event: словарь с данными о событии
        bot: экземпляр бота для отправки сообщений
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    event_id = event['event_id']
    title = event['title']
    start_time = event['start_time']
    engineer_id = event['telegram_id']
    engineer_name = event['engineer_name'] or 'Инженер'
    
    # Форматируем время
    time_str = start_time.strftime("%H:%M")
    date_str = start_time.strftime("%d.%m")
    
    # Получаем название аудитории
    auditory = get_russian_name(event['auditory_name']) if event['auditory_name'] else "не указана"
    
    # Обратная транслитерация названия
    russian_title = cyrtranslit.to_cyrillic(title)
    
    # Создаём клавиатуру
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтверждаю", callback_data=f"confirm_{event_id}"),
            InlineKeyboardButton("🔄 Ищу замену", callback_data=f"replace_{event_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем сообщение
    await bot.send_message(
        chat_id=engineer_id,
        text=(
            f"🔔 **Напоминание о мероприятии!**\n\n"
            f"📅 **Когда:** {date_str} в {time_str}\n"
            f"📌 **Мероприятие:** {russian_title}\n"
            f"🏢 **Аудитория:** {auditory}\n\n"
            f"Пожалуйста, подтвердите своё участие:"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    # Логируем в таблицу notifications
    await log_notification(event_id, engineer_id, 'reminder')
    
    logger.info(f"Напоминание отправлено {engineer_name} (ID: {engineer_id})")


async def log_notification(event_id: int, user_id: int, notification_type: str):
    """Логирует отправку уведомления в таблицу notifications."""
    pool = get_db_pool()
    await pool.execute(
        """
        INSERT INTO notifications (user_id, event_id, type, sent_at)
        VALUES ($1, $2, $3, NOW())
        """,
        user_id,
        event_id,
        notification_type
    )


async def send_morning_summary(bot):
    """
    Отправляет утреннюю сводку о мероприятиях на сегодня.
    """
    # TODO: реализовать позже
    logger.info("Утренняя сводка будет реализована позже")
    pass


async def send_unconfirmed_report(bot):
    """
    Отправляет отчёт о неподтверждённых назначениях.
    """
    # TODO: реализовать позже
    logger.info("Отчёт о неподтверждённых будет реализован позже")
    pass
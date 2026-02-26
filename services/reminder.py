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
    from config import config
    from datetime import datetime
    import cyrtranslit
    from utils.auditory_names import get_russian_name  # добавить импорт
    
    if not config.GROUP_CHAT_ID:
        logger.warning("GROUP_CHAT_ID не настроен, сводка не будет отправлена")
        return
    
    pool = get_db_pool()
    today = datetime.now().date()
    
    logger.info(f"Формируем утреннюю сводку на {today}")
    
    rows = await pool.fetch(
        """
        SELECT 
            ce.id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building,
            u.full_name as engineer_name,
            u.telegram_id,
            ea.status as assignment_status,
            ea.confirmed_at
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        LEFT JOIN event_assignments ea ON ce.id = ea.event_id 
            AND ea.status IN ('accepted', 'assigned', 'replacing')
        LEFT JOIN users u ON ea.assigned_to = u.telegram_id
        WHERE DATE(ce.start_time) = $1
          AND ce.status = 'confirmed'
        ORDER BY ce.start_time
        """,
        today
    )
    
    if not rows:
        await bot.send_message(
            chat_id=config.GROUP_CHAT_ID,
            message_thread_id=config.TOPIC_ID,
            text="🌅 **Доброе утро!**\n\nНа сегодня мероприятий нет. Хорошего дня! ☀️",
            parse_mode="Markdown"
        )
        logger.info("Утренняя сводка отправлена (мероприятий нет)")
        return
    
    # Формируем сообщение
    message = f"🌅 **Доброе утро!**\n\n📅 **Мероприятия на {today.strftime('%d.%m.%Y')}**\n\n"
    
    for event in rows:
        time_str = event['start_time'].strftime("%H:%M")
        end_time_str = event['end_time'].strftime("%H:%M")
        
        # Обратная транслитерация названия мероприятия
        title = event['title']
        russian_title = cyrtranslit.to_cyrillic(title)
        
        # 🔥 ИСПРАВЛЕНИЕ: русское название аудитории и корпуса
        auditory = 'не указана'
        building = ''
        
        if event['auditory_name']:
            auditory = get_russian_name(event['auditory_name'])
        
        if event.get('building'):
            building = get_russian_name(event['building'])
        
        # Формируем строку с аудиторией
        if auditory != 'не указана' and building:
            location = f"{auditory} ({building})"
        elif auditory != 'не указана':
            location = auditory
        elif building:
            location = f"ауд. не указана ({building})"
        else:
            location = "ауд. не указана"
        
        # Информация об инженере
        engineer = event['engineer_name'] or '❌ не назначен'
        status = event['assignment_status']
        
        # Выбираем иконку в зависимости от статуса
        if status == 'accepted':
            status_icon = "✅"
            status_text = "подтвердил"
        elif status == 'assigned':
            status_icon = "⏳"
            status_text = "ожидает подтверждения"
        elif status == 'replacing':
            status_icon = "🔄"
            status_text = "ищет замену"
        else:
            status_icon = "❌"
            status_text = "не назначен"
        
        message += f"• **{time_str}–{end_time_str}** — {russian_title}\n"
        message += f"  🏢 Ауд. {location}\n"
        message += f"  {status_icon} {engineer} {status_text}\n\n"
    
    # Добавляем статистику
    total = len(rows)
    confirmed = sum(1 for e in rows if e['assignment_status'] == 'accepted')
    pending = sum(1 for e in rows if e['assignment_status'] == 'assigned')
    replacing = sum(1 for e in rows if e['assignment_status'] == 'replacing')
    no_assign = sum(1 for e in rows if not e['assignment_status'])
    
    message += f"📊 **Статистика:**\n"
    message += f"• Всего мероприятий: {total}\n"
    message += f"• ✅ Подтверждено: {confirmed}\n"
    message += f"• ⏳ Ожидают: {pending}\n"
    message += f"• 🔄 Ищут замену: {replacing}\n"
    message += f"• ❌ Не назначены: {no_assign}\n"
    
    await bot.send_message(
        chat_id=config.GROUP_CHAT_ID,
        message_thread_id=config.TOPIC_ID,
        text=message,
        parse_mode="Markdown"
    )
    
    logger.info(f"Утренняя сводка отправлена. Мероприятий: {total}")

async def send_unconfirmed_report(bot):
    """
    Отправляет отчёт о неподтверждённых назначениях.
    """
    # TODO: реализовать позже
    logger.info("Отчёт о неподтверждённых будет реализован позже")
    pass

async def auto_complete_events() -> int:
    """
    Автоматически отмечает как выполненные мероприятия,
    которые закончились более часа назад и не были отмечены вручную.
    
    Returns:
        int: количество обновлённых записей
    """
    pool = get_db_pool()
    
    # Правильный синтаксис: end_time < NOW() - INTERVAL '1 hour'
    result = await pool.execute(
        """
        UPDATE event_assignments 
        SET status = 'done', completed_at = NOW()
        WHERE event_id IN (
            SELECT id FROM calendar_events 
            WHERE end_time < NOW() - INTERVAL '1 hour'
        )
        AND status IN ('accepted', 'assigned')
        """
    )
    
    # Парсим результат, чтобы получить количество обновлённых строк
    # asyncpg возвращает строку типа "UPDATE X"
    import re
    match = re.search(r'UPDATE (\d+)', result)
    count = int(match.group(1)) if match else 0
    
    if count > 0:
        logger.info(f"Автоматически завершено {count} мероприятий")
    
    return count

async def send_completion_reminder(event: Dict[str, Any], bot):
    """Отправляет напоминание о необходимости отметить выполнение."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    event_id = event['event_id']
    title = event['title']
    engineer_id = event['telegram_id']
    engineer_name = event['engineer_name']
    
    russian_title = cyrtranslit.to_cyrillic(title)
    
    keyboard = [
        [InlineKeyboardButton("✅ Отметить выполнение", callback_data=f"complete_{event_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await bot.send_message(
        chat_id=engineer_id,
        text=(
            f"❓ **Мероприятие завершено?**\n\n"
            f"📌 **Мероприятие:** {russian_title}\n\n"
            f"Если вы уже провели мероприятие, отметьте его как выполненное:"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def send_afternoon_report(bot):
    """
    Отправляет дневной отчёт менеджеру о статусах мероприятий.
    """
    from config import config
    
    if not config.GROUP_CHAT_ID:
        return
    
    pool = get_db_pool()
    
    # Получаем статистику за сегодня
    rows = await pool.fetch(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ea.status = 'done' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN ea.status = 'accepted' THEN 1 ELSE 0 END) as confirmed,
            SUM(CASE WHEN ea.status = 'assigned' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN ea.status = 'replacing' THEN 1 ELSE 0 END) as replacing
        FROM event_assignments ea
        JOIN calendar_events ce ON ea.event_id = ce.id
        WHERE DATE(ce.start_time) = CURRENT_DATE
        """
    )
    
    if rows:
        data = rows[0]
        total = data['total'] or 0
        completed = data['completed'] or 0
        confirmed = data['confirmed'] or 0
        pending = data['pending'] or 0
        
        report = (
            f"📊 **Дневной отчёт**\n\n"
            f"📅 **Мероприятий сегодня:** {total}\n"
            f"✅ **Выполнено:** {completed}\n"
            f"👍 **Подтверждено:** {confirmed}\n"
            f"⏳ **Ожидают:** {pending}\n"
        )
        
        await bot.send_message(
            chat_id=config.GROUP_CHAT_ID,
            message_thread_id=config.TOPIC_ID,
            text=report,
            parse_mode="Markdown"
        )
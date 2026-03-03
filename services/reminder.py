"""Модуль для отправки напоминаний о мероприятиях."""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.constants import (
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_ASSIGNED,
    ASSIGNMENT_STATUS_DONE,
    ASSIGNMENT_STATUS_REPLACING,
    NOTIFICATION_COMPLETION_REMINDER,
    NOTIFICATION_REMINDER,
)
from database import get_db_pool
from utils.auditory_names import get_russian_name
from utils.translit import to_cyrillic

logger = logging.getLogger(__name__)


async def find_upcoming_events(minutes_before: int = 35) -> List[Dict[str, Any]]:
    """
    Находит события, которые начнутся через указанное количество минут.
    Отправляем напоминания только тем, у кого статус 'assigned' (ещё не подтвердили)
    И только если мероприятие ещё не завершено никем из инженеров.
    
    Args:
        minutes_before: за сколько минут до начала ищем события (по умолчанию 35)
        
    Returns:
        List[Dict[str, Any]]: Список событий для отправки напоминаний
    """
    pool = get_db_pool()
    
    # Вычисляем временной диапазон: от current_time+25 до current_time+35 минут
    now = datetime.now()
    time_from = now + timedelta(minutes=minutes_before - 10)
    time_to = now + timedelta(minutes=minutes_before)
    
    logger.info(f"Ищем события для напоминаний с {time_from} по {time_to}")
    
    rows = await pool.fetch(
        """
        SELECT 
            ce.id as event_id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building,
            ea.assigned_to,
            u.full_name as engineer_name,
            u.telegram_id,
            ea.status as current_status,
            -- Проверяем, завершено ли мероприятие кем-то из инженеров
            EXISTS (
                SELECT 1 
                FROM event_assignments ea2 
                WHERE ea2.event_id = ce.id 
                  AND ea2.status = 'done'
            ) as is_completed_by_anyone
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        LEFT JOIN event_assignments ea ON ce.id = ea.event_id 
            AND ea.status = 'assigned'  -- Только те, кто ещё не подтвердил
        LEFT JOIN users u ON ea.assigned_to = u.telegram_id
        WHERE ce.start_time BETWEEN $1 AND $2
          AND ce.status = 'confirmed'
          -- Исключаем мероприятия, которые уже кто-то завершил
          AND NOT EXISTS (
              SELECT 1 
              FROM event_assignments ea2 
              WHERE ea2.event_id = ce.id 
                AND ea2.status = 'done'
          )
        ORDER BY ce.start_time
        """,
        time_from,
        time_to
    )
    
    # Фильтруем результаты, оставляя только те, где есть назначенный инженер
    valid_rows = [row for row in rows if row['assigned_to'] is not None]
    
    logger.info(f"Найдено событий для напоминаний: {len(valid_rows)} из {len(rows)}")
    return [dict(row) for row in valid_rows]


async def find_completed_events() -> List[Dict[str, Any]]:
    """
    Находит мероприятия, которые закончились 15-30 минут назад,
    ещё не отмечены как выполненные, и не завершены никем из инженеров.
    Отправляем напоминания только тем, у кого статус 'accepted' (подтвердили, но не завершили).
    
    Returns:
        List[Dict[str, Any]]: Список событий для отправки напоминаний о завершении
    """
    pool = get_db_pool()
    
    now = datetime.now()
    time_from = now - timedelta(minutes=30)
    time_to = now - timedelta(minutes=15)
    
    logger.info(f"Ищем завершённые мероприятия для напоминаний с {time_from} по {time_to}")
    
    rows = await pool.fetch(
        """
        SELECT 
            ce.id as event_id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building,
            ea.assigned_to,
            u.full_name as engineer_name,
            u.telegram_id,
            ea.status as current_status
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        JOIN event_assignments ea ON ce.id = ea.event_id 
            AND ea.status = 'accepted'  -- Только те, кто подтвердил
        JOIN users u ON ea.assigned_to = u.telegram_id
        WHERE ce.end_time BETWEEN $1 AND $2
          AND ce.status = 'confirmed'
          -- Исключаем мероприятия, которые уже кто-то завершил
          AND NOT EXISTS (
              SELECT 1 
              FROM event_assignments ea2 
              WHERE ea2.event_id = ce.id 
                AND ea2.status = 'done'
          )
        ORDER BY ce.end_time
        """,
        time_from,
        time_to
    )
    
    logger.info(f"Найдено завершённых мероприятий для напоминаний: {len(rows)}")
    return [dict(row) for row in rows]


async def is_event_completed(event_id: int) -> bool:
    """
    Проверяет, завершено ли мероприятие кем-либо из инженеров.
    
    Args:
        event_id: ID мероприятия
        
    Returns:
        bool: True если мероприятие уже завершено
    """
    pool = get_db_pool()
    result = await pool.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM event_assignments 
            WHERE event_id = $1 AND status = $2
        )
        """,
        event_id,
        ASSIGNMENT_STATUS_DONE,
    )
    return result


async def can_send_notification(event_id: int, user_id: int, notification_type: str) -> bool:
    """
    Проверяет, можно ли отправить уведомление пользователю по данному событию.
    
    Args:
        event_id: ID мероприятия
        user_id: ID пользователя
        notification_type: тип уведомления ('reminder', 'completion_reminder')
        
    Returns:
        bool: True если уведомление можно отправить
    """
    pool = get_db_pool()
    
    # Проверяем, не завершено ли мероприятие
    if await is_event_completed(event_id):
        logger.info(f"Мероприятие {event_id} уже завершено, уведомление не требуется")
        return False
    
    # Проверяем, не отправляли ли уже такое уведомление за последние 2 часа
    recent = await pool.fetchval(
        """
        SELECT COUNT(*) FROM notifications 
        WHERE event_id = $1 AND user_id = $2 
          AND type = $3 
          AND sent_at > NOW() - INTERVAL '2 hours'
        """,
        event_id,
        user_id,
        notification_type
    )
    
    if recent > 0:
        logger.info(f"Уведомление типа {notification_type} для мероприятия {event_id} уже отправлялось менее 2 часов назад")
        return False
    
    return True


async def send_reminder(event: Dict[str, Any], bot):
    """
    Отправляет напоминание ответственному инженеру.
    Отправляет только если статус назначения 'assigned' (не подтверждён)
    и мероприятие ещё не завершено.
    
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
    
    # 🔍 ПРОВЕРКА 1: Мероприятие ещё не завершено?
    if await is_event_completed(event_id):
        logger.info(f"Мероприятие {event_id} уже завершено, напоминание не отправлено")
        return
    
    # 🔍 ПРОВЕРКА 2: Получаем актуальный статус из БД
    pool = get_db_pool()
    current_status = await pool.fetchval(
        """
        SELECT status FROM event_assignments 
        WHERE event_id = $1 AND assigned_to = $2
        """,
        event_id,
        engineer_id
    )
    
    # Если статус не 'assigned' — не отправляем напоминание
    if current_status != ASSIGNMENT_STATUS_ASSIGNED:
        status_messages = {
            ASSIGNMENT_STATUS_ACCEPTED: f"Инженер {engineer_name} уже подтвердил участие",
            ASSIGNMENT_STATUS_REPLACING: f"Инженер {engineer_name} запросил замену",
            ASSIGNMENT_STATUS_DONE: f"Мероприятие {event_id} уже завершено",
        }
        message = status_messages.get(current_status, f"Мероприятие {event_id} имеет статус {current_status}")
        logger.info(f"{message}, напоминание пропущено")
        return
    
    # 🔍 ПРОВЕРКА 3: Можно ли отправить уведомление (защита от дублирования)
    if not await can_send_notification(event_id, engineer_id, NOTIFICATION_REMINDER):
        return
    
    # Форматируем время
    time_str = start_time.strftime("%H:%M")
    date_str = start_time.strftime("%d.%m")
    
    # Получаем название аудитории
    auditory = get_russian_name(event['auditory_name']) if event['auditory_name'] else "не указана"
    if event.get('building'):
        building = get_russian_name(event['building'])
        auditory += f" ({building})"
    
    # Обратная транслитерация названия
    russian_title = to_cyrillic(title)
    
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
    await log_notification(event_id, engineer_id, NOTIFICATION_REMINDER)
    
    logger.info(f"Напоминание отправлено {engineer_name} (ID: {engineer_id}) для мероприятия {event_id}")


async def send_completion_reminder(event: Dict[str, Any], bot):
    """
    Отправляет напоминание о необходимости отметить выполнение мероприятия.
    Отправляет только если статус 'accepted' и мероприятие ещё не завершено.
    
    Args:
        event: словарь с данными о событии
        bot: экземпляр бота для отправки сообщений
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    event_id = event['event_id']
    title = event['title']
    end_time = event['end_time']
    engineer_id = event['telegram_id']
    engineer_name = event['engineer_name'] or 'Инженер'
    
    # 🔍 ПРОВЕРКА 1: Мероприятие ещё не завершено?
    if await is_event_completed(event_id):
        logger.info(f"Мероприятие {event_id} уже завершено, напоминание о завершении не требуется")
        return
    
    # 🔍 ПРОВЕРКА 2: Получаем актуальный статус
    pool = get_db_pool()
    current_status = await pool.fetchval(
        """
        SELECT status FROM event_assignments 
        WHERE event_id = $1 AND assigned_to = $2
        """,
        event_id,
        engineer_id
    )
    
    # Если статус не 'accepted' — не отправляем
    if current_status != ASSIGNMENT_STATUS_ACCEPTED:
        logger.info(f"Мероприятие {event_id} имеет статус {current_status}, напоминание о завершении пропущено")
        return
    
    # 🔍 ПРОВЕРКА 3: Можно ли отправить уведомление (защита от дублирования)
    if not await can_send_notification(
        event_id,
        engineer_id,
        NOTIFICATION_COMPLETION_REMINDER,
    ):
        return
    
    # Обратная транслитерация
    russian_title = to_cyrillic(title)
    time_str = end_time.strftime("%H:%M")
    date_str = end_time.strftime("%d.%m")
    
    # Получаем аудиторию
    auditory = get_russian_name(event['auditory_name']) if event['auditory_name'] else "не указана"
    if event.get('building'):
        building = get_russian_name(event['building'])
        auditory += f" ({building})"
    
    # Создаём клавиатуру
    keyboard = [
        [InlineKeyboardButton("✅ Отметить выполнение", callback_data=f"complete_{event_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await bot.send_message(
        chat_id=engineer_id,
        text=(
            f"❓ **Мероприятие завершено?**\n\n"
            f"📌 **Мероприятие:** {russian_title}\n"
            f"🕐 **Окончание:** {date_str} в {time_str}\n"
            f"🏢 **Аудитория:** {auditory}\n\n"
            f"Если мероприятие уже проведено, отметьте его как выполненное:"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    # Логируем
    await log_notification(event_id, engineer_id, NOTIFICATION_COMPLETION_REMINDER)
    
    logger.info(f"Напоминание о завершении отправлено {engineer_name} для мероприятия {event_id}")


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


async def auto_complete_events() -> int:
    """
    Автоматически отмечает как выполненные мероприятия,
    которые закончились более часа назад и не были отмечены вручную.
    
    Returns:
        int: количество обновлённых записей
    """
    pool = get_db_pool()
    
    result = await pool.execute(
        """
        UPDATE event_assignments 
        SET status = $1, completed_at = NOW()
        WHERE event_id IN (
            SELECT id FROM calendar_events 
            WHERE end_time < NOW() - INTERVAL '1 hour'
        )
        AND status IN ($2, $3)
        """,
        ASSIGNMENT_STATUS_DONE,
        ASSIGNMENT_STATUS_ACCEPTED,
        ASSIGNMENT_STATUS_ASSIGNED
    )
    
    # Парсим результат, чтобы получить количество обновлённых строк
    match = re.search(r'UPDATE (\d+)', result)
    count = int(match.group(1)) if match else 0
    
    if count > 0:
        logger.info(f"Автоматически завершено {count} мероприятий")
    
    return count


async def send_morning_summary(bot):
    """
    Отправляет утреннюю сводку о мероприятиях на сегодня.
    """
    from config import config
    
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
            ea.confirmed_at,
            -- Проверяем, завершено ли мероприятие
            EXISTS (
                SELECT 1 
                FROM event_assignments ea2 
                WHERE ea2.event_id = ce.id 
                  AND ea2.status = 'done'
            ) as is_completed
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        LEFT JOIN event_assignments ea ON ce.id = ea.event_id 
            AND ea.status IN ('accepted', 'assigned', 'replacing', 'done')
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
        russian_title = to_cyrillic(event['title'])
        
        # Русское название аудитории
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
        if event['is_completed']:
            # Мероприятие уже завершено
            engineer = event['engineer_name'] or 'инженер'
            status_icon = "✅"
            status_text = "завершено"
        else:
            # Мероприятие ещё не завершено
            engineer = event['engineer_name'] or '❌ не назначен'
            status = event['assignment_status']
            
            # Выбираем иконку в зависимости от статуса
            if status == ASSIGNMENT_STATUS_ACCEPTED:
                status_icon = "✅"
                status_text = "подтвердил"
            elif status == ASSIGNMENT_STATUS_ASSIGNED:
                status_icon = "⏳"
                status_text = "ожидает подтверждения"
            elif status == ASSIGNMENT_STATUS_REPLACING:
                status_icon = "🔄"
                status_text = "ищет замену"
            else:
                status_icon = "❌"
                status_text = "не назначен"
        
        message += f"• **{time_str}–{end_time_str}** — {russian_title}\n"
        message += f"  🏢 Ауд. {location}\n"
        
        if event['is_completed']:
            message += f"  {status_icon} {engineer} {status_text}\n\n"
        else:
            message += f"  {status_icon} {engineer} {status_text}\n\n"
    
    # Добавляем статистику
    total = len(rows)
    completed = sum(1 for e in rows if e['is_completed'])
    confirmed = sum(1 for e in rows if not e['is_completed'] and e['assignment_status'] == 'accepted')
    pending = sum(1 for e in rows if not e['is_completed'] and e['assignment_status'] == 'assigned')
    replacing = sum(1 for e in rows if not e['is_completed'] and e['assignment_status'] == 'replacing')
    no_assign = sum(1 for e in rows if not e['is_completed'] and not e['assignment_status'])
    
    message += f"📊 **Статистика:**\n"
    message += f"• Всего мероприятий: {total}\n"
    message += f"• ✅ Завершено: {completed}\n"
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


async def send_afternoon_report(bot):
    """
    Отправляет дневной отчёт менеджеру о статусах мероприятий.
    """
    from config import config
    
    if not config.GROUP_CHAT_ID:
        logger.warning("GROUP_CHAT_ID не настроен, отчёт не будет отправлен")
        return
    
    pool = get_db_pool()
    today = datetime.now().date()
    
    # Получаем статистику за сегодня
    rows = await pool.fetch(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ea.status = 'done' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN ea.status = 'accepted' THEN 1 ELSE 0 END) as confirmed,
            SUM(CASE WHEN ea.status = 'assigned' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN ea.status = 'replacing' THEN 1 ELSE 0 END) as replacing,
            SUM(CASE WHEN ea.status IS NULL THEN 1 ELSE 0 END) as no_assign
        FROM calendar_events ce
        LEFT JOIN event_assignments ea ON ce.id = ea.event_id
            AND ea.status IN ('accepted', 'assigned', 'replacing', 'done')
        WHERE DATE(ce.start_time) = $1
          AND ce.status = 'confirmed'
        """,
        today
    )
    
    if rows:
        data = rows[0]
        total = data['total'] or 0
        completed = data['completed'] or 0
        confirmed = data['confirmed'] or 0
        pending = data['pending'] or 0
        replacing = data['replacing'] or 0
        no_assign = data['no_assign'] or 0
        
        report = (
            f"📊 **Дневной отчёт**\n\n"
            f"📅 **Мероприятий сегодня:** {total}\n"
            f"✅ **Завершено:** {completed}\n"
            f"👍 **Подтверждено:** {confirmed}\n"
            f"⏳ **Ожидают:** {pending}\n"
            f"🔄 **Ищут замену:** {replacing}\n"
            f"❌ **Не назначены:** {no_assign}\n"
        )
        
        await bot.send_message(
            chat_id=config.GROUP_CHAT_ID,
            message_thread_id=config.TOPIC_ID,
            text=report,
            parse_mode="Markdown"
        )
        
        logger.info(f"Дневной отчёт отправлен. Мероприятий: {total}")


async def send_unconfirmed_report(bot):
    """
    Отправляет отчёт о неподтверждённых назначениях.
    """
    # TODO: реализовать позже
    logger.info("Отчёт о неподтверждённых будет реализован позже")
    pass
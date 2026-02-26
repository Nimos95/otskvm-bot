"""Обработчик для инженеров: мои мероприятия и задачи."""

import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import get_db_pool
from utils.auditory_names import get_russian_name
import cyrtranslit

logger = logging.getLogger(__name__)


async def show_my_events(message, user_id: int):
    """
    Показывает инженеру список его мероприятий на сегодня.
    """
    pool = get_db_pool()
    today = datetime.now().date()
    
    # Получаем мероприятия инженера на сегодня
    rows = await pool.fetch(
        """
        SELECT 
            ce.id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building,
            ea.status,
            ea.confirmed_at
        FROM calendar_events ce
        JOIN event_assignments ea ON ce.id = ea.event_id
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE ea.assigned_to = $1
          AND DATE(ce.start_time) = $2
          AND ce.status = 'confirmed'
          AND ea.status IN ('accepted', 'assigned')
        ORDER BY ce.start_time
        """,
        user_id,
        today
    )
    
    if not rows:
        await message.reply_text(
            "📋 **У вас нет мероприятий на сегодня.**\n\n"
            "Хорошего дня! ☀️",
            parse_mode="Markdown"
        )
        return
    
    # Формируем сообщение
    text = f"📋 **Ваши мероприятия на сегодня**\n\n"
    
    keyboard = []
    
    for event in rows:
        event_id = event['id']
        start_time = event['start_time'].strftime("%H:%M")
        end_time = event['end_time'].strftime("%H:%M")
        
        # Обратная транслитерация
        title = event['title']
        russian_title = cyrtranslit.to_cyrillic(title)
        
        # Аудитория
        auditory = get_russian_name(event['auditory_name']) if event['auditory_name'] else "не указана"
        if event.get('building'):
            building = get_russian_name(event['building'])
            auditory += f" ({building})"
        
        # Статус
        status = event['status']
        if status == 'accepted':
            status_icon = "✅"
            status_text = "Подтверждено"
        else:
            status_icon = "⏳"
            status_text = "Ожидает подтверждения"
        
        # Добавляем информацию в текст
        text += f"• **{start_time}–{end_time}** — {russian_title}\n"
        text += f"  🏢 Ауд. {auditory}\n"
        text += f"  {status_icon} {status_text}\n\n"
        
        # Добавляем кнопку досрочного завершения (если мероприятие ещё идёт или уже прошло)
        now = datetime.now()
        if event['end_time'] < now:
            # Уже прошло
            button_text = f"✅ Завершить: {russian_title[:20]}"
        elif event['start_time'] < now < event['end_time']:
            # Идёт сейчас
            button_text = f"⏹️ Завершить досрочно: {russian_title[:20]}"
        else:
            # Ещё не началось
            continue
        
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"engineer_complete_{event_id}"
            )
        ])
    
    if not keyboard:
        text += "_Нет мероприятий, которые можно завершить._"
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
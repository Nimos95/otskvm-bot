"""Обработчик команды /today."""

import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import Database, get_db_pool
from utils.auditory_names import get_russian_name

logger = logging.getLogger(__name__)


async def today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду `/today` и показывает мероприятия на сегодня.

    Сценарий:
        - обновляет `last_active` пользователя;
        - запрашивает мероприятия на текущую дату через `get_events_for_date`;
        - формирует список с указанием времени и аудитории;
        - добавляет кнопки для перехода к завтрашнему дню или неделе.

    Возможные ошибки:
        ⚠️ ВНИМАНИЕ: если синхронизация календаря ещё не выполнялась или
        Google Calendar пуст, пользователь увидит сообщение об отсутствии
        мероприятий, что является нормальным сценарием.
    """
    if not update.effective_user or not update.message:
        return

    telegram_id = update.effective_user.id
    await Database.update_user_last_active(telegram_id)
    
    # Получаем события на сегодня
    events = await get_events_for_date(datetime.now().date())
    
    if not events:
        await update.message.reply_text(
            "📅 На сегодня мероприятий нет.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📆 На завтра", callback_data="tomorrow_schedule")
            ]])
        )
        return
    
    # Формируем сообщение
    message = f"📅 **Мероприятия на {datetime.now().strftime('%d.%m.%Y')}**\n\n"
    
    for event in events:
        time_str = event["start_time"].strftime("%H:%M")
        title = event["title"]
        
        # Добавляем информацию об аудитории, если есть
        if event.get("auditory_name"):
            rus_name = get_russian_name(event["auditory_name"])
            message += f"• **{time_str}** — {title} (ауд. {rus_name})\n"
        else:
            message += f"• **{time_str}** — {title}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📆 Завтра", callback_data="tomorrow_schedule"),
            InlineKeyboardButton("📅 Неделя", callback_data="week_schedule")
        ],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def get_events_for_date(date) -> list:
    """
    Возвращает список событий на указанную дату.

    Аргументы:
        date: объект `date`, для которого нужно получить мероприятия.

    Возвращает:
        Список словарей с полями из `calendar_events` и дополнительным
        полем `auditory_name` (техническое имя аудитории).

    Примечания:
        🔥 ВАЖНО (SQL): выборка:
        - ограничена интервалом [date; date+1 день);
        - фильтрует только подтверждённые события (`ce.status = 'confirmed'`);
        - использует LEFT JOIN с `auditories`, чтобы не терять события
          без привязанной аудитории.
    """
    pool = get_db_pool()
    
    start_date = datetime.combine(date, datetime.min.time())
    end_date = start_date + timedelta(days=1)
    
    rows = await pool.fetch(
        """
        SELECT 
            ce.*,
            a.name as auditory_name
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE ce.start_time >= $1 
          AND ce.start_time < $2
          AND ce.status = 'confirmed'
        ORDER BY ce.start_time
        """,
        start_date,
        end_date
    )
    
    return [dict(row) for row in rows]
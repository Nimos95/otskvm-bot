"""Обработчик назначения ответственных на мероприятия."""

import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import get_db_pool
from utils.auditory_names import get_russian_name

from config import config

from utils.roles import require_roles

import cyrtranslit

logger = logging.getLogger(__name__)

@require_roles(['superadmin', 'manager'])
async def assign_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /assign и кнопки "Назначения".
    Показывает список мероприятий для назначения ответственных.
    """
    if not update.message:
        return
    
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} вызвал /assign")
    
    # Получаем мероприятия на ближайшие 5 дней
    pool = get_db_pool()
    today = datetime.now().date()
    
    # Создаем список дат на количество дней из конфига
    days_range = getattr(config, 'ASSIGN_DAYS_RANGE', 5)
    dates = [today + timedelta(days=i) for i in range(days_range)]
    
    logger.info(f"Ищем мероприятия на даты: {dates}")
    
    # Формируем запрос с динамическим количеством параметров
    placeholders = ','.join([f'${i+1}' for i in range(len(dates))])
    
    rows = await pool.fetch(
        f"""
        SELECT 
            ce.id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE DATE(ce.start_time) IN ({placeholders})
          AND ce.status = 'confirmed'
        ORDER BY ce.start_time
        """,
        *dates
    )
    
    logger.info(f"Найдено мероприятий: {len(rows)}")
    
    if not rows:
        await update.message.reply_text(
            "📅 На ближайшие 5 дней нет мероприятий для назначения."
        )
        return
    
    # Формируем сообщение с кнопками
    text = "📋 **Выберите мероприятие для назначения ответственного:**\n\n"
    
    keyboard = []
    for event in rows:
        event_id = event["id"]
        # Форматируем дату с днём недели для ясности
        date_str = event["start_time"].strftime("%a, %d.%m %H:%M")
        title = event["title"]
        
        # Обратная транслитерация названия мероприятия
        russian_title = cyrtranslit.to_cyrillic(title)
        
        # Получаем русское название аудитории
        auditory = get_russian_name(event["auditory_name"]) if event["auditory_name"] else "нет аудитории"
        building = event["building"] or ""
        location = f"{auditory} {building}".strip()
        
        # Кнопка для выбора мероприятия
        button_text = f"{date_str} — {russian_title}"
        if location:
            button_text += f" ({location})"
        
        # Обрезаем слишком длинные названия
        if len(button_text) > 40:
            button_text = button_text[:37] + "..."
        
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"assign_event_{event_id}"
        )])
    
    # Кнопка "Назад" в главное меню
    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_engineers_for_event(query, event_id):
    """
    Показывает список инженеров для назначения на мероприятие.
    """
    pool = get_db_pool()
    
    # Получаем информацию о мероприятии
    event_row = await pool.fetchrow(
        """
        SELECT 
            ce.title,
            ce.start_time,
            a.name as auditory_name,
            a.building
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE ce.id = $1
        """,
        int(event_id)
    )
    
    if not event_row:
        await query.edit_message_text("Мероприятие не найдено")
        return
    
    # Получаем список инженеров (кто уже назначен — показываем отдельно)
    engineers = await pool.fetch(
        """
        SELECT 
            u.telegram_id,
            u.full_name,
            u.role,
            ea.id as assignment_id,
            ea.status as assignment_status,
            ea.role as assigned_role
        FROM users u
        LEFT JOIN event_assignments ea ON u.telegram_id = ea.assigned_to AND ea.event_id = $1
        WHERE u.role IN ('superadmin', 'engineer', 'admin', 'manager')
        ORDER BY 
            CASE WHEN ea.id IS NOT NULL THEN 0 ELSE 1 END,
            u.full_name
        """,
        int(event_id)
    )
    
    # Форматируем дату
    date_str = event_row["start_time"].strftime("%d.%m.%Y %H:%M")
    
    # Обратная транслитерация названия мероприятия
    title = event_row["title"]
    russian_title = cyrtranslit.to_cyrillic(title)
    
    # Получаем русское название аудитории
    auditory = get_russian_name(event_row["auditory_name"]) if event_row["auditory_name"] else "нет аудитории"
    building = event_row["building"] or ""
    location = f"{auditory} {building}".strip()
    
    text = (
        f"📅 **Мероприятие:** {russian_title}\n"
        f"🕐 **Время:** {date_str}\n"
        f"🏢 **Аудитория:** {location}\n\n"
        f"**Выберите ответственного:**"
    )
    
    keyboard = []
    
    for eng in engineers:
        eng_id = eng["telegram_id"]
        name = eng["full_name"]
        status = eng["assignment_status"] if eng["assignment_status"] else None
        assigned_role = eng["assigned_role"] if eng["assigned_role"] else ""
        
        # Разные иконки для разных статусов
        if status == "accepted":
            btn_text = f"✅ {name} (подтвердил)"
        elif status == "assigned":
            btn_text = f"⏳ {name} (ожидает ответа)"
        elif status == "done":
            btn_text = f"✔️ {name} (выполнил)"
        else:
            btn_text = f"👤 {name}"
        
        keyboard.append([InlineKeyboardButton(
            btn_text,
            callback_data=f"assign_to_{event_id}_{eng_id}"
        )])
    
    # Кнопка для назначения нескольких инженеров
    keyboard.append([InlineKeyboardButton(
        "➕ Назначить нескольких", 
        callback_data=f"assign_multi_{event_id}"
    )])
    
    # Кнопки навигации
    keyboard.append([
        InlineKeyboardButton("« К списку мероприятий", callback_data="assign_list"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def assign_engineer_to_event(query, context, user_id, event_id, engineer_id):
    """
    Назначает инженера на мероприятие.
    """
    pool = get_db_pool()
    
    # Проверяем, не назначен ли уже
    existing = await pool.fetchrow(
        "SELECT id, status FROM event_assignments WHERE event_id = $1 AND assigned_to = $2",
        int(event_id),
        int(engineer_id)
    )
    
    if existing:
        await query.answer("Этот инженер уже назначен на мероприятие", show_alert=True)
        # Показываем обновлённый список
        await show_engineers_for_event(query, event_id)
        return
    
    # Назначаем инженера
    await pool.execute(
        """
        INSERT INTO event_assignments 
        (event_id, assigned_to, assigned_by, role, status, assigned_at)
        VALUES ($1, $2, $3, 'primary', 'assigned', NOW())
        """,
        int(event_id),
        int(engineer_id),
        int(user_id)
    )
    
    await query.answer("✅ Инженер назначен!")
    
    # Получаем информацию для уведомления
    event_info = await pool.fetchrow(
        "SELECT title, start_time FROM calendar_events WHERE id = $1",
        int(event_id)
    )
    
    engineer_info = await pool.fetchrow(
        "SELECT full_name FROM users WHERE telegram_id = $1",
        int(engineer_id)
    )
    
    if event_info and engineer_info:
        date_str = event_info["start_time"].strftime("%d.%m.%Y %H:%M")
        title = event_info["title"]
        russian_title = cyrtranslit.to_cyrillic(title)
        
        # Отправляем уведомление назначенному инженеру
        try:
            # Формируем клавиатуру для подтверждения
            keyboard = [
                [
                    InlineKeyboardButton("✅ Принять", callback_data=f"accept_{event_id}"),
                    InlineKeyboardButton("❌ Отказаться", callback_data=f"decline_{event_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=int(engineer_id),
                text=(
                    f"🔔 **Вам назначено мероприятие!**\n\n"
                    f"📅 **Мероприятие:** {russian_title}\n"
                    f"🕐 **Время:** {date_str}\n\n"
                    f"Пожалуйста, подтвердите участие:"
                ),
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление инженеру {engineer_id}: {e}")
    
    # Показываем обновлённый список
    await show_assign_list(query, context) # ← возвращаемся к списку мероприятий


async def accept_assignment(query, user_id, event_id):
    """
    Инженер принимает назначение.
    """
    pool = get_db_pool()
    
    await pool.execute(
        """
        UPDATE event_assignments 
        SET status = 'accepted', confirmed_at = NOW()
        WHERE event_id = $1 AND assigned_to = $2
        """,
        int(event_id),
        int(user_id)
    )
    
    await query.answer("✅ Назначение принято!")
    await query.edit_message_text(
        "✅ Вы подтвердили участие в мероприятии."
    )

async def show_assign_list(query, context):
    """
    Показывает список мероприятий для назначения (возврат из callback).
    """
    # Получаем pool для запросов к БД
    pool = get_db_pool()
    today = datetime.now().date()
    
    # Получаем те же данные, что и в assign_handler
    days_range = getattr(config, 'ASSIGN_DAYS_RANGE', 5)
    dates = [today + timedelta(days=i) for i in range(days_range)]
    
    placeholders = ','.join([f'${i+1}' for i in range(len(dates))])
    
    rows = await pool.fetch(
        f"""
        SELECT 
            ce.id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE DATE(ce.start_time) IN ({placeholders})
          AND ce.status = 'confirmed'
        ORDER BY ce.start_time
        """,
        *dates
    )
    
    if not rows:
        await query.edit_message_text("📅 На ближайшие дни нет мероприятий для назначения.")
        return
    
    # Формируем сообщение с кнопками
    text = "📋 **Выберите мероприятие для назначения ответственного:**\n\n"
    
    keyboard = []
    for event in rows:
        event_id = event["id"]
        date_str = event["start_time"].strftime("%a, %d.%m %H:%M")
        title = event["title"]
        russian_title = cyrtranslit.to_cyrillic(title)
        
        auditory = get_russian_name(event["auditory_name"]) if event["auditory_name"] else "нет аудитории"
        building = event["building"] or ""
        location = f"{auditory} {building}".strip()
        
        button_text = f"{date_str} — {russian_title}"
        if location:
            button_text += f" ({location})"
        
        if len(button_text) > 40:
            button_text = button_text[:37] + "..."
        
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"assign_event_{event_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Вместо удаления и создания фейкового update — просто редактируем текущее сообщение
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def decline_assignment(query, user_id, event_id):
    """
    Инженер отказывается от назначения.
    """
    pool = get_db_pool()
    
    # Удаляем назначение
    await pool.execute(
        "DELETE FROM event_assignments WHERE event_id = $1 AND assigned_to = $2",
        int(event_id),
        int(user_id)
    )
    
    await query.answer("❌ Вы отказались от участия")
    await query.edit_message_text(
        "❌ Вы отказались от участия в мероприятии."
    )
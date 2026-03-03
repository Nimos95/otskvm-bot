"""Обработчик inline-кнопок."""

import logging
import cyrtranslit
from datetime import datetime, timedelta

from handlers.menu import show_persistent_menu
from services.reminder import log_notification

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.constants import (
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_ASSIGNED,
    ASSIGNMENT_STATUS_DONE,
)
from database import Database, get_db_pool
from repositories.auditories import (
    get_active_auditories,
    get_auditory_name_by_id,
)
from utils.auditory_names import get_russian_name
from utils.translit import to_cyrillic
from handlers.today import get_events_for_date
from handlers import start
from handlers.admin import admin_callbacks

from handlers.help import (
    show_help_menu,
    show_help,
    help_commands_handler,
    help_roles_handler,
    help_statuses_handler,
    help_schedule_handler,
    help_assign_handler,
    help_notifications_handler,
    help_faq_handler
)

from handlers.assign import (
    show_engineers_for_event, assign_engineer_to_event,
    accept_assignment, decline_assignment, show_assign_list,
    show_multi_assign, multi_toggle_handler, multi_confirm_handler
)

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на inline-кнопки."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    await Database.update_user_last_active(user_id)
    
    if data == "list_auditories":
        await show_auditories(query)

    elif data == "schedule_menu":
        await show_schedule_menu(query)

    elif data == "today_schedule":
        await show_today_schedule_calendar(query)

    elif data == "tomorrow_schedule":
        await show_tomorrow_schedule_calendar(query)

    elif data == "week_schedule":
        await show_week_schedule_calendar(query)

    elif data.startswith("aud_"):
        auditory_id = data[4:]
        await show_status_buttons(query, auditory_id, context)

    elif data.startswith("set_"):
        parts = data.split("_")
        if len(parts) >= 3:
            auditory_id = parts[1]
            status = parts[2]
            if status == "green":
                await set_status_from_button(query, context, user_id, auditory_id, status, None)
            else:
                context.user_data["waiting_for"] = {
                    "type": "status_comment",
                    "auditory_id": auditory_id,
                    "status": status,
                    "query": query
                }
                await query.edit_message_text(
                    f"📝 Опишите проблему для статуса **{status.upper()}**:\n\n"
                    "(отправьте текстовое сообщение или /cancel для отмены)",
                    parse_mode="Markdown"
                )

    elif data == "back_to_main":
        await show_persistent_menu(query)

    elif data == "help":
        # Перенаправляем на новое меню помощи
        from handlers.help import show_help_menu
        await show_help_menu(query)

    elif data == "first_start":
        await start.first_start_handler(update, context)

    elif data == "assign_list":
        await show_assign_list(query, context)

    elif data.startswith("assign_event_"):
        event_id = data.split("_")[2]
        await show_engineers_for_event(query, event_id)

    elif data.startswith("assign_to_"):
        parts = data.split("_")
        if len(parts) >= 4:
            event_id = parts[2]
            engineer_id = parts[3]
            await assign_engineer_to_event(query, context, user_id, event_id, engineer_id)

    elif data.startswith("confirm_"):
        event_id = int(data.split("_")[1])
        await confirm_assignment(query, user_id, event_id, context)

    elif data.startswith("replace_"):
        event_id = int(data.split("_")[1])
        await request_replacement(query, user_id, event_id, context)

    elif data.startswith("accept_"):
        event_id = data.split("_")[1]
        await accept_assignment(query, user_id, event_id)

    elif data.startswith("decline_"):
        event_id = data.split("_")[1]
        await decline_assignment(query, user_id, event_id)

    elif data.startswith("complete_"):
        event_id = int(data.split("_")[1])
        await complete_event_manually(query, user_id, event_id, context)

    elif data in admin_callbacks:
        await admin_callbacks[data](update, context)

    elif data == "help_main":
        from handlers.help import show_help_menu
        await show_help_menu(query)

    elif data == "help_commands":
        await help_commands_handler(query)

    elif data == "help_roles":
        await help_roles_handler(query)

    elif data == "help_statuses":
        await help_statuses_handler(query)

    elif data == "help_schedule":
        await help_schedule_handler(query)

    elif data == "help_assign":
        await help_assign_handler(query)

    elif data == "help_notifications":
        await help_notifications_handler(query)

    elif data == "help_faq":
        await help_faq_handler(query)

    elif data.startswith("engineer_complete_"):
        event_id = int(data.split("_")[2])
        await engineer_complete_handler(query, user_id, event_id, context)

    elif data.startswith("assign_multi_"):
        event_id = data.split("_")[2]
        await show_multi_assign(query, context, event_id)

    elif data.startswith("multi_toggle_"):
        parts = data.split("_")
        if len(parts) >= 4:
            event_id = parts[2]
            engineer_id = parts[3]
            await multi_toggle_handler(query, context, user_id, event_id, engineer_id)

    elif data.startswith("multi_confirm_"):
        event_id = data.split("_")[2]
        await multi_confirm_handler(query, context, user_id, event_id)

    else:
        await query.edit_message_text("Неизвестная команда")
    


async def confirm_assignment(query, user_id, event_id, context):
    """Подтверждение участия в мероприятии."""
    pool = get_db_pool()
    
    try:
        # Обновляем статус
        result = await pool.execute(
            """
            UPDATE event_assignments 
            SET status = 'accepted', confirmed_at = NOW()
            WHERE event_id = $1 AND assigned_to = $2
            """,
            event_id,
            user_id
        )
        
        # Логируем
        await log_notification(event_id, user_id, 'confirmation')
        
        # Получаем информацию о мероприятии для уведомления менеджера
        event_info = await pool.fetchrow(
            """
            SELECT 
                ce.title,
                ce.start_time,
                u.full_name as engineer_name
            FROM calendar_events ce
            LEFT JOIN users u ON u.telegram_id = $2
            WHERE ce.id = $1
            """,
            event_id,
            user_id
        )
        
        await query.answer("✅ Участие подтверждено!")
        await query.edit_message_text(
            "✅ Вы подтвердили участие в мероприятии. Спасибо!"
        )
        
        # Уведомляем менеджера
        if event_info:
            await notify_manager_about_confirmation(event_info, user_id, context)
            
    except Exception as e:
        logger.error(f"Ошибка при подтверждении: {e}")
        await query.answer("❌ Произошла ошибка")
        await query.edit_message_text("❌ Не удалось подтвердить участие.")


async def request_replacement(query, user_id, event_id, context):
    """Запрос замены на мероприятие."""
    pool = get_db_pool()
    
    try:
        # Получаем информацию для уведомления с транслитерацией
        event_info = await pool.fetchrow(
            """
            SELECT 
                ce.title,
                ce.start_time,
                u.full_name as engineer_name
            FROM calendar_events ce
            LEFT JOIN users u ON u.telegram_id = $2
            WHERE ce.id = $1
            """,
            event_id,
            user_id
        )
        
        if event_info:
            # Обратная транслитерация названия
            title = event_info['title']
            russian_title = cyrtranslit.to_cyrillic(title)
            event_info = dict(event_info)
            event_info['title'] = russian_title
        
        # Меняем статус на 'replacement_requested'
        await pool.execute(
            """
            UPDATE event_assignments 
            SET status = 'replacement_requested'
            WHERE event_id = $1 AND assigned_to = $2
            """,
            event_id,
            user_id
        )
        
        await query.answer("🔄 Запрос на замену отправлен")
        await query.edit_message_text(
            "🔄 Запрос на замену отправлен руководству.\n"
            "Ожидайте, с вами свяжутся."
        )
        
        # Уведомляем менеджера о необходимости замены
        if event_info:
            await notify_manager_about_replacement(event_info, user_id, context)
            
    except Exception as e:
        logger.error(f"Ошибка при запросе замены: {e}")
        await query.answer("❌ Произошла ошибка")


async def notify_manager_about_confirmation(event_info, user_id, context):
    """Уведомляет менеджера о подтверждении инженера."""
    from config import config
    import cyrtranslit
    
    if not config.GROUP_CHAT_ID:
        return
    
    title = event_info['title']
    # 🔥 ИСПРАВЛЕНИЕ: обратная транслитерация
    russian_title = cyrtranslit.to_cyrillic(title)
    
    time_str = event_info['start_time'].strftime("%d.%m %H:%M")
    engineer_name = event_info['engineer_name']
    
    await context.bot.send_message(
        chat_id=config.GROUP_CHAT_ID,
        message_thread_id=config.TOPIC_ID,
        text=(
            f"✅ **Подтверждение получено**\n\n"
            f"👤 **Инженер:** {engineer_name}\n"
            f"📅 **Мероприятие:** {russian_title}\n"  # ← исправлено
            f"🕐 **Время:** {time_str}\n\n"
            f"Статус подтверждён."
        ),
        parse_mode="Markdown"
    )


async def notify_manager_about_replacement(event_info, user_id, context):
    """Уведомляет менеджера о запросе замены."""
    from config import config
    import cyrtranslit
    
    if not config.GROUP_CHAT_ID:
        return
    
    # Название уже должно быть с транслитерацией
    title = event_info['title']
    russian_title = cyrtranslit.to_cyrillic(title)
    time_str = event_info['start_time'].strftime("%d.%m %H:%M")
    engineer_name = event_info['engineer_name']
    
    # Создаём клавиатуру для быстрого поиска замены
    keyboard = [
        [InlineKeyboardButton("👥 Назначить замену", callback_data="assign_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=config.GROUP_CHAT_ID,
        message_thread_id=config.TOPIC_ID,
        text=(
            f"🔄 **Запрос на замену!**\n\n"
            f"👤 **Инженер:** {engineer_name}\n"
            f"📅 **Мероприятие:** {russian_title}\n"
            f"🕐 **Время:** {time_str}\n\n"
            f"Требуется срочно найти замену!"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def complete_event_manually(query, user_id, event_id, context):
    """Ручное завершение мероприятия инженером."""
    pool = get_db_pool()
    
    try:
        # Проверяем, что инженер действительно назначен на это мероприятие
        assignment = await pool.fetchrow(
            """
            SELECT status FROM event_assignments 
            WHERE event_id = $1 AND assigned_to = $2
            """,
            event_id,
            user_id
        )
        
        if not assignment:
            await query.answer("❌ Вы не назначены на это мероприятие", show_alert=True)
            return
        
        # Обновляем статус
        await pool.execute(
            """
            UPDATE event_assignments 
            SET status = 'done', completed_at = NOW()
            WHERE event_id = $1 AND assigned_to = $2
            """,
            event_id,
            user_id
        )
        
        # Логируем
        await log_notification(event_id, user_id, 'manual_completion')
        
        await query.answer("✅ Мероприятие отмечено как выполненное!")
        await query.edit_message_text(
            "✅ Вы отметили мероприятие как выполненное.\n"
            "Спасибо за работу!"
        )
        
        # Уведомляем менеджера
        await notify_manager_about_completion(event_id, user_id, context)
        
    except Exception as e:
        logger.error(f"Ошибка при ручном завершении: {e}")
        await query.answer("❌ Произошла ошибка")

async def notify_manager_about_completion(event_id, user_id, context):
    """Уведомляет менеджера о завершении мероприятия."""
    from config import config
    
    if not config.GROUP_CHAT_ID:
        return
    
    pool = get_db_pool()
    
    # Получаем информацию о мероприятии и инженере
    info = await pool.fetchrow(
        """
        SELECT 
            ce.title,
            ce.start_time,
            u.full_name as engineer_name
        FROM calendar_events ce
        LEFT JOIN users u ON u.telegram_id = $2
        WHERE ce.id = $1
        """,
        event_id,
        user_id
    )
    
    if info:
        title = info['title']
        russian_title = cyrtranslit.to_cyrillic(title)
        time_str = info['start_time'].strftime("%d.%m %H:%M")
        engineer_name = info['engineer_name']
        
        await context.bot.send_message(
            chat_id=config.GROUP_CHAT_ID,
            message_thread_id=config.TOPIC_ID,
            text=(
                f"✅ **Мероприятие выполнено**\n\n"
                f"👤 **Инженер:** {engineer_name}\n"
                f"📅 **Мероприятие:** {russian_title}\n"
                f"🕐 **Время:** {time_str}\n\n"
                f"Статус: выполнено"
            ),
            parse_mode="Markdown"
        )


async def show_main_menu(query):
    """Показывает главное меню."""
    keyboard = [
        [InlineKeyboardButton("📋 Список аудиторий", callback_data="list_auditories")],
        [InlineKeyboardButton("📅 Расписание", callback_data="schedule_menu")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )


async def show_help(query):
    """Показывает справку."""
    keyboard = [
        [InlineKeyboardButton("📋 Список аудиторий", callback_data="list_auditories")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📌 **Доступные команды:**\n"
        "/start — главное меню\n"
        "/status <аудитория> <статус> — быстро отметить статус\n\n"
        "**Статусы:**\n"
        "🟢 green — всё работает\n"
        "🟡 yellow — есть проблемы\n"
        "🔴 red — не работает\n\n"
        "Используйте кнопки для навигации.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_schedule_menu(query):
    """Показывает меню расписания."""
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="today_schedule")],
        [InlineKeyboardButton("📆 Завтра", callback_data="tomorrow_schedule")],
        [InlineKeyboardButton("📅 Неделя", callback_data="week_schedule")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 **Расписание мероприятий**\n\n"
        "Выберите период:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_today_schedule_calendar(query):
    """Показывает расписание на сегодня."""
    from handlers.today import get_events_for_date
    
    today = datetime.now().date()
    events = await get_events_for_date(today)
    
    if not events:
        keyboard = [
            [InlineKeyboardButton("📆 Завтра", callback_data="tomorrow_schedule")],
            [InlineKeyboardButton("« Назад", callback_data="schedule_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📅 **Сегодня ({today.strftime('%d.%m.%Y')})**\n\n"
            f"На сегодня мероприятий нет.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    message = f"📅 **Мероприятия на сегодня ({today.strftime('%d.%m.%Y')})**\n\n"
    
    for event in events:
        time_str = event["start_time"].strftime("%H:%M")
        en_title = event["title"]
        ru_title = to_cyrillic(en_title)
        
        if event.get("auditory_name"):
            rus_name = get_russian_name(event["auditory_name"])
            message += f"• **{time_str}** — {ru_title} (ауд. {rus_name})\n"
        else:
            message += f"• **{time_str}** — {ru_title}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📆 Завтра", callback_data="tomorrow_schedule"),
            InlineKeyboardButton("📅 Неделя", callback_data="week_schedule")
        ],
        [InlineKeyboardButton("« К выбору периода", callback_data="schedule_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_tomorrow_schedule_calendar(query):
    """Показывает расписание на завтра."""
    from handlers.today import get_events_for_date
    
    tomorrow = datetime.now().date() + timedelta(days=1)
    events = await get_events_for_date(tomorrow)
    
    if not events:
        keyboard = [
            [InlineKeyboardButton("📅 Сегодня", callback_data="today_schedule")],
            [InlineKeyboardButton("📅 Неделя", callback_data="week_schedule")],
            [InlineKeyboardButton("« Назад", callback_data="schedule_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📆 **Завтра ({tomorrow.strftime('%d.%m.%Y')})**\n\n"
            f"На завтра мероприятий нет.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    message = f"📆 **Мероприятия на завтра ({tomorrow.strftime('%d.%m.%Y')})**\n\n"
    
    for event in events:
        time_str = event["start_time"].strftime("%H:%M")
        en_title = event["title"]
        ru_title = to_cyrillic(en_title)
        
        if event.get("auditory_name"):
            rus_name = get_russian_name(event["auditory_name"])
            message += f"• **{time_str}** — {ru_title} (ауд. {rus_name})\n"
        else:
            message += f"• **{time_str}** — {ru_title}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📅 Сегодня", callback_data="today_schedule"),
            InlineKeyboardButton("📅 Неделя", callback_data="week_schedule")
        ],
        [InlineKeyboardButton("« К выбору периода", callback_data="schedule_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_week_schedule_calendar(query):
    """Показывает расписание на неделю."""
    from handlers.today import get_events_for_date
    
    today = datetime.now().date()
    events_by_day = {}
    
    for i in range(7):
        date = today + timedelta(days=i)
        events = await get_events_for_date(date)
        if events:
            events_by_day[date] = events
    
    if not events_by_day:
        keyboard = [
            [InlineKeyboardButton("📅 Сегодня", callback_data="today_schedule")],
            [InlineKeyboardButton("📆 Завтра", callback_data="tomorrow_schedule")],
            [InlineKeyboardButton("« Назад", callback_data="schedule_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📅 **Неделя ({today.strftime('%d.%m')} - {(today+timedelta(days=6)).strftime('%d.%m.%Y')})**\n\n"
            f"На эту неделю мероприятий нет.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    message = f"📅 **Мероприятия на неделю ({today.strftime('%d.%m')} - {(today+timedelta(days=6)).strftime('%d.%m.%Y')})**\n\n"
    
    for date in sorted(events_by_day.keys()):
        day_str = date.strftime("%a, %d.%m")
        message += f"**{day_str}:**\n"
        
        for event in events_by_day[date]:
            time_str = event["start_time"].strftime("%H:%M")
            en_title = event["title"]
            ru_title = to_cyrillic(en_title)
            
            if event.get("auditory_name"):
                rus_name = get_russian_name(event["auditory_name"])
                message += f"  • {time_str} — {ru_title} (ауд. {rus_name})\n"
            else:
                message += f"  • {time_str} — {ru_title}\n"
        message += "\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📅 Сегодня", callback_data="today_schedule"),
            InlineKeyboardButton("📆 Завтра", callback_data="tomorrow_schedule")
        ],
        [InlineKeyboardButton("« К выбору периода", callback_data="schedule_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_auditories(query):
    """Показывает список аудиторий с русскими названиями на кнопках."""
    rows = await get_active_auditories()

    if not rows:
        await query.edit_message_text("В базе нет аудиторий")
        return
    
    keyboard = []
    row_buttons = []
    for i, row_data in enumerate(rows):
        aud_id = row_data["id"]
        eng_name = row_data["name"]
        rus_name = get_russian_name(eng_name)
        
        row_buttons.append(InlineKeyboardButton(rus_name, callback_data=f"aud_{aud_id}"))
        
        if len(row_buttons) == 2 or i == len(rows) - 1:
            keyboard.append(row_buttons)
            row_buttons = []
    
    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Выберите аудиторию:",
        reply_markup=reply_markup
    )


async def show_status_buttons(query, auditory_id, context):
    """Показывает кнопки выбора статуса и текущее состояние аудитории."""
    name = await get_auditory_name_by_id(int(auditory_id))
    if not name:
        await query.edit_message_text("Аудитория не найдена")
        return
    
    eng_name = name
    rus_name = get_russian_name(eng_name)
    
    last_status = await Database.get_latest_status(int(auditory_id))
    
    status_text = ""
    if last_status:
        status_emoji = {
            "green": "🟢",
            "yellow": "🟡",
            "red": "🔴",
        }.get(last_status["status"], "⚪")
        status_time = last_status["created_at"].strftime("%d.%m.%Y %H:%M")
        status_text = f"\n\n**Текущий статус:** {status_emoji} {last_status['status'].upper()}\n_Обновлено: {status_time}_"
        if last_status.get("comment"):
            status_text += f"\n_Комментарий: {last_status['comment']}_"
    
    keyboard = [
        [
            InlineKeyboardButton("🟢 Работает", callback_data=f"set_{auditory_id}_green"),
            InlineKeyboardButton("🟡 Проблемы", callback_data=f"set_{auditory_id}_yellow"),
        ],
        [
            InlineKeyboardButton("🔴 Не работает", callback_data=f"set_{auditory_id}_red"),
        ],
        [InlineKeyboardButton("« Назад к списку", callback_data="list_auditories")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    new_text = f"Аудитория: **{rus_name}**{status_text}\n\nВыберите новый статус:"
    
    try:
        await query.edit_message_text(
            new_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ Статус уже актуален")
        else:
            logger.error(f"Ошибка при обновлении: {e}")


async def set_status_from_button(query, context, user_id, auditory_id, status, comment):
    """Устанавливает статус через кнопку."""
    pool = get_db_pool()
    row = await pool.fetchrow("SELECT name FROM auditories WHERE id = $1", int(auditory_id))
    if not row:
        await query.edit_message_text("Аудитория не найдена")
        return
    
    eng_name = row["name"]
    rus_name = get_russian_name(eng_name)
    full_name = query.from_user.full_name or query.from_user.first_name or "Пользователь"
    
    await Database.add_user(telegram_id=user_id, full_name=full_name, username=query.from_user.username)
    
    success = await Database.add_status(
        telegram_id=user_id,
        auditory_name=eng_name,
        status=status,
        comment=comment
    )
    
    if success:
        status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(status, "")
        
        from config import config
        if config.GROUP_CHAT_ID and config.TOPIC_ID:
            try:
                message = f"🔄 {full_name} обновил статус {rus_name}: {status_emoji} {status.upper()}"
                if comment:
                    message += f"\n📝 Комментарий: {comment}"
                
                await context.bot.send_message(
                    chat_id=config.GROUP_CHAT_ID,
                    message_thread_id=config.TOPIC_ID,
                    text=message
                )
            except Exception as e:
                logger.error("Не удалось отправить уведомление в топик: %s", e)
        
        await show_status_buttons(query, auditory_id, context)
    else:
        await query.edit_message_text(
            "❌ Не удалось добавить статус",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад", callback_data=f"aud_{auditory_id}")]
            ])
        )

async def engineer_complete_handler(query, user_id, event_id, context):
    """
    Обработчик досрочного завершения из списка мероприятий инженера.
    """
    pool = get_db_pool()
    
    try:
        # Проверяем, что инженер назначен на это мероприятие
        assignment = await pool.fetchrow(
            """
            SELECT status FROM event_assignments 
            WHERE event_id = $1 AND assigned_to = $2
            """,
            event_id,
            user_id
        )
        
        if not assignment:
            await query.answer("❌ Вы не назначены на это мероприятие", show_alert=True)
            return
        
        # Обновляем статус
        await pool.execute(
            """
            UPDATE event_assignments 
            SET status = 'done', completed_at = NOW()
            WHERE event_id = $1 AND assigned_to = $2
            """,
            event_id,
            user_id
        )
        
        # Логируем
        await log_notification(event_id, user_id, 'early_completion')
        
        await query.answer("✅ Мероприятие завершено досрочно!")
        
        # Обновляем сообщение, убирая кнопку
        await query.edit_message_text(
            query.message.text + "\n\n✅ **Мероприятие завершено досрочно!**",
            parse_mode="Markdown"
        )
        
        # Уведомляем менеджера
        await notify_manager_about_early_completion(event_id, user_id, context)
        
    except Exception as e:
        logger.error(f"Ошибка при досрочном завершении: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def notify_manager_about_early_completion(event_id, user_id, context):
    """Уведомляет менеджера о досрочном завершении."""
    from config import config
    
    if not config.GROUP_CHAT_ID:
        return
    
    pool = get_db_pool()
    
    info = await pool.fetchrow(
        """
        SELECT 
            ce.title,
            ce.start_time,
            ce.end_time,
            u.full_name as engineer_name
        FROM calendar_events ce
        LEFT JOIN users u ON u.telegram_id = $2
        WHERE ce.id = $1
        """,
        event_id,
        user_id
    )
    
    if info:
        title = info['title']
        russian_title = cyrtranslit.to_cyrillic(title)
        end_time = info['end_time'].strftime("%H:%M")
        engineer_name = info['engineer_name']
        
        await context.bot.send_message(
            chat_id=config.GROUP_CHAT_ID,
            message_thread_id=config.TOPIC_ID,
            text=(
                f"⏱️ **Досрочное завершение**\n\n"
                f"👤 **Инженер:** {engineer_name}\n"
                f"📅 **Мероприятие:** {russian_title}\n"
                f"🕐 **Планировалось до:** {end_time}\n\n"
                f"Завершено досрочно!"
            ),
            parse_mode="Markdown"
        )
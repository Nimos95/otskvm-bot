"""Обработчик для справки и помощи."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from database import Database

logger = logging.getLogger(__name__)

async def show_help_menu(query):
    """Показывает главное меню справки (для callback)."""
    keyboard = [
        [InlineKeyboardButton("📋 Команды бота", callback_data="help_commands")],
        [InlineKeyboardButton("👥 Роли и права", callback_data="help_roles")],
        [InlineKeyboardButton("🟢 Статусы аудиторий", callback_data="help_statuses")],
        [InlineKeyboardButton("📅 Расписание", callback_data="help_schedule")],
        [InlineKeyboardButton("👥 Назначения", callback_data="help_assign")],
        [InlineKeyboardButton("🔔 Уведомления", callback_data="help_notifications")],
        [InlineKeyboardButton("❓ Частые вопросы", callback_data="help_faq")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📚 **Справка по боту OTSKVM**\n\n"
        "Выберите интересующий вас раздел:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_help(message):
    """
    Показывает главное меню справки.
    """
    keyboard = [
        [InlineKeyboardButton("📋 Команды бота", callback_data="help_commands")],
        [InlineKeyboardButton("👥 Роли и права", callback_data="help_roles")],
        [InlineKeyboardButton("🟢 Статусы аудиторий", callback_data="help_statuses")],
        [InlineKeyboardButton("📅 Расписание", callback_data="help_schedule")],
        [InlineKeyboardButton("👥 Назначения", callback_data="help_assign")],
        [InlineKeyboardButton("🔔 Уведомления", callback_data="help_notifications")],
        [InlineKeyboardButton("❓ Частые вопросы", callback_data="help_faq")],
        [InlineKeyboardButton("« Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "📚 **Справка по боту OTSKVM**\n\n"
        "Выберите интересующий вас раздел:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def help_commands_handler(query):
    """Показывает список команд."""
    text = (
        "📋 **Команды бота**\n\n"
        "**Основные команды:**\n"
        "• `/start` — главное меню\n"
        "• `/help` — эта справка\n"
        "• `/cancel` — отмена текущего действия\n\n"
        
        "**Статусы аудиторий:**\n"
        "• `/status <аудитория> <статус> [комментарий]` — быстро отметить статус\n"
        "  Пример: `/status 118 green`\n"
        "  Пример: `/status Г3.56 yellow Проектор моргает`\n\n"
        
        "**Расписание:**\n"
        "• `/today` — мероприятия на сегодня\n\n"
        
        "**Назначения (для менеджеров):**\n"
        "• `/assign` — назначить ответственных на мероприятия\n\n"
        
        "**Административные (только superadmin):**\n"
        "• `/setrole @username role` — изменить роль пользователя\n"
        "  Доступные роли: superadmin, admin, manager, engineer, viewer"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="help_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def help_roles_handler(query):
    """Показывает информацию о ролях."""
    text = (
        "👥 **Роли пользователей**\n\n"
        "**👑 superadmin** — разработчик\n"
        "• Полный доступ ко всем функциям\n"
        "• Управление ролями (/setrole)\n"
        "• Админ-панель\n\n"
        
        "**📊 admin** — руководство (начальник управления, проджект-менеджер)\n"
        "• Просмотр статистики\n"
        "• Просмотр дашбордов\n"
        "• Не может изменять данные\n\n"
        
        "**📋 manager** — начальник отдела\n"
        "• Назначение ответственных\n"
        "• Создание задач\n"
        "• Просмотр статистики отдела\n"
        "• Отметка статусов аудиторий\n\n"
        
        "**🔧 engineer** — инженер\n"
        "• Отметка статусов аудиторий\n"
        "• Подтверждение назначений\n"
        "• Просмотр своих задач\n"
        "• Работа с расписанием\n\n"
        
        "**👁️ viewer** — наблюдатель\n"
        "• Только просмотр (статусы, расписание)\n"
        "• Без возможности изменений"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="help_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def help_statuses_handler(query):
    """Показывает информацию о статусах."""
    text = (
        "🟢 **Статусы аудиторий**\n\n"
        "**🟢 green** — всё работает\n"
        "• Оборудование исправно\n"
        "• Мероприятие можно проводить\n\n"
        
        "**🟡 yellow** — есть проблемы\n"
        "• Частичные неполадки\n"
        "• Требуется внимание\n"
        "• Бот запросит комментарий\n\n"
        
        "**🔴 red** — не работает\n"
        "• Серьёзные проблемы\n"
        "• Требуется срочное вмешательство\n"
        "• Бот запросит комментарий\n\n"
        
        "**Как отмечать статус:**\n"
        "• Через кнопки в меню «Аудитории»\n"
        "• Командой `/status`\n"
        "  Пример: `/status 118 red Проектор не включается`"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="help_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def help_schedule_handler(query):
    """Показывает информацию о расписании."""
    text = (
        "📅 **Расписание мероприятий**\n\n"
        "**Команда `/today`**\n"
        "Показывает мероприятия на сегодня с кнопками:\n"
        "• «Завтра» — мероприятия на следующий день\n"
        "• «Неделя» — сводка на 7 дней\n\n"
        
        "**Интеграция с Google Calendar**\n"
        "• Бот автоматически синхронизируется с календарём каждые 6 часов\n"
        "• События привязываются к аудиториям\n"
        "• Названия транслитерируются для хранения\n\n"
        
        "**Утренняя сводка**\n"
        "• Каждый день в 9:00 бот присылает список мероприятий на сегодня\n"
        "• Показывает, кто назначен ответственным\n"
        "• Статистика подтверждений"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="help_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def help_assign_handler(query):
    """Показывает информацию о назначениях."""
    text = (
        "👥 **Назначение ответственных**\n\n"
        "**Кто может назначать:**\n"
        "• Менеджеры (начальники отделов)\n"
        "• Суперадмины\n\n"
        
        "**Как назначить:**\n"
        "1. Нажмите кнопку «Назначения» в меню\n"
        "2. Выберите мероприятие из списка\n"
        "3. Выберите инженера\n"
        "4. Инженер получит уведомление\n\n"
        
        "**Статусы назначений:**\n"
        "• `assigned` — назначен, ожидает подтверждения\n"
        "• `accepted` — подтверждён инженером\n"
        "• `replacing` — запрошена замена\n"
        "• `done` — мероприятие проведено\n\n"
        
        "**Уведомления:**\n"
        "• Инженер получает личное сообщение с кнопками\n"
        "• Менеджер видит подтверждения в общем чате\n"
        "• Напоминание приходит за 30 минут"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="help_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def help_notifications_handler(query):
    """Показывает информацию об уведомлениях."""
    text = (
        "🔔 **Система уведомлений**\n\n"
        "**Напоминания:**\n"
        "• За 30 минут до мероприятия\n"
        "• Приходят ответственному инженеру\n"
        "• Кнопки «Подтверждаю» и «Ищу замену»\n\n"
        
        "**Подтверждение:**\n"
        "• Инженер нажимает «Подтверждаю»\n"
        "• Менеджер видит уведомление в чате\n"
        "• Статус меняется на `accepted`\n\n"
        
        "**Замена:**\n"
        "• Инженер нажимает «Ищу замену»\n"
        "• Менеджер получает срочное уведомление\n"
        "• Требуется назначить нового инженера\n\n"
        
        "**Автоматическое завершение:**\n"
        "• Через час после окончания\n"
        "• Статус меняется на `done`\n"
        "• Можно завершить вручную"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="help_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def help_faq_handler(query):
    """Часто задаваемые вопросы."""
    text = (
        "❓ **Частые вопросы**\n\n"
        "**1. Не приходит уведомление о назначении**\n"
        "• Проверьте, что вы есть в списке инженеров\n"
        "• Убедитесь, что у вас правильная роль (`engineer`)\n"
        "• Напишите в чат отдела\n\n"
        
        "**2. Не могу отметить статус аудитории**\n"
        "• Проверьте название аудитории\n"
        "• Используйте кнопки для выбора\n"
        "• Убедитесь, что у вас есть права (`engineer` или `manager`)\n\n"
        
        "**3. Не вижу мероприятий в /today**\n"
        "• Проверьте, есть ли события в календаре\n"
        "• Синхронизация происходит каждые 6 часов\n"
        "• Можно принудительно запустить через админ-панель\n\n"
        
        "**4. Как сменить роль?**\n"
        "• Только `superadmin` может менять роли\n"
        "• Команда `/setrole @username role`\n"
        "• Напишите разработчику\n\n"
        
        "**5. Бот не отвечает**\n"
        "• Проверьте подключение к интернету\n"
        "• Напишите в чат отдела — возможно, ведутся работы"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="help_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
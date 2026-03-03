"""Обработчики постоянного меню в топике.

Задачи модуля:
- формировать главное меню в зависимости от роли пользователя;
- отображать это меню как reply‑клавиатуру в чате/топике;
- маршрутизировать нажатия на кнопки меню в соответствующие обработчики
  (аудитории, расписание, назначения, помощь, админ‑панель и т.д.).
"""

import logging

from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import ContextTypes

from handlers.auditories import show_auditories
from handlers.schedule import show_schedule_menu
from handlers.help import show_help

logger = logging.getLogger(__name__)



async def get_main_menu_keyboard(user_id: int):
    """Возвращает клавиатуру в зависимости от роли пользователя.

    ⚠️ ВНИМАНИЕ: ниже в файле есть более новая версия этой функции с расширенным
    набором кнопок. В runtime именно она переопределяет текущую реализацию.
    Сохранена для совместимости/истории правок.
    """
    from database import Database
    
    user = await Database.get_user(user_id)
    role = user.get('role', 'engineer') if user else 'engineer'
    
    # Базовое меню для всех
    keyboard = [
        [KeyboardButton("📋 Аудитории")],
        [KeyboardButton("📅 Расписание"), KeyboardButton("❓ Помощь")]
    ]
    
    # Для менеджеров добавляем назначения
    if role in ['superadmin', 'admin', 'manager']:
        keyboard.insert(1, [KeyboardButton("👥 Назначения")])
    
    # Для superadmin добавляем админ-панель
    if role in ['superadmin', 'manager']:
        keyboard.append([KeyboardButton("🛠 Админ-панель")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


async def show_persistent_menu(update_or_query):
    """
    Показывает постоянное меню (работает и с сообщениями, и с callback).

    Сценарий:
        1. Определяет `user_id` из разных типов входных объектов (`Update`, `CallbackQuery`, Chat).
        2. Строит клавиатуру с учётом роли пользователя.
        3. Отправляет сообщение «Главное меню» подходящим способом (reply или send_message).

    Аргументы:
        update_or_query: объект Telegram (`Update`, `CallbackQuery` или `Chat`).

    Возможные ошибки:
        ⚠️ ВНИМАНИЕ: при невозможности определить `user_id` в лог пишется ошибка,
        но исключение не выбрасывается, чтобы не прерывать другие сценарии.
    """
    # Получаем user_id из разных типов объектов
    if hasattr(update_or_query, 'from_user'):
        user_id = update_or_query.from_user.id
    elif hasattr(update_or_query, 'effective_user'):
        user_id = update_or_query.effective_user.id
    else:
        user_id = None
    
    if not user_id:
        logger.error("Не удалось определить user_id")
        return
    
    # ВАЖНО: добавляем await!
    keyboard = await get_main_menu_keyboard(user_id)
    
    try:
        # Проверяем тип объекта и отправляем сообщение правильным способом
        if hasattr(update_or_query, 'message') and hasattr(update_or_query, 'callback_query'):
            # Это callback query
            await update_or_query.message.reply_text(
                "🤖 **Главное меню**\n\n"
                "Выберите действие:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        elif hasattr(update_or_query, 'message'):
            # Это update с сообщением
            await update_or_query.message.reply_text(
                "🤖 **Главное меню**\n\n"
                "Выберите действие:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        elif hasattr(update_or_query, 'effective_chat'):
            # Это update без message, но с чатом
            await update_or_query.effective_chat.send_message(
                "🤖 **Главное меню**\n\n"
                "Выберите действие:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            # Пробуем отправить как есть (может быть Chat)
            await update_or_query.send_message(
                "🤖 **Главное меню**\n\n"
                "Выберите действие:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        logger.info(f"Постоянное меню отображено для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при показе меню: {e}")


async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатия на кнопки постоянного меню (reply‑клавиатура).

    Сценарий:
        - по тексту нажатой кнопки определяет, какое действие выполнить:
          показать аудитории, расписание, назначения, помощь, админ‑панель,
          личные мероприятия инженера или обновить меню.

    Аргументы:
        update: объект `Update` с текстовым сообщением.
        context: контекст Telegram‑бота.

    Возможные ошибки:
        ⚠️ ВНИМАНИЕ: для некоторых действий (например, «Назначения») хендлер
        импортирует и вызывает другие обработчики внутри функции. Это сделано
        для избежания циклических импортов, но важно учитывать при рефакторинге.
    """
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    user_id = update.effective_user.id

    
    logger.info(f"Пользователь {user_id} нажал кнопку: {text}")
    
    if text == "📋 Аудитории":
        await show_auditories(update.message)
        
    elif text == "📅 Расписание":
        await show_schedule_menu(update.message)

    elif text == "👥 Назначения":
        from handlers.assign import assign_handler
    # Создаём фейковый update с командой /assign
        await assign_handler(update, context)
        
    elif text == "❓ Помощь":
        await show_help(update.message)

    elif text == "🛠 Админ-панель":
        logger.info("Вызвана админ-панель")
        from handlers.admin import admin_panel_handler
        await admin_panel_handler(update, context)

    elif text == "📋 Мои мероприятия":
        from handlers.engineer_tasks import show_my_events
        await show_my_events(update.message, user_id)

    elif text == "🔄 Обновить меню":
        logger.info(f"Пользователь {user_id} обновляет меню")
        await show_persistent_menu(update)

async def get_main_menu_keyboard(user_id: int):
    """
    Возвращает клавиатуру главного меню в зависимости от роли пользователя.

    Аргументы:
        user_id: Telegram ID пользователя.

    Возвращает:
        Объект `ReplyKeyboardMarkup` с набором кнопок для данного пользователя.

    Примечания:
        🔥 ВАЖНО: меню строится на основе роли из таблицы `users`:
        - инженеры видят свои мероприятия;
        - менеджеры и superadmin дополнительно видят раздел назначений и админ‑панель;
        - для всех добавлена кнопка «Обновить меню» для пересборки клавиатуры
          после изменения ролей.
    """
    from database import Database
    
    user = await Database.get_user(user_id)
    role = user.get('role', 'engineer') if user else 'engineer'
    
    # Базовое меню для всех
    keyboard = [
        [KeyboardButton("📋 Аудитории")],
        [KeyboardButton("📅 Расписание"), KeyboardButton("❓ Помощь")]
    ]
    
    # 🔥 ДЛЯ ИНЖЕНЕРОВ И НАЧАЛЬНИКА: добавляем раздел с их мероприятиями
    if role in ['superadmin', 'manager', 'engineer']:
        keyboard.insert(1, [KeyboardButton("📋 Мои мероприятия")])
    
    # Для менеджеров добавляем назначения
    if role in ['superadmin', 'manager']:
        keyboard.insert(1, [KeyboardButton("👥 Назначения")])
    
    # Для superadmin добавляем админ-панель
    if role in ['superadmin', 'manager']:
        keyboard.append([KeyboardButton("🛠 Админ-панель")])

    # 🔥 ДЛЯ ВСЕХ: кнопка обновления меню
    keyboard.append([KeyboardButton("🔄 Обновить меню")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
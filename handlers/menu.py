"""Обработчик постоянного меню в топике."""

import logging

from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import ContextTypes

from handlers.auditories import show_auditories
from handlers.schedule import show_schedule_menu
from handlers.help import show_help

logger = logging.getLogger(__name__)



async def get_main_menu_keyboard(user_id: int):
    """Возвращает клавиатуру в зависимости от роли пользователя."""
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
    if role == 'superadmin':
        keyboard.append([KeyboardButton("🛠 Админ-панель")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


async def show_persistent_menu(update_or_query):
    """
    Показывает постоянное меню (работает и с сообщениями, и с callback).
    
    Args:
        update_or_query: Update.message или CallbackQuery
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
    Обрабатывает нажатия на кнопки постоянного меню.
    
    Args:
        update: объект обновления от Telegram
        context: контекст бота
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

async def get_main_menu_keyboard(user_id: int):
    """Возвращает клавиатуру в зависимости от роли пользователя."""
    from database import Database
    
    user = await Database.get_user(user_id)
    role = user.get('role', 'engineer') if user else 'engineer'
    
    # Базовое меню для всех
    keyboard = [
        [KeyboardButton("📋 Аудитории")],
        [KeyboardButton("📅 Расписание"), KeyboardButton("❓ Помощь")]
    ]
    
    # Для менеджеров добавляем назначения
    if role in ['superadmin', 'manager']:
        keyboard.insert(1, [KeyboardButton("👥 Назначения")])
    
    # Для superadmin добавляем админ-панель
    if role == 'superadmin':
        keyboard.append([KeyboardButton("🛠 Админ-панель")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
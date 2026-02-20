"""Обработчик постоянного меню в топике."""

import logging

from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import ContextTypes

from handlers.auditories import show_auditories
from handlers.schedule import show_schedule_menu
from handlers.help import show_help

logger = logging.getLogger(__name__)



def get_main_menu_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📋 Аудитории")],
            [KeyboardButton("📅 Расписание"), KeyboardButton("👥 Назначения")],  # ← добавили
            [KeyboardButton("❓ Помощь")]
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Меню бота"
    )
    return keyboard


async def show_persistent_menu(update_or_query):
    """
    Показывает постоянное меню (работает и с сообщениями, и с callback).
    
    Args:
        update_or_query: Update.message или CallbackQuery
    """
    keyboard = get_main_menu_keyboard()
    
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
            
        logger.info("Постоянное меню отображено")
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

        # Отладка
    print(f"🔥 Нажата кнопка: {text}")
    await update.message.reply_text(f"Обработчик сработал! Кнопка: {text}")
    
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
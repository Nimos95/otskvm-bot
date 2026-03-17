"""
Основной файл VK бота
"""

import os
from dotenv import load_dotenv
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from loguru import logger

# Подключаем наши модули
from database import Database
import vk_utils as utils

# Загружаем токен из .env
load_dotenv()
VK_TOKEN = os.getenv("VK_TOKEN")

# Создаём экземпляр бота
bot = Bot(VK_TOKEN)

# ============================================
# ОБРАБОТЧИКИ ДЛЯ ЛИЧНЫХ СООБЩЕНИЙ
# ============================================

@bot.on.private_message(text="start")
async def start_handler(message: Message):
    """Обработчик команды start"""
    user_id = message.from_id
    logger.info(f"Пользователь {user_id} запустил бота")
    
    keyboard = (
        Keyboard()
        .add(Text("📋 Мои мероприятия"), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Text("📅 Сегодня"), color=KeyboardButtonColor.SECONDARY)
        .add(Text("📊 Статусы"), color=KeyboardButtonColor.SECONDARY)
        .row()
        .add(Text("❓ Помощь"), color=KeyboardButtonColor.NEGATIVE)
    )
    
    await message.answer(
        "👋 **Добро пожаловать в OTSKVM Бот!**\n\n"
        "Я помогу вам отслеживать мероприятия и статусы аудиторий.\n"
        "Выберите действие в меню ниже:",
        keyboard=keyboard
    )

@bot.on.private_message(text="📋 Мои мероприятия")
async def my_events_handler(message: Message):
    """Показывает мероприятия инженера"""
    user_id = message.from_id
    logger.info(f"Пользователь {user_id} запросил свои мероприятия")
    
    # TODO: добавить запрос к БД
    await message.answer(
        "📋 **Ваши мероприятия на сегодня:**\n\n"
        "Пока нет мероприятий. Эта функциональность в разработке."
    )

@bot.on.private_message(text="📅 Сегодня")
async def today_handler(message: Message):
    """Мероприятия на сегодня"""
    await message.answer(
        "📅 **Мероприятия на сегодня:**\n\n"
        "Раздел в разработке."
    )

@bot.on.private_message(text="📊 Статусы")
async def status_handler(message: Message):
    """Статусы аудиторий"""
    await message.answer(
        "📊 **Статусы аудиторий:**\n\n"
        "Раздел в разработке."
    )

@bot.on.private_message(text="❓ Помощь")
async def help_handler(message: Message):
    """Справка"""
    await message.answer(
        "❓ **Помощь по боту**\n\n"
        "📋 Мои мероприятия — ваши назначенные мероприятия\n"
        "📅 Сегодня — все мероприятия на сегодня\n"
        "📊 Статусы — текущие статусы аудиторий\n\n"
        "Разработка ведётся активно, скоро появятся новые функции!"
    )

@bot.on.private_message()
async def fallback_handler(message: Message):
    """Обработчик неизвестных команд"""
    await message.answer(
        "❌ Неизвестная команда. Напишите 'start' для начала работы."
    )

# ============================================
# ОБРАБОТЧИК ДЛЯ ЧАТОВ (МОЛЧИМ)
# ============================================

@bot.on.chat_message()
async def chat_message_handler(message: Message):
    """Игнорируем все сообщения в чатах"""
    logger.debug(f"Сообщение в чате {message.peer_id} проигнорировано")
    return

# ============================================
# ЗАПУСК БОТА (УПРОЩЁННЫЙ ВАРИАНТ)
# ============================================

if __name__ == "__main__":
    import asyncio
    
    # Создаём событийный цикл
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Подключаемся к БД
    loop.run_until_complete(Database.connect())
    logger.info("🔥 VK бот запускается...")
    
    try:
        # Запускаем бота
        bot.run_forever()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    finally:
        # Отключаемся от БД
        loop.run_until_complete(Database.disconnect())
        loop.close()
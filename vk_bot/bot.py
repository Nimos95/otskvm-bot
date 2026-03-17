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

@bot.on.message(text="start")
async def start_handler(message: Message):
    """Обработчик команды start"""
    user_id = message.from_id
    logger.info(f"Пользователь {user_id} запустил бота")
    
    # Создаём клавиатуру
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

@bot.on.message(text="📋 Мои мероприятия")
async def my_events_handler(message: Message):
    """Показывает мероприятия инженера"""
    user_id = message.from_id
    logger.info(f"Пользователь {user_id} запросил свои мероприятия")
    
    # TODO: добавить запрос к БД
    await message.answer(
        "📋 **Ваши мероприятия на сегодня:**\n\n"
        "Пока нет мероприятий. Эта функциональность в разработке."
    )

@bot.on.message(text="📅 Сегодня")
async def today_handler(message: Message):
    """Мероприятия на сегодня"""
    await message.answer(
        "📅 **Мероприятия на сегодня:**\n\n"
        "Раздел в разработке."
    )

@bot.on.message(text="📊 Статусы")
async def status_handler(message: Message):
    """Статусы аудиторий"""
    await message.answer(
        "📊 **Статусы аудиторий:**\n\n"
        "Раздел в разработке."
    )

@bot.on.message(text="❓ Помощь")
async def help_handler(message: Message):
    """Справка"""
    await message.answer(
        "❓ **Помощь по боту**\n\n"
        "📋 Мои мероприятия — ваши назначенные мероприятия\n"
        "📅 Сегодня — все мероприятия на сегодня\n"
        "📊 Статусы — текущие статусы аудиторий\n\n"
        "Разработка ведётся активно, скоро появятся новые функции!"
    )

@bot.on.message()
async def echo_handler(message: Message):
    """Обработчик неизвестных команд"""
    await message.answer(
        "❌ Неизвестная команда. Напишите start для начала работы."
    )

# 🔥 ПРАВИЛЬНЫЙ СПОСОБ ДЛЯ VKBOTTLE 4.x [citation:2]
async def startup():
    """Действия при запуске бота"""
    logger.info("🚀 VK бот запускается...")
    await Database.connect()
    logger.info("✅ VK бот готов к работе")

async def shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 VK бот останавливается...")
    await Database.disconnect()
    logger.info("👋 VK бот остановлен")

# Добавляем функции в списки on_startup и on_shutdown
bot.loop_wrapper.on_startup.append(startup())
bot.loop_wrapper.on_shutdown.append(shutdown())

if __name__ == "__main__":
    # Запускаем бота [citation:2]
    bot.run_forever()
"""Обработчик текстовых сообщений без команд.

Задачи модуля:
- обрабатывать пользовательский текст в контексте ожидаемого шага диалога
  (например, ввод комментария к статусу аудитории);
- реагировать на команду `/cancel`, введённую как обычный текст;
- не вмешиваться в обычную переписку, если бот ничего не «ждёт» от пользователя.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import Database, get_db_pool
from utils.auditory_names import get_russian_name

logger = logging.getLogger(__name__)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает текстовые сообщения пользователя.

    Сценарии:
        1. Если в `context.user_data["waiting_for"]` лежит ожидание комментария
           к статусу аудитории, текст воспринимается как комментарий и записывается
           в `status_log`, после чего пользователю показываются варианты продолжения.
        2. Если пользователь отправляет `/cancel` как обычный текст, снимается
           текущее ожидание и приходит подтверждение отмены.

    Аргументы:
        update: объект `Update` с текстовым сообщением.
        context: контекст Telegram‑бота (хранит состояние `waiting_for`).

    Возможные ошибки:
        ⚠️ ВНИМАНИЕ: если к этому моменту аудитория была удалена или ID некорректен,
        пользователь получит сообщение «Аудитория не найдена», а состояние
        ожидания будет сброшено, чтобы не застревать в сломанном шаге.
    """
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    waiting_for = context.user_data.get("waiting_for")
    
    if waiting_for and waiting_for.get("type") == "status_comment":
        auditory_id = waiting_for["auditory_id"]
        status = waiting_for["status"]
        original_query = waiting_for.get("query")
        
        context.user_data["waiting_for"] = None
        
        pool = get_db_pool()
        row = await pool.fetchrow("SELECT name FROM auditories WHERE id = $1", int(auditory_id))
        if not row:
            await update.message.reply_text("Аудитория не найдена")
            return
        
        eng_name = row["name"]
        rus_name = get_russian_name(eng_name)
        full_name = update.effective_user.full_name or update.effective_user.first_name or "Пользователь"
        
        success = await Database.add_status(
            telegram_id=user_id,
            auditory_name=eng_name,
            status=status,
            comment=text
        )
        
        if success:
            status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(status, "")
            
            from config import config
            if config.GROUP_CHAT_ID and config.TOPIC_ID:
                try:
                    await context.bot.send_message(
                        chat_id=config.GROUP_CHAT_ID,
                        message_thread_id=config.TOPIC_ID,
                        text=f"🔄 {full_name} обновил статус {rus_name}: {status_emoji} {status.upper()}\n"
                             f"📝 Комментарий: {text}"
                    )
                except Exception as e:
                    logger.error("Не удалось отправить уведомление в топик: %s", e)
            
            keyboard = [
                [InlineKeyboardButton("📋 К списку аудиторий", callback_data="list_auditories")],
                [InlineKeyboardButton("🔄 К этой аудитории", callback_data=f"aud_{auditory_id}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Статус аудитории **{rus_name}** обновлён: {status_emoji} {status.upper()}\n"
                f"📝 Комментарий: {text}\n\n"
                f"Что делаем дальше?",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            keyboard = [
                [InlineKeyboardButton("🔄 К аудитории", callback_data=f"aud_{auditory_id}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ Не удалось добавить статус. Попробуйте снова.",
                reply_markup=reply_markup
            )
        
    elif text == "/cancel":
        if context.user_data.get("waiting_for"):
            context.user_data["waiting_for"] = None
            await update.message.reply_text("❌ Действие отменено")
        else:
            await update.message.reply_text("Нет активного действия для отмены")
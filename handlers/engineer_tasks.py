"""Обработчик для инженеров: мои мероприятия и задачи."""

import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from database import get_db_pool
from utils.auditory_names import get_russian_name
import cyrtranslit

logger = logging.getLogger(__name__)

# Состояние для ConversationHandler (ввод причины отмены)
CANCEL_REASON = 1


async def show_my_events(message, user_id: int):
    """
    Показывает инженеру список его мероприятий на сегодня.
    """
    pool = get_db_pool()
    today = datetime.now().date()
    
    # Получаем мероприятия инженера на сегодня
    rows = await pool.fetch(
        """
        SELECT 
            ce.id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building,
            ea.status,
            ea.confirmed_at
        FROM calendar_events ce
        JOIN event_assignments ea ON ce.id = ea.event_id
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE ea.assigned_to = $1
          AND DATE(ce.start_time) = $2
          AND ce.status = 'confirmed'
          AND ea.status IN ('accepted', 'assigned')
        ORDER BY ce.start_time
        """,
        user_id,
        today
    )
    
    if not rows:
        await message.reply_text(
            "📋 **У вас нет мероприятий на сегодня.**\n\n"
            "Хорошего дня! ☀️",
            parse_mode="Markdown"
        )
        return
    
    # Формируем сообщение
    text = f"📋 **Ваши мероприятия на сегодня**\n\n"
    
    keyboard = []
    
    for event in rows:
        event_id = event['id']
        start_time = event['start_time'].strftime("%H:%M")
        end_time = event['end_time'].strftime("%H:%M")
        
        # Обратная транслитерация
        title = event['title']
        russian_title = cyrtranslit.to_cyrillic(title)
        
        # Аудитория
        auditory = get_russian_name(event['auditory_name']) if event['auditory_name'] else "не указана"
        if event.get('building'):
            building = get_russian_name(event['building'])
            auditory += f" ({building})"
        
        # Статус
        status = event['status']
        if status == 'accepted':
            status_icon = "✅"
            status_text = "Подтверждено"
        else:
            status_icon = "⏳"
            status_text = "Ожидает подтверждения"
        
        # Добавляем информацию в текст
        text += f"• **{start_time}–{end_time}** — {russian_title}\n"
        text += f"  🏢 Ауд. {auditory}\n"
        text += f"  {status_icon} {status_text}\n\n"
        
        # КНОПКИ для мероприятия
        event_buttons = []
        
        # Кнопка завершения (если мероприятие идёт или прошло)
        now = datetime.now()
        if event['start_time'] < now:
            if now < event['end_time']:
                # Идёт сейчас
                event_buttons.append(
                    InlineKeyboardButton(
                        f"⏹️ Завершить досрочно",
                        callback_data=f"engineer_complete_{event_id}"
                    )
                )
            elif event['end_time'] < now:
                # Уже прошло
                event_buttons.append(
                    InlineKeyboardButton(
                        f"✅ Завершить",
                        callback_data=f"engineer_complete_{event_id}"
                    )
                )
        
        # 🔴 КНОПКА ОТМЕНЫ для всех мероприятий (кроме уже завершённых)
        event_buttons.append(
            InlineKeyboardButton(
                f"❌ Отменить",
                callback_data=f"engineer_cancel_{event_id}"
            )
        )
        
        # Добавляем кнопки для этого мероприятия в общую клавиатуру
        if event_buttons:
            keyboard.append(event_buttons)
    
    if not keyboard:
        text += "_Нет мероприятий, которые можно завершить или отменить._"
        reply_markup = None
    else:
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def cancel_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало процесса отмены мероприятия.
    Запрашивает причину отмены.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID мероприятия
    try:
        event_id = int(query.data.split('_')[2])  # engineer_cancel_123
    except (IndexError, ValueError):
        await query.edit_message_text("❌ Ошибка: некорректный ID мероприятия")
        return ConversationHandler.END
    
    # Сохраняем ID в контекст
    context.user_data['cancelling_event_id'] = event_id
    
    # Получаем информацию о мероприятии
    pool = get_db_pool()
    event = await pool.fetchrow(
        """
        SELECT ce.title
        FROM calendar_events ce
        WHERE ce.id = $1
        """,
        event_id
    )
    
    title = cyrtranslit.to_cyrillic(event['title']) if event else "Неизвестное мероприятие"
    
    await query.edit_message_text(
        f"❓ **Отмена мероприятия**\n\n"
        f"Мероприятие: *{title}*\n\n"
        f"Пожалуйста, напишите причину отмены:\n"
        f"• Мероприятие отменили организаторы\n"
        f"• Технические проблемы\n"
        f"• Конфликт расписания\n"
        f"• Другая причина\n\n"
        f"Или отправьте /cancel чтобы отменить действие.",
        parse_mode="Markdown"
    )
    
    return CANCEL_REASON


async def cancel_event_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Получает причину отмены и обрабатывает отмену мероприятия.
    """
    user_id = update.effective_user.id
    reason = update.message.text.strip()
    
    if not reason or len(reason) < 3:
        await update.message.reply_text(
            "❌ Слишком короткая причина. Пожалуйста, опишите подробнее (минимум 3 символа)."
        )
        return CANCEL_REASON
    
    event_id = context.user_data.get('cancelling_event_id')
    if not event_id:
        await update.message.reply_text("❌ Ошибка: не найден ID мероприятия")
        return ConversationHandler.END
    
    pool = get_db_pool()
    
    try:
        # Получаем информацию о мероприятии и инженере
        event_info = await pool.fetchrow(
            """
            SELECT 
                ce.title,
                ce.start_time,
                ce.end_time,
                u.full_name as engineer_name,
                u.telegram_id as engineer_id,
                a.name as auditory_name
            FROM calendar_events ce
            JOIN event_assignments ea ON ce.id = ea.event_id
            JOIN users u ON ea.assigned_to = u.telegram_id
            LEFT JOIN auditories a ON ce.auditory_id = a.id
            WHERE ce.id = $1 AND ea.assigned_to = $2
            """,
            event_id, user_id
        )
        
        if not event_info:
            await update.message.reply_text("❌ Мероприятие не найдено")
            return ConversationHandler.END
        
        # 1. Обновляем статус в event_assignments
        await pool.execute(
            """
            UPDATE event_assignments 
            SET status = 'cancelled'
            WHERE event_id = $1 AND assigned_to = $2
            """,
            event_id, user_id
        )
        
        # 2. Записываем в cancellation_log
        await pool.execute(
            """
            INSERT INTO cancellation_log 
            (event_id, cancelled_by, cancelled_at, source, reason, notification_sent)
            VALUES ($1, $2, NOW(), $3, $4, $5)
            """,
            event_id, user_id, 'bot', reason, False
        )
        
        # 3. Отменяем также другие назначения на это мероприятие (если есть)
        await pool.execute(
            """
            UPDATE event_assignments 
            SET status = 'cancelled'
            WHERE event_id = $1 AND status IN ('assigned', 'accepted')
            """,
            event_id
        )
        
        # Получаем русские названия
        russian_title = cyrtranslit.to_cyrillic(event_info['title'])
        auditory = get_russian_name(event_info['auditory_name']) if event_info['auditory_name'] else "Не указана"
        
        # Получаем список менеджеров для уведомлений
        managers = await pool.fetch(
            "SELECT telegram_id FROM users WHERE role IN ('manager', 'superadmin')"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отмене мероприятия {event_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при отмене мероприятия. Пожалуйста, сообщите администратору."
        )
        return ConversationHandler.END
    
    # Определяем контекст отмены
    now = datetime.now()
    if now < event_info['start_time']:
        cancel_context = "до начала"
    elif event_info['start_time'] <= now <= event_info['end_time']:
        cancel_context = "во время проведения"
    else:
        cancel_context = "после завершения"
    
    # Формируем сообщение для менеджера
    manager_text = (
        f"🚨 **Мероприятие ОТМЕНЕНО**\n\n"
        f"👤 Инженер: {event_info['engineer_name']}\n"
        f"📅 Мероприятие: {russian_title}\n"
        f"📍 Аудитория: {auditory}\n"
        f"⏰ Время: {event_info['start_time'].strftime('%d.%m.%Y %H:%M')}\n"
        f"🕐 Отмена: {cancel_context}\n"
        f"❓ Причина: {reason}\n\n"
        f"⚠️ Мероприятие не состоялось."
    )
    
    # Отправляем уведомления менеджерам
    notification_sent = False
    for manager in managers:
        try:
            await context.bot.send_message(
                chat_id=manager['telegram_id'],
                text=manager_text,
                parse_mode="Markdown"
            )
            notification_sent = True
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление менеджеру {manager['telegram_id']}: {e}")
    
    # Обновляем флаг notification_sent
    if notification_sent:
        await pool.execute(
            """
            UPDATE cancellation_log 
            SET notification_sent = TRUE 
            WHERE event_id = $1 AND cancelled_by = $2
            """,
            event_id, user_id
        )
    
    # Подтверждаем инженеру
    await update.message.reply_text(
        f"✅ Мероприятие *{russian_title}* отменено.\n"
        f"Причина сохранена. Уведомление отправлено начальнику.",
        parse_mode="Markdown"
    )
    
    # Очищаем контекст
    context.user_data.pop('cancelling_event_id', None)
    
    return ConversationHandler.END


async def cancel_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена действия (выход из ConversationHandler)."""
    await update.message.reply_text("❌ Действие отменено.")
    return ConversationHandler.END


async def complete_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик завершения мероприятия (обычного или досрочного).
    """
    query = update.callback_query
    await query.answer()
    
    try:
        event_id = int(query.data.split('_')[2])  # engineer_complete_123
    except (IndexError, ValueError):
        await query.edit_message_text("❌ Ошибка: некорректный ID мероприятия")
        return
    
    user_id = query.from_user.id
    pool = get_db_pool()
    
    # Проверяем, что мероприятие принадлежит пользователю
    event = await pool.fetchrow(
        """
        SELECT 
            ce.title,
            ce.start_time,
            ce.end_time,
            ea.status
        FROM event_assignments ea
        JOIN calendar_events ce ON ea.event_id = ce.id
        WHERE ea.event_id = $1 AND ea.assigned_to = $2
        """,
        event_id, user_id
    )
    
    if not event:
        await query.edit_message_text("❌ Мероприятие не найдено")
        return
    
    if event['status'] != 'accepted':
        await query.edit_message_text("❌ Можно завершить только подтверждённые мероприятия")
        return
    
    # Отмечаем как выполненное
    await pool.execute(
        """
        UPDATE event_assignments 
        SET status = 'done', completed_at = NOW()
        WHERE event_id = $1 AND assigned_to = $2
        """,
        event_id, user_id
    )
    
    # Получаем русское название
    russian_title = cyrtranslit.to_cyrillic(event['title'])
    
    # Определяем тип завершения
    now = datetime.now()
    if now < event['end_time']:
        completion_type = "досрочно"
    else:
        completion_type = ""
    
    await query.edit_message_text(
        f"✅ Мероприятие *{russian_title}* завершено {completion_type}!\n"
        f"Спасибо за работу!",
        parse_mode="Markdown"
    )
    
    # Уведомляем менеджеров
    managers = await pool.fetch("SELECT telegram_id FROM users WHERE role IN ('manager', 'superadmin')")
    for manager in managers:
        try:
            await context.bot.send_message(
                chat_id=manager['telegram_id'],
                text=f"✅ {query.from_user.full_name} завершил мероприятие *{russian_title}*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить менеджера {manager['telegram_id']}: {e}")


def register_handlers(app):
    """
    Регистрирует обработчики для engineer_tasks.
    """
    # Обработчик для кнопки "Мои мероприятия"
    # (вызывается из menu.py)
    
    # ConversationHandler для отмены мероприятия
    cancel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cancel_event_start, pattern=r'^engineer_cancel_\d+$')],
        states={
            CANCEL_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_event_reason)],
        },
        fallbacks=[CommandHandler('cancel', cancel_event)],
    )
    
    app.add_handler(cancel_conv)
    
    # Обработчик завершения мероприятия
    app.add_handler(CallbackQueryHandler(complete_event, pattern=r'^engineer_complete_\d+$'))
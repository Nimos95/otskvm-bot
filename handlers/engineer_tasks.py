"""Обработчик для инженеров: мои мероприятия и задачи."""

import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database import get_db_pool
from utils.auditory_names import get_russian_name
from utils.translit import to_cyrillic

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SELECTING_ACTION = 1
CANCEL_REASON = 2


async def show_my_events(message, user_id: int):
    """
    ШАГ 1: Показывает инженеру список его мероприятий на сегодня
    с кнопками для выбора мероприятия.
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
    
    # Формируем текст с общим списком
    text = "📋 **Ваши мероприятия на сегодня:**\n\n"
    
    keyboard = []
    
    for i, event in enumerate(rows, 1):
        event_id = event['id']
        start_time = event['start_time'].strftime("%H:%M")
        end_time = event['end_time'].strftime("%H:%M")
        
        # Обратная транслитерация
        title = event['title']
        russian_title = to_cyrillic(title)
        
        # Аудитория
        auditory = get_russian_name(event['auditory_name']) if event['auditory_name'] else "не указана"
        
        # Статус
        status_icon = "✅" if event['status'] == 'accepted' else "⏳"
        
        # Добавляем в текст
        text += f"{i}. {status_icon} **{start_time}–{end_time}** — {russian_title}\n"
        text += f"   🏢 {auditory}\n\n"
        
        # Кнопка для выбора мероприятия (сокращённое название)
        button_text = f"{i}. {russian_title[:30]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"event_select_{event_id}")])
    
    # Добавляем кнопку "Назад" в главное меню
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def event_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ШАГ 2: Показывает действия для выбранного мероприятия.
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID мероприятия
    try:
        event_id = int(query.data.split('_')[2])  # event_select_123
    except (IndexError, ValueError):
        await query.edit_message_text("❌ Ошибка: некорректный ID мероприятия")
        return
    
    user_id = query.from_user.id
    pool = get_db_pool()
    
    # Получаем детальную информацию о мероприятии
    event = await pool.fetchrow(
        """
        SELECT 
            ce.id,
            ce.title,
            ce.start_time,
            ce.end_time,
            ce.description,
            a.name as auditory_name,
            a.building,
            ea.status,
            ea.confirmed_at
        FROM calendar_events ce
        JOIN event_assignments ea ON ce.id = ea.event_id
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE ce.id = $1 AND ea.assigned_to = $2
        """,
        event_id, user_id
    )
    
    if not event:
        await query.edit_message_text("❌ Мероприятие не найдено")
        return
    
    # Сохраняем ID в контекст для следующих шагов
    context.user_data['selected_event_id'] = event_id
    
    # Форматируем время
    start = event['start_time'].strftime("%d.%m.%Y %H:%M")
    end = event['end_time'].strftime("%H:%M")
    
    # Транслитерация
    russian_title = to_cyrillic(event['title'])
    auditory = get_russian_name(event['auditory_name']) if event['auditory_name'] else "не указана"
    if event.get('building'):
        building = get_russian_name(event['building'])
        auditory += f" ({building})"
    
    # Детальная информация
    text = (
        f"📌 **{russian_title}**\n\n"
        f"📍 **Аудитория:** {auditory}\n"
        f"⏰ **Время:** {start} – {end}\n"
        f"📊 **Статус:** {'✅ Подтверждено' if event['status'] == 'accepted' else '⏳ Ожидает подтверждения'}\n"
    )
    
    if event['description']:
        desc = to_cyrillic(event['description'])
        text += f"📝 **Описание:** {desc}\n"
    
    text += f"\n**Выберите действие:**"
    
    # Кнопки действий в зависимости от ситуации
    keyboard = []
    now = datetime.now()
    
    # Кнопка завершения (если мероприятие идёт или прошло)
    if event['start_time'] < now:
        if now < event['end_time']:
            # Идёт сейчас
            keyboard.append([InlineKeyboardButton("⏹️ Завершить досрочно", callback_data="event_complete")])
        elif event['end_time'] < now:
            # Уже прошло
            keyboard.append([InlineKeyboardButton("✅ Отметить выполненным", callback_data="event_complete")])
    
    # Кнопка отмены (для всех случаев)
    keyboard.append([InlineKeyboardButton("❌ Отменить мероприятие", callback_data="event_cancel")])
    
    # Кнопка назад к списку
    keyboard.append([InlineKeyboardButton("◀️ К списку", callback_data="my_tasks")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return SELECTING_ACTION


async def event_complete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик завершения мероприятия.
    При завершении одним инженером - автоматически завершает за всех остальных.
    """
    query = update.callback_query
    await query.answer()
    
    event_id = context.user_data.get('selected_event_id')
    if not event_id:
        await query.edit_message_text("❌ Ошибка: не выбран ID мероприятия")
        return ConversationHandler.END
    
    user_id = query.from_user.id
    pool = get_db_pool()
    
    # Начинаем транзакцию для целостности данных
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Проверяем мероприятие и получаем информацию о нём
            event = await conn.fetchrow(
                """
                SELECT 
                    ce.title,
                    ce.start_time,
                    ce.end_time,
                    ea.status,
                    (SELECT COUNT(*) FROM event_assignments 
                     WHERE event_id = ce.id AND status IN ('assigned', 'accepted')) as total_active
                FROM event_assignments ea
                JOIN calendar_events ce ON ea.event_id = ce.id
                WHERE ea.event_id = $1 AND ea.assigned_to = $2
                """,
                event_id, user_id
            )
            
            if not event:
                await query.edit_message_text("❌ Мероприятие не найдено")
                return ConversationHandler.END
            
            if event['status'] != 'accepted':
                await query.edit_message_text("❌ Можно завершить только подтверждённые мероприятия")
                return ConversationHandler.END
            
            # Русское название для уведомлений
            russian_title = to_cyrillic(event['title'])
            
            # 1. Помечаем текущего инженера как выполнившего
            await conn.execute(
                """
                UPDATE event_assignments 
                SET status = 'done', completed_at = NOW()
                WHERE event_id = $1 AND assigned_to = $2
                """,
                event_id, user_id
            )
            
            # 2. Находим ВСЕХ других инженеров, назначенных на это мероприятие
            other_engineers = await conn.fetch(
                """
                SELECT 
                    u.telegram_id,
                    u.full_name
                FROM event_assignments ea
                JOIN users u ON ea.assigned_to = u.telegram_id
                WHERE ea.event_id = $1 
                  AND ea.assigned_to != $2
                  AND ea.status IN ('assigned', 'accepted')
                """,
                event_id, user_id
            )
            
            other_count = len(other_engineers) if other_engineers else 0
            
            # 3. Если есть другие инженеры - автоматически завершаем за них
            if other_engineers:
                await conn.execute(
                    """
                    UPDATE event_assignments 
                    SET status = 'done', completed_at = NOW()
                    WHERE event_id = $1 AND assigned_to != $2
                      AND status IN ('assigned', 'accepted')
                    """,
                    event_id, user_id
                )
                
                # 4. Отправляем уведомления остальным инженерам
                completer_name = query.from_user.full_name
                for eng in other_engineers:
                    try:
                        await context.bot.send_message(
                            chat_id=eng['telegram_id'],
                            text=(
                                f"👥 *Мероприятие автоматически завершено*\n\n"
                                f"📅 *{russian_title}*\n"
                                f"✅ Завершил: {completer_name}\n\n"
                                f"Вы автоматически отмечены как выполнивший задачу.\n"
                                f"Спасибо за работу!"
                            ),
                            parse_mode="Markdown"
                        )
                        logger.info(f"Уведомление отправлено инженеру {eng['telegram_id']} о автоматическом завершении")
                    except Exception as e:
                        logger.error(f"Не удалось уведомить инженера {eng['telegram_id']}: {e}")
            
            # Определяем тип завершения для основного пользователя
            now = datetime.now()
            if now < event['end_time']:
                completion_type = "досрочно"
                completion_emoji = "⏱️"
            else:
                completion_type = ""
                completion_emoji = "✅"
            
            # Формируем сообщение для основного пользователя
            if other_count > 0:
                others_message = f"\n\n👥 Также отмечены как выполнившие: {other_count} {_get_engineer_word(other_count)}"
            else:
                others_message = ""
            
            # Подтверждение основному пользователю
            await query.edit_message_text(
                f"{completion_emoji} Мероприятие *{russian_title}* завершено {completion_type}!\n"
                f"{others_message}\n\n"
                f"Спасибо за работу!",
                parse_mode="Markdown"
            )
            
            # 5. Получаем список менеджеров для уведомлений
            managers = await conn.fetch(
                "SELECT telegram_id FROM users WHERE role IN ('manager', 'superadmin')"
            )
            
            # Формируем сообщение для менеджеров
            if other_count > 0:
                others_list = ", ".join([eng['full_name'] for eng in other_engineers[:3]])
                if other_count > 3:
                    others_list += f" и ещё {other_count - 3}"
                others_text = f"\n👥 Также отмечены: {others_list}"
            else:
                others_text = ""
            
            manager_text = (
                f"✅ *Мероприятие завершено*\n\n"
                f"📅 {russian_title}\n"
                f"👤 Завершил: {query.from_user.full_name}"
                f"{others_text}"
            )
            
            # Отправляем уведомления менеджерам
            for manager in managers:
                try:
                    await context.bot.send_message(
                        chat_id=manager['telegram_id'],
                        text=manager_text,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить менеджера {manager['telegram_id']}: {e}")
    
    # Логируем действие
    logger.info(
        f"Пользователь {user_id} завершил мероприятие {event_id}. "
        f"Автоматически завершено за {other_count if 'other_count' in locals() else 0} других инженеров."
    )
    
    # Очищаем контекст
    if 'selected_event_id' in context.user_data:
        del context.user_data['selected_event_id']
    
    return ConversationHandler.END


# Вспомогательная функция для склонения слова "инженер"
def _get_engineer_word(count: int) -> str:
    """Возвращает правильное склонение слова 'инженер' для числа."""
    if count % 10 == 1 and count % 100 != 11:
        return "инженера"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "инженеров"
    else:
        return "инженеров"


async def event_cancel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало процесса отмены (запрос причины).
    """
    query = update.callback_query
    await query.answer()
    
    event_id = context.user_data.get('selected_event_id')
    if not event_id:
        await query.edit_message_text("❌ Ошибка: не выбран ID мероприятия")
        return ConversationHandler.END
    
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
    
    title = to_cyrillic(event['title']) if event else "Неизвестное мероприятие"
    
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


async def event_cancel_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Получает причину и отменяет мероприятие.
    """
    user_id = update.effective_user.id
    reason = update.message.text.strip()
    
    if not reason or len(reason) < 3:
        await update.message.reply_text(
            "❌ Слишком короткая причина. Пожалуйста, опишите подробнее (минимум 3 символа)."
        )
        return CANCEL_REASON
    
    event_id = context.user_data.get('selected_event_id')
    if not event_id:
        await update.message.reply_text("❌ Ошибка: не найден ID мероприятия")
        return ConversationHandler.END
    
    pool = get_db_pool()
    
    try:
        # Получаем информацию о мероприятии
        event_info = await pool.fetchrow(
            """
            SELECT 
                ce.title,
                ce.start_time,
                u.full_name as engineer_name,
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
        
        # 1. Обновляем статус
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
        
        # 3. Отменяем другие назначения
        await pool.execute(
            """
            UPDATE event_assignments 
            SET status = 'cancelled'
            WHERE event_id = $1 AND status IN ('assigned', 'accepted')
            """,
            event_id
        )
        
        russian_title = to_cyrillic(event_info['title'])
        auditory = get_russian_name(event_info['auditory_name']) if event_info['auditory_name'] else "Не указана"
        
        # Получаем менеджеров
        managers = await pool.fetch("SELECT telegram_id FROM users WHERE role IN ('manager', 'superadmin')")
        
        # Определяем контекст отмены
        now = datetime.now()
        if now < event_info['start_time']:
            cancel_context = "до начала"
        elif event_info['start_time'] <= now:
            cancel_context = "во время проведения"
        else:
            cancel_context = "после завершения"
        
        # Уведомление менеджерам
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
                logger.error(f"Не удалось уведомить менеджера {manager['telegram_id']}: {e}")
        
        # Обновляем флаг
        if notification_sent:
            await pool.execute(
                """
                UPDATE cancellation_log 
                SET notification_sent = TRUE 
                WHERE event_id = $1 AND cancelled_by = $2
                """,
                event_id, user_id
            )
        
        # Подтверждение инженеру
        await update.message.reply_text(
            f"✅ Мероприятие *{russian_title}* отменено.\n"
            f"Причина сохранена. Уведомление отправлено начальнику.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отмене мероприятия {event_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при отмене мероприятия. Пожалуйста, сообщите администратору."
        )
        return ConversationHandler.END
    
    # Очищаем контекст
    context.user_data.pop('selected_event_id', None)
    
    return ConversationHandler.END


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена действия."""
    await update.message.reply_text("❌ Действие отменено.")
    return ConversationHandler.END

async def back_to_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Возврат к списку мероприятий.
    """
    query = update.callback_query
    await query.answer()
    
    # Просто вызываем show_my_events для текущего пользователя
    user_id = query.from_user.id
    
    # Очищаем сохранённый event_id
    if 'selected_event_id' in context.user_data:
        del context.user_data['selected_event_id']
    
    # Получаем сообщение и вызываем show_my_events
    await show_my_events(query.message, user_id)
    
    return ConversationHandler.END  # Завершаем разговор, если были в нём


def register_handlers(app):
    """
    Регистрирует обработчики для engineer_tasks.
    """
    # Обработчик выбора мероприятия из списка
    app.add_handler(CallbackQueryHandler(event_select_handler, pattern=r'^event_select_\d+$'))
    
    # Обработчик возврата к списку
    app.add_handler(CallbackQueryHandler(back_to_list_handler, pattern=r'^my_tasks$'))
    
    # ConversationHandler для всего процесса (выбор действия -> отмена/завершение)
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(event_complete_handler, pattern=r'^event_complete$'),
            CallbackQueryHandler(event_cancel_start, pattern=r'^event_cancel$')
        ],
        states={
            SELECTING_ACTION: [
                CallbackQueryHandler(event_complete_handler, pattern=r'^event_complete$'),
                CallbackQueryHandler(event_cancel_start, pattern=r'^event_cancel$')
            ],
            CANCEL_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_cancel_reason)],
        },
        fallbacks=[CommandHandler('cancel', cancel_action)],
        name="engineer_task_conversation",
        persistent=False
    )
    
    app.add_handler(conv_handler)
    logger.info("Обработчики engineer_tasks зарегистрированы")
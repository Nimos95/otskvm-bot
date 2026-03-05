"""Обработчики назначения ответственных инженеров на мероприятия.

Задачи модуля:
- дать менеджеру удобный интерфейс выбора мероприятия из ближайшего диапазона дат;
- позволить назначать одного или нескольких инженеров на мероприятие;
- отправлять инженерам уведомления с кнопками подтверждения/отказа;
- отображать текущие статусы назначений (назначен, подтвердил, выполнил и т.д.).

Используемые компоненты:
- `config.config` — настройки диапазона дат и другие параметры;
- `database.get_db_pool` — пул подключений к PostgreSQL;
- `utils.roles.require_roles` — ограничение доступа к хендлерам только для менеджеров;
- `utils.auditory_names.get_russian_name`, `utils.translit.to_cyrillic` — человекочитаемые
  названия мероприятий и аудиторий;
- объекты `telegram`/`telegram.ext` для построения клавиатур и обработки callback‑запросов.
"""

import logging
from datetime import datetime, timedelta 

import cyrtranslit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import config
from database import get_db_pool
from utils.auditory_names import get_russian_name
from utils.roles import require_roles
from utils.translit import to_cyrillic

logger = logging.getLogger(__name__)

@require_roles(['superadmin', 'manager'])
async def assign_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды `/assign` и кнопки «Назначения».

    Сценарий:
        1. Менеджер вызывает команду или нажимает кнопку в меню.
        2. Бот запрашивает из БД мероприятия на ближайший диапазон дат
           (по умолчанию 5 дней, настраивается `ASSIGN_DAYS_RANGE`).
        3. Формируется список мероприятий с инлайн‑кнопками для перехода к выбору
           инженера.

    Аргументы:
        update: объект `Update` с командой или сообщением кнопки.
        context: контекст Telegram‑бота (в этом хендлере почти не используется).

    Возвращает:
        None. Отправляет сообщение с инлайн‑клавиатурой или текст об отсутствии
        мероприятий.

    Возможные ошибки:
        ⚠️ ВНИМАНИЕ: если `update.message` отсутствует (например, callback),
        хендлер просто завершится без действия — это защита от некорректного
        вызова.
    """
    if not update.message:
        return
    
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} вызвал /assign")
    
    # Получаем мероприятия на ближайший диапазон дней из конфига.
    pool = get_db_pool()
    today = datetime.now().date()
    
    # Создаем список дат на количество дней из конфига
    days_range = getattr(config, 'ASSIGN_DAYS_RANGE', 5)
    dates = [today + timedelta(days=i) for i in range(days_range)]
    
    logger.info(f"Ищем мероприятия на даты: {dates}")
    
    # 🔥 ВАЖНО: используем плейсхолдеры `$1..$N`, а не подстановку дат в строку,
    # чтобы избежать SQL‑инъекций и сохранить кросс‑совместимость с asyncpg.
    placeholders = ','.join([f'${i+1}' for i in range(len(dates))])
    
    rows = await pool.fetch(
        f"""
        SELECT 
            ce.id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE DATE(ce.start_time) IN ({placeholders})
          AND ce.status = 'confirmed'
          AND ce.start_time > NOW()
        ORDER BY ce.start_time
        """,
        *dates
    )
    
    logger.info(f"Найдено мероприятий: {len(rows)}")
    
    if not rows:
        await update.message.reply_text(
            "📅 На ближайшие 5 дней нет мероприятий для назначения."
        )
        return
    
    # Формируем сообщение с кнопками
    text = "📋 **Выберите мероприятие для назначения ответственного:**\n\n"
    
    keyboard = []
    for event in rows:
        event_id = event["id"]
        # Форматируем дату с днём недели для ясности
        date_str = event["start_time"].strftime("%a, %d.%m %H:%M")
        title = event["title"]
        
        # Обратная транслитерация названия мероприятия
        russian_title = to_cyrillic(title)
        
        # Получаем русское название аудитории
        auditory = get_russian_name(event["auditory_name"]) if event["auditory_name"] else "нет аудитории"
        building = event["building"] or ""
        location = f"{auditory} {building}".strip()
        
        # Кнопка для выбора мероприятия
        button_text = f"{date_str} — {russian_title}"
        if location:
            button_text += f" ({location})"
        
        # Обрезаем слишком длинные названия
        if len(button_text) > 40:
            button_text = button_text[:37] + "..."
        
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"assign_event_{event_id}"
        )])
    
    # Кнопка "Назад" в главное меню
    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_engineers_for_event(query, event_id):
    """
    Показывает список инженеров для назначения на выбранное мероприятие.

    Сценарий:
        1. Менеджер выбирает мероприятие из списка.
        2. Хендлер выводит всех инженеров/менеджеров/суперадминов с их текущим
           статусом назначения по данному событию.
        3. Нажатие на инженера приводит к назначению / переотправке уведомления.

    Аргументы:
        query: объект `CallbackQuery`, с помощью которого редактируется сообщение.
        event_id: ID мероприятия в таблице `calendar_events`.

    Возвращает:
        None. Редактирует существующее сообщение с новой клавиатурой.

    Примечания:
        🔥 ВАЖНО: в запросе используется `LEFT JOIN` с `event_assignments`,
        чтобы в интерфейсе отображались как уже назначенные, так и ещё не
        назначенные инженеры.
    """
    pool = get_db_pool()
    
    # 🔥 ВАЖНО: фильтруем только будущие мероприятия (`start_time > NOW()`),
    # чтобы не позволить назначать инженеров на прошедшие события.
    event_row = await pool.fetchrow(
        """
        SELECT 
            ce.title,
            ce.start_time,
            a.name as auditory_name,
            a.building
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE ce.id = $1
          AND ce.start_time > NOW()
        """,
        int(event_id)
    )
    
    if not event_row:
        await query.edit_message_text("Мероприятие не найдено")
        return
    
    # Получаем список инженеров и статусы их назначений по данному событию.
    engineers = await pool.fetch(
        """
        SELECT 
            u.telegram_id,
            u.full_name,
            u.role,
            ea.id as assignment_id,
            ea.status as assignment_status,
            ea.role as assigned_role
        FROM users u
        LEFT JOIN event_assignments ea ON u.telegram_id = ea.assigned_to AND ea.event_id = $1
        WHERE u.role IN ('superadmin', 'engineer', 'manager')
        ORDER BY 
            CASE WHEN ea.id IS NOT NULL THEN 0 ELSE 1 END,
            u.full_name
        """,
        int(event_id)
    )
    
    # Форматируем дату
    date_str = event_row["start_time"].strftime("%d.%m.%Y %H:%M")
    
    # Обратная транслитерация названия мероприятия
    title = event_row["title"]
    russian_title = to_cyrillic(title)
    
    # Получаем русское название аудитории
    auditory = get_russian_name(event_row["auditory_name"]) if event_row["auditory_name"] else "нет аудитории"
    building = event_row["building"] or ""
    location = f"{auditory} {building}".strip()
    
    text = (
        f"📅 **Мероприятие:** {russian_title}\n"
        f"🕐 **Время:** {date_str}\n"
        f"🏢 **Аудитория:** {location}\n\n"
        f"**Выберите ответственного:**"
    )
    
    keyboard = []
    
    for eng in engineers:
        eng_id = eng["telegram_id"]
        name = eng["full_name"]
        status = eng["assignment_status"] if eng["assignment_status"] else None
        assigned_role = eng["assigned_role"] if eng["assigned_role"] else ""
        
        # Разные иконки для разных статусов
        if status == "accepted":
            btn_text = f"✅ {name} (подтвердил)"
        elif status == "assigned":
            btn_text = f"⏳ {name} (ожидает ответа)"
        elif status == "done":
            btn_text = f"✔️ {name} (выполнил)"
        else:
            btn_text = f"👤 {name}"
        
        keyboard.append([InlineKeyboardButton(
            btn_text,
            callback_data=f"assign_to_{event_id}_{eng_id}"
        )])
    
    # Кнопка для назначения нескольких инженеров
    keyboard.append([InlineKeyboardButton(
        "➕ Назначить нескольких", 
        callback_data=f"assign_multi_{event_id}"
    )])
    
    # Кнопки навигации
    keyboard.append([
        InlineKeyboardButton("« К списку мероприятий", callback_data="assign_list"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def assign_engineer_to_event(query, context, user_id, event_id, engineer_id):
    """
    Назначает одного инженера на мероприятие.

    Сценарий:
        1. Менеджер выбирает инженера в списке.
        2. Проверяем, что событие ещё не началось и имеет статус `confirmed`.
        3. Проверяем, что инженер ещё не назначен.
        4. Создаём запись в `event_assignments` и отправляем инженеру уведомление
           с кнопками «Принять» / «Отказаться».

    Аргументы:
        query: `CallbackQuery`, через который показываем всплывающие уведомления.
        context: контекст Telegram‑бота, нужен для отправки сообщений инженеру.
        user_id: Telegram ID менеджера, который делает назначение.
        event_id: ID мероприятия в таблице `calendar_events`.
        engineer_id: Telegram ID назначаемого инженера.

    Возможные ошибки:
        ⚠️ ВНИМАНИЕ: если мероприятие уже в прошлом или не подтверждено,
        назначение блокируется, а менеджер получает всплывающее сообщение.
    """
    pool = get_db_pool()

    # 🔥 ВАЖНО: дополнительная проверка, что мероприятие ещё не началось
    # и всё ещё подтверждено. Это защита от "застывших" кнопок в старых сообщениях.
    event = await pool.fetchrow(
        """
        SELECT start_time FROM calendar_events 
        WHERE id = $1 AND start_time > NOW() AND status = 'confirmed'
        """,
        int(event_id)
    )
    
    if not event:
        await query.answer("❌ Нельзя назначить на прошедшее мероприятие", show_alert=True)
        return
    
    # Проверяем, не назначен ли уже данный инженер на это мероприятие.
    existing = await pool.fetchrow(
        "SELECT id, status FROM event_assignments WHERE event_id = $1 AND assigned_to = $2",
        int(event_id),
        int(engineer_id)
    )
    
    if existing:
        await query.answer("Этот инженер уже назначен на мероприятие", show_alert=True)
        # Показываем обновлённый список
        await show_engineers_for_event(query, event_id)
        return
    
    # Вставляем новое назначение в таблицу event_assignments.
    await pool.execute(
        """
        INSERT INTO event_assignments 
        (event_id, assigned_to, assigned_by, role, status, assigned_at)
        VALUES ($1, $2, $3, 'primary', 'assigned', NOW())
        """,
        int(event_id),
        int(engineer_id),
        int(user_id)
    )
    
    await query.answer("✅ Инженер назначен!")
    
    # Получаем информацию для уведомления
    event_info = await pool.fetchrow(
        "SELECT title, start_time FROM calendar_events WHERE id = $1",
        int(event_id)
    )
    
    engineer_info = await pool.fetchrow(
        "SELECT full_name FROM users WHERE telegram_id = $1",
        int(engineer_id)
    )
    
    if event_info and engineer_info:
        date_str = event_info["start_time"].strftime("%d.%m.%Y %H:%M")
        title = event_info["title"]
        russian_title = to_cyrillic(title)
        
        # Отправляем уведомление назначенному инженеру
        try:
            # Формируем клавиатуру для подтверждения
            keyboard = [
                [
                    InlineKeyboardButton("✅ Принять", callback_data=f"accept_{event_id}"),
                    InlineKeyboardButton("❌ Отказаться", callback_data=f"decline_{event_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=int(engineer_id),
                text=(
                    f"🔔 **Вам назначено мероприятие!**\n\n"
                    f"📅 **Мероприятие:** {russian_title}\n"
                    f"🕐 **Время:** {date_str}\n\n"
                    f"Пожалуйста, подтвердите участие:"
                ),
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление инженеру {engineer_id}: {e}")
    
    # Показываем обновлённый список
    await show_assign_list(query, context) # ← возвращаемся к списку мероприятий


async def accept_assignment(query, user_id, event_id):
    """
    Инженер принимает назначение на мероприятие.

    Аргументы:
        query: `CallbackQuery` от инженера.
        user_id: Telegram ID инженера.
        event_id: ID мероприятия.

    Возвращает:
        None. Обновляет статус в БД и редактирует сообщение с подтверждением.

    Примечания:
        🔥 ВАЖНО: статус меняется на `accepted`, а время подтверждения фиксируется
        в поле `confirmed_at`, чтобы по логам можно было понять скорость реакции.
    """
    pool = get_db_pool()
    
    await pool.execute(
        """
        UPDATE event_assignments 
        SET status = 'accepted', confirmed_at = NOW()
        WHERE event_id = $1 AND assigned_to = $2
        """,
        int(event_id),
        int(user_id)
    )
    
    await query.answer("✅ Назначение принято!")
    await query.edit_message_text(
        "✅ Вы подтвердили участие в мероприятии."
    )

async def show_assign_list(query, context):
    """
    Показывает список мероприятий для назначения (вариант из callback).

    Сценарий:
        Используется при навигации назад из вложенных экранов (список инженеров,
        мульти‑назначение). По сути повторяет логику `assign_handler`, но
        редактирует существующее сообщение вместо отправки нового.

    Аргументы:
        query: `CallbackQuery`, по которому редактируется сообщение.
        context: контекст бота (используется только для совместимости интерфейса).
    """
    # Получаем пул для запросов к БД.
    pool = get_db_pool()
    today = datetime.now().date()
    
    # Получаем те же данные, что и в assign_handler, чтобы интерфейсы
    # из команды и из callback выглядели одинаково.
    days_range = getattr(config, 'ASSIGN_DAYS_RANGE', 5)
    dates = [today + timedelta(days=i) for i in range(days_range)]
    
    placeholders = ','.join([f'${i+1}' for i in range(len(dates))])
    
    rows = await pool.fetch(
        f"""
        SELECT 
            ce.id,
            ce.title,
            ce.start_time,
            ce.end_time,
            a.name as auditory_name,
            a.building
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE DATE(ce.start_time) IN ({placeholders})
          AND ce.status = 'confirmed'
          AND ce.start_time > NOW()
        ORDER BY ce.start_time
        """,
        *dates
    )
    
    if not rows:
        await query.edit_message_text("📅 На ближайшие дни нет мероприятий для назначения.")
        return
    
    # Формируем сообщение с кнопками
    text = "📋 **Выберите мероприятие для назначения ответственного:**\n\n"
    
    keyboard = []
    for event in rows:
        event_id = event["id"]
        date_str = event["start_time"].strftime("%a, %d.%m %H:%M")
        title = event["title"]
        russian_title = cyrtranslit.to_cyrillic(title)
        
        auditory = get_russian_name(event["auditory_name"]) if event["auditory_name"] else "нет аудитории"
        building = event["building"] or ""
        location = f"{auditory} {building}".strip()
        
        button_text = f"{date_str} — {russian_title}"
        if location:
            button_text += f" ({location})"
        
        if len(button_text) > 40:
            button_text = button_text[:37] + "..."
        
        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"assign_event_{event_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Вместо удаления и создания фейкового update — просто редактируем текущее сообщение
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def assign_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает список мероприятий для назначения (возврат из callback).
    """
    query = update.callback_query
    await query.answer()
    
    # Используем существующую функцию show_assign_list
    await show_assign_list(query, context)


async def decline_assignment(query, user_id, event_id):
    """
    Инженер отказывается от участия в мероприятии.

    Аргументы:
        query: `CallbackQuery` от инженера.
        user_id: Telegram ID инженера.
        event_id: ID мероприятия.

    Примечания:
        ⚠️ ВНИМАНИЕ: текущее назначение полностью удаляется из `event_assignments`.
        Это означает, что история отказа сохраняется только в логах бота,
        а не в БД. Если в будущем понадобится аналитика отказов, потребуется
        отдельная таблица/поле.
    """
    pool = get_db_pool()
    
    # Удаляем назначение
    await pool.execute(
        "DELETE FROM event_assignments WHERE event_id = $1 AND assigned_to = $2",
        int(event_id),
        int(user_id)
    )
    
    await query.answer("❌ Вы отказались от участия")
    await query.edit_message_text(
        "❌ Вы отказались от участия в мероприятии."
    )

async def show_multi_assign(query, context, event_id):
    """
    Показывает интерфейс для назначения нескольких инженеров на мероприятие.

    Сценарий:
        1. Менеджер выбирает режим «Назначить нескольких».
        2. Отображается список инженеров, где по клику инженер попадает
           во временный список `selected_engineers_*`.
        3. После выбора нескольких инженеров менеджер подтверждает массовое
           назначение.

    Аргументы:
        query: `CallbackQuery`, по которому редактируется сообщение.
        context: контекст Telegram‑бота, хранит временный набор выбранных инженеров.
        event_id: ID мероприятия.

    Примечания:
        🔥 ВАЖНО: выбранные инженеры хранятся в `context.user_data` как `set`.
        Это удобно для переключения выбора, но такие данные не должны
        сериализоваться в persistent‑storage — здесь контекст используется
        только в рамках текущей сессии менеджера.
    """
    pool = get_db_pool()
    
    # Получаем информацию о мероприятии, чтобы показать её в заголовке экрана.
    event_row = await pool.fetchrow(
        """
        SELECT 
            ce.title,
            ce.start_time,
            a.name as auditory_name,
            a.building
        FROM calendar_events ce
        LEFT JOIN auditories a ON ce.auditory_id = a.id
        WHERE ce.id = $1
        """,
        int(event_id)
    )
    
    if not event_row:
        await query.edit_message_text("Мероприятие не найдено")
        return
    
    # Получаем список инженеров с их текущими статусами по этому событию.
    engineers = await pool.fetch(
        """
        SELECT 
            u.telegram_id,
            u.full_name,
            u.role,
            ea.id as assignment_id,
            ea.status as assignment_status,
            ea.role as assigned_role
        FROM users u
        LEFT JOIN event_assignments ea ON u.telegram_id = ea.assigned_to AND ea.event_id = $1
        WHERE u.role IN ('engineer', 'manager', 'superadmin')
        ORDER BY 
            CASE WHEN ea.id IS NOT NULL THEN 0 ELSE 1 END,
            u.full_name
        """,
        int(event_id)
    )
    
    # Форматируем дату
    date_str = event_row["start_time"].strftime("%d.%m.%Y %H:%M")
    
    # Обратная транслитерация
    title = event_row["title"]
    russian_title = to_cyrillic(title)
    
    auditory = get_russian_name(event_row["auditory_name"]) if event_row["auditory_name"] else "нет аудитории"
    building = event_row["building"] or ""
    location = f"{auditory} {building}".strip()
    
    text = (
        f"📅 **Мероприятие:** {russian_title}\n"
        f"🕐 **Время:** {date_str}\n"
        f"🏢 **Аудитория:** {location}\n\n"
        f"**Выберите инженеров для назначения:**\n"
        f"_(нажмите на инженера, чтобы выбрать/снять выбор)_\n\n"
    )
    
    # 🔥 ВАЖНО: используем `context.user_data` как хранилище состояния выбора
    # для конкретного `event_id`, чтобы одно и то же сообщение корректно
    # отображало выбранных инженеров при каждом обновлении.
    key = f"selected_engineers_{event_id}"
    selected = context.user_data.get(key, set())
    
    keyboard = []
    
    for eng in engineers:
        eng_id = eng["telegram_id"]
        name = eng["full_name"]
        status = eng["assignment_status"] if eng["assignment_status"] else None
        
        # Проверяем, выбран ли инженер
        is_selected = eng_id in selected
        
        if is_selected:
            btn_text = f"✅ {name}"
        elif status == "accepted":
            btn_text = f"✅ {name} (подтвердил)"
        elif status == "assigned":
            btn_text = f"⏳ {name} (ожидает)"
        else:
            btn_text = f"👤 {name}"
        
        keyboard.append([InlineKeyboardButton(
            btn_text,
            callback_data=f"multi_toggle_{event_id}_{eng_id}"
        )])
    
    # Кнопка для подтверждения назначения
    if selected:
        keyboard.append([
            InlineKeyboardButton(
                f"✅ Назначить выбранных ({len(selected)})", 
                callback_data=f"multi_confirm_{event_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("« Назад к списку", callback_data=f"assign_event_{event_id}")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def multi_toggle_handler(query, context, user_id, event_id, engineer_id):
    """
    Добавляет или удаляет инженера из временного списка выбранных.

    Аргументы:
        query: `CallbackQuery` с нажатием на конкретного инженера.
        context: контекст Telegram‑бота.
        user_id: Telegram ID менеджера (сейчас не используется, но оставлен для расширения).
        event_id: ID мероприятия.
        engineer_id: Telegram ID инженера, которого включаем/исключаем.

    Примечания:
        ⚠️ ВНИМАНИЕ: так как состояние хранится в памяти процесса бота, при
        его перезапуске выбор будет потерян — это осознанный компромисс,
        чтобы не усложнять схему хранения.
    """
    # 🔥 ИСПОЛЬЗОВАНИЕ context.user_data: создаём отдельный set под конкретное событие.
    key = f"selected_engineers_{event_id}"
    
    if key not in context.user_data:
        context.user_data[key] = set()
    
    selected = context.user_data[key]
    
    if engineer_id in selected:
        selected.remove(engineer_id)
    else:
        selected.add(engineer_id)
    
    # Обновляем отображение
    await show_multi_assign(query, context, event_id)


async def multi_confirm_handler(query, context, user_id, event_id):
    """
    Подтверждает назначение всех ранее выбранных инженеров.

    Аргументы:
        query: `CallbackQuery` от менеджера при нажатии кнопки подтверждения.
        context: контекст Telegram‑бота с набором выбранных инженеров.
        user_id: Telegram ID менеджера, назначающего инженеров.
        event_id: ID мероприятия.

    Возвращает:
        None. Создаёт записи в `event_assignments`, отправляет уведомления и
        обновляет интерфейс выбора инженеров.

    Примечания:
        🔥 ВАЖНО: для каждого инженера дополнительно проверяется отсутствие
        существующего назначения, чтобы избежать дублей при повторном нажатии.
    """
    # 🔥 ВАЖНО: используем `context.user_data` как источник временного списка
    # выбранных инженеров для данного события.
    key = f"selected_engineers_{event_id}"
    selected = context.user_data.get(key, set())
    
    if not selected:
        await query.answer("❌ Никто не выбран", show_alert=True)
        return
    
    pool = get_db_pool()
    success_count = 0
    already_count = 0
    
    for engineer_id in selected:
        # Проверяем, не назначен ли уже
        existing = await pool.fetchrow(
            "SELECT id FROM event_assignments WHERE event_id = $1 AND assigned_to = $2",
            int(event_id),
            int(engineer_id)
        )
        
        if existing:
            already_count += 1
            continue
        
        # Назначаем инженера
        await pool.execute(
            """
            INSERT INTO event_assignments 
            (event_id, assigned_to, assigned_by, role, status, assigned_at)
            VALUES ($1, $2, $3, 'primary', 'assigned', NOW())
            """,
            int(event_id),
            int(engineer_id),
            int(user_id)
        )
        
        # Отправляем уведомление
        await send_assignment_notification(context, event_id, engineer_id)
        
        success_count += 1
    
    # После подтверждения очищаем выбранных, чтобы при следующем заходе
    # менеджер не увидел «старый» выбор.
    context.user_data.pop(key, None)
    
    await query.answer(f"✅ Назначено: {success_count}, уже были назначены: {already_count}")
    
    # Возвращаемся к списку инженеров
    await show_engineers_for_event(query, event_id)


async def send_assignment_notification(context, event_id, engineer_id):
    """
    Отправляет уведомление о назначении инженеру.

    Аргументы:
        context: контекст Telegram‑бота с доступом к `bot`.
        event_id: ID мероприятия.
        engineer_id: Telegram ID инженера.

    Примечания:
        🔥 ВАЖНО: текст уведомления и клавиатура продублированы с одиночным
        назначением (`assign_engineer_to_event`), чтобы поведение было
        одинаковым независимо от того, назначен инженер один или в группе.
    """
    pool = get_db_pool()
    
    event_info = await pool.fetchrow(
        """
        SELECT 
            ce.title,
            ce.start_time
        FROM calendar_events ce
        WHERE ce.id = $1
        """,
        int(event_id)
    )
    
    if not event_info:
        return
    
    date_str = event_info["start_time"].strftime("%d.%m.%Y %H:%M")
    title = event_info["title"]
    russian_title = to_cyrillic(title)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{event_id}"),
            InlineKeyboardButton("❌ Отказаться", callback_data=f"decline_{event_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=int(engineer_id),
            text=(
                f"🔔 **Вам назначено мероприятие!**\n\n"
                f"📅 **Мероприятие:** {russian_title}\n"
                f"🕐 **Время:** {date_str}\n\n"
                f"Пожалуйста, подтвердите участие:"
            ),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление инженеру {engineer_id}: {e}")
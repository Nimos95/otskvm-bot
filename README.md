
---

## Детальное описание таблиц

### 1. users — пользователи системы

| Поле | Тип | Описание |
|------|-----|----------|
| telegram_id | BIGINT (PK) | ID пользователя в Telegram |
| full_name | VARCHAR(100) | Имя для отображения |
| username | VARCHAR(100) | @username в Telegram |
| role | VARCHAR(20) | admin / manager / engineer / viewer |
| created_at | TIMESTAMP | Когда зарегистрировался |
| last_active | TIMESTAMP | Последняя активность |
| is_active | BOOLEAN | Не уволен ли |

**Роли:**
- `admin` — начальник управления (полный доступ)
- `manager` — проджект-менеджер (ставит задачи, смотрит статистику)
- `engineer` — инженер (отмечает статусы, получает задачи)
- `viewer` — внешний наблюдатель (только просмотр)

---

### 2. auditories — аудитории

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | Внутренний ID |
| name | VARCHAR(50) | Номер аудитории ('501', '315') |
| building | VARCHAR(50) | Корпус |
| floor | INTEGER | Этаж |
| equipment | TEXT | Описание оборудования |
| notes | TEXT | Заметки |
| is_active | BOOLEAN | Не списана ли |

---

### 3. status_log — история статусов (ядро системы)

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| auditory_id | INTEGER (FK) | Аудитория |
| status | VARCHAR(10) | green / yellow / red |
| comment | TEXT | Описание проблемы |
| reported_by | BIGINT (FK) | Кто отметил |
| created_at | TIMESTAMP | Когда отметили |
| equipment_type | VARCHAR(50) | Тип оборудования |
| problem_category | VARCHAR(50) | Категория проблемы |
| resolved_at | TIMESTAMP | Когда починили |
| resolution_comment | TEXT | Как починили |

---

### 4. calendar_events — мероприятия из Google Calendar

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| google_event_id | VARCHAR(255) | ID из Google Calendar |
| auditory_id | INTEGER (FK) | Аудитория |
| title | VARCHAR(255) | Название мероприятия |
| description | TEXT | Описание |
| start_time | TIMESTAMP | Начало |
| end_time | TIMESTAMP | Конец |
| organizer | VARCHAR(255) | Организатор |
| status | VARCHAR(20) | confirmed / cancelled / tentative |
| last_sync | TIMESTAMP | Последняя синхронизация |

---

### 5. event_assignments — кто ответственный за мероприятие

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| event_id | INTEGER (FK) | Мероприятие |
| assigned_to | BIGINT (FK) | Инженер |
| assigned_by | BIGINT (FK) | Начальник |
| assigned_at | TIMESTAMP | Когда назначили |
| role | VARCHAR(30) | primary / secondary / trainee / backup |
| status | VARCHAR(20) | assigned / accepted / done / cancelled |
| confirmed_at | TIMESTAMP | Когда инженер подтвердил |
| completed_at | TIMESTAMP | Когда отработал |

**Уникальность:** один инженер не может быть назначен на одно мероприятие дважды

---

### 6. tasks — задачи от начальника

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| title | TEXT | Краткое описание |
| description | TEXT | Подробности |
| created_by | BIGINT (FK) | Кто создал |
| assigned_to | BIGINT (FK) | Кому назначено |
| assigned_group | VARCHAR(50) | Или группа ('all', 'engineers') |
| auditory_id | INTEGER (FK) | Связанная аудитория |
| deadline | TIMESTAMP | Срок |
| priority | VARCHAR(10) | low / medium / high / urgent |
| status | VARCHAR(20) | new / accepted / in_progress / done / cancelled / overdue |
| created_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |

---

### 7. task_comments — комментарии к задачам

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| task_id | INTEGER (FK) | Задача |
| user_id | BIGINT (FK) | Кто написал |
| comment | TEXT | Текст |
| created_at | TIMESTAMP | |

---

### 8. notifications — лог уведомлений

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| user_id | BIGINT (FK) | Кому |
| task_id | INTEGER (FK) | По какой задаче |
| event_id | INTEGER (FK) | По какому мероприятию |
| type | VARCHAR(30) | new_task / reminder / deadline / assignment / cancellation |
| sent_at | TIMESTAMP | Когда отправили |
| read_at | TIMESTAMP | Когда прочитал |
| telegram_message_id | BIGINT | ID сообщения в Telegram |

---

### 9. cancellation_log — отмены мероприятий

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| event_id | INTEGER (FK) | Мероприятие |
| cancelled_by | BIGINT (FK) | Кто отменил |
| cancelled_at | TIMESTAMP | |
| source | VARCHAR(20) | bot / calendar_webhook / manual |
| reason | TEXT | Причина |
| notification_sent | BOOLEAN | Уведомили ли |

---

### 10. equipment_types — справочник оборудования

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| name | VARCHAR(50) | projector / sound / hdmi / remote / computer / other |
| description | TEXT | |

---

### 11. problem_categories — справочник категорий проблем

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL (PK) | |
| name | VARCHAR(100) | no_power / no_signal / broken_cable / software |
| equipment_type_id | INTEGER (FK) | Связь с оборудованием |
| description | TEXT | |


---

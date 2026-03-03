-- Дополнительные индексы для оптимизации часто используемых запросов.

-- Быстрый поиск последнего статуса по аудитории
CREATE INDEX IF NOT EXISTS idx_status_log_auditory_created_at
    ON status_log (auditory_id, created_at DESC);

-- Фильтрация подтверждённых событий по времени начала
CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time_status
    ON calendar_events (start_time, status);

-- Частые выборки назначений по событию и статусу
CREATE INDEX IF NOT EXISTS idx_event_assignments_event_status
    ON event_assignments (event_id, status);

-- Частые выборки назначений по инженеру и статусу
CREATE INDEX IF NOT EXISTS idx_event_assignments_assigned_to_status
    ON event_assignments (assigned_to, status);

-- Проверка недавних уведомлений по событию/пользователю/типу
CREATE INDEX IF NOT EXISTS idx_notifications_event_user_type_sent_at
    ON notifications (event_id, user_id, type, sent_at DESC);

-- Аналитика отмен по мероприятию
CREATE INDEX IF NOT EXISTS idx_cancellation_log_event_id
    ON cancellation_log (event_id);


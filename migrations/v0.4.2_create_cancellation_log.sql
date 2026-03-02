-- Создание таблицы cancellation_log для отслеживания отмен мероприятий
CREATE TABLE IF NOT EXISTS cancellation_log (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
    cancelled_by BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    cancelled_at TIMESTAMP NOT NULL DEFAULT NOW(),
    source VARCHAR(20) NOT NULL CHECK (source IN ('bot', 'calendar_webhook', 'manual')),
    reason TEXT,
    notification_sent BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Индексы для быстрого поиска
    CONSTRAINT fk_cancellation_event FOREIGN KEY (event_id) 
        REFERENCES calendar_events(id) ON DELETE CASCADE,
    CONSTRAINT fk_cancellation_user FOREIGN KEY (cancelled_by) 
        REFERENCES users(telegram_id) ON DELETE CASCADE
);

-- Индексы для оптимизации запросов
CREATE INDEX idx_cancellation_log_event_id ON cancellation_log(event_id);
CREATE INDEX idx_cancellation_log_cancelled_by ON cancellation_log(cancelled_by);
CREATE INDEX idx_cancellation_log_cancelled_at ON cancellation_log(cancelled_at);
CREATE INDEX idx_cancellation_log_source ON cancellation_log(source);

-- Комментарии к полям для документации
COMMENT ON TABLE cancellation_log IS 'Лог отмен мероприятий';
COMMENT ON COLUMN cancellation_log.id IS 'Уникальный идентификатор записи';
COMMENT ON COLUMN cancellation_log.event_id IS 'ID отменённого мероприятия из calendar_events';
COMMENT ON COLUMN cancellation_log.cancelled_by IS 'ID пользователя, отменившего мероприятие';
COMMENT ON COLUMN cancellation_log.cancelled_at IS 'Дата и время отмены';
COMMENT ON COLUMN cancellation_log.source IS 'Источник отмены: bot / calendar_webhook / manual';
COMMENT ON COLUMN cancellation_log.reason IS 'Причина отмены (текст)';
COMMENT ON COLUMN cancellation_log.notification_sent IS 'Флаг отправки уведомления об отмене';

-- Добавляем проверку, что причина обязательна для отмен через бота
-- (но можно оставить комментарий)

-- Для обратной совместимости: если таблица уже существует, но нет каких-то полей
DO $$
BEGIN
    -- Проверяем существование таблицы
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cancellation_log') THEN
        -- Добавляем поле notification_sent, если его нет
        IF NOT EXISTS (SELECT FROM information_schema.columns 
                       WHERE table_name = 'cancellation_log' AND column_name = 'notification_sent') THEN
            ALTER TABLE cancellation_log ADD COLUMN notification_sent BOOLEAN DEFAULT FALSE;
        END IF;
        
        -- Добавляем поле reason, если его нет
        IF NOT EXISTS (SELECT FROM information_schema.columns 
                       WHERE table_name = 'cancellation_log' AND column_name = 'reason') THEN
            ALTER TABLE cancellation_log ADD COLUMN reason TEXT;
        END IF;
        
        -- Добавляем поле source, если его нет (с проверкой constraint)
        IF NOT EXISTS (SELECT FROM information_schema.columns 
                       WHERE table_name = 'cancellation_log' AND column_name = 'source') THEN
            ALTER TABLE cancellation_log ADD COLUMN source VARCHAR(20);
            -- Обновляем существующие записи значением по умолчанию
            UPDATE cancellation_log SET source = 'manual' WHERE source IS NULL;
            -- Делаем поле NOT NULL
            ALTER TABLE cancellation_log ALTER COLUMN source SET NOT NULL;
            -- Добавляем проверку
            ALTER TABLE cancellation_log ADD CONSTRAINT cancellation_log_source_check 
                CHECK (source IN ('bot', 'calendar_webhook', 'manual'));
        END IF;
    END IF;
END $$;
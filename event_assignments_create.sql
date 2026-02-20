-- Подключаемся к базе
\c otskvmbot;

-- Таблица назначений ответственных
CREATE TABLE event_assignments (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES calendar_events(id) ON DELETE CASCADE,
    assigned_to BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    assigned_by BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    assigned_at TIMESTAMP DEFAULT NOW(),
    role VARCHAR(30) DEFAULT 'primary',        -- primary, secondary, trainee, backup
    status VARCHAR(20) DEFAULT 'assigned',      -- assigned, accepted, done, cancelled
    confirmed_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Один инженер не может быть назначен на одно мероприятие дважды
    CONSTRAINT unique_event_engineer UNIQUE(event_id, assigned_to)
);

-- Индексы для быстрого поиска
CREATE INDEX idx_assignments_event ON event_assignments(event_id);
CREATE INDEX idx_assignments_user ON event_assignments(assigned_to);
CREATE INDEX idx_assignments_status ON event_assignments(status);

-- Комментарии к полям (для документации)
COMMENT ON TABLE event_assignments IS 'Назначения ответственных на мероприятия';
COMMENT ON COLUMN event_assignments.role IS 'Роль: primary - основной, secondary - помощник, trainee - стажёр, backup - подмена';
COMMENT ON COLUMN event_assignments.status IS 'Статус: assigned - назначен, accepted - принял, done - выполнил, cancelled - отменён';
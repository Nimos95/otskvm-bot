-- ========================================
-- Версия: v0.3.0
-- Описание: Назначение ответственных
-- Дата: 20.02.2026
-- ========================================

-- Таблица назначений
CREATE TABLE IF NOT EXISTS event_assignments (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES calendar_events(id) ON DELETE CASCADE,
    assigned_to BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    assigned_by BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    assigned_at TIMESTAMP DEFAULT NOW(),
    role VARCHAR(30) DEFAULT 'primary',
    status VARCHAR(30) DEFAULT 'assigned',
    confirmed_at TIMESTAMP,
    completed_at TIMESTAMP,
    UNIQUE(event_id, assigned_to)
);

COMMENT ON TABLE event_assignments IS 'Назначения ответственных';
COMMENT ON COLUMN event_assignments.role IS 'primary, secondary, trainee, backup';
COMMENT ON COLUMN event_assignments.status IS 'assigned, accepted, done, cancelled, replacing';

-- Индексы
CREATE INDEX idx_assignments_event ON event_assignments(event_id);
CREATE INDEX idx_assignments_user ON event_assignments(assigned_to);
CREATE INDEX idx_assignments_status ON event_assignments(status);

-- Права доступа (выполнять после создания пользователя bot_user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
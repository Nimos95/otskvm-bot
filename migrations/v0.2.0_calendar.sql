-- ========================================
-- Версия: v0.2.0
-- Описание: Google Calendar интеграция
-- Дата: 18.02.2026
-- ========================================

-- Таблица событий календаря
CREATE TABLE IF NOT EXISTS calendar_events (
    id SERIAL PRIMARY KEY,
    google_event_id VARCHAR(255) UNIQUE,
    auditory_id INTEGER REFERENCES auditories(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    organizer VARCHAR(255),
    status VARCHAR(20) DEFAULT 'confirmed',
    last_sync TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE calendar_events IS 'События из Google Calendar';
COMMENT ON COLUMN calendar_events.status IS 'confirmed, cancelled, tentative';

-- Индексы
CREATE INDEX idx_calendar_events_date ON calendar_events(start_time);
CREATE INDEX idx_calendar_events_auditory ON calendar_events(auditory_id);

-- Права доступа (выполнять после создания пользователя bot_user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
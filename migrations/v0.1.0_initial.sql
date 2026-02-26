-- ========================================
-- Версия: v0.1.0
-- Описание: Начальные таблицы
-- Дата: 16.02.2026
-- ========================================

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    username VARCHAR(100),
    role VARCHAR(20) DEFAULT 'engineer',
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Комментарии
COMMENT ON TABLE users IS 'Пользователи системы';
COMMENT ON COLUMN users.role IS 'superadmin, admin, manager, engineer, viewer';

-- Таблица аудиторий
CREATE TABLE IF NOT EXISTS auditories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    building VARCHAR(50),
    floor INTEGER,
    equipment TEXT,
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

COMMENT ON TABLE auditories IS 'Аудитории';

-- Таблица статусов
CREATE TABLE IF NOT EXISTS status_log (
    id SERIAL PRIMARY KEY,
    auditory_id INTEGER REFERENCES auditories(id) ON DELETE CASCADE,
    status VARCHAR(10) NOT NULL,
    comment TEXT,
    reported_by BIGINT REFERENCES users(telegram_id),
    created_at TIMESTAMP DEFAULT NOW(),
    equipment_type VARCHAR(50),
    problem_category VARCHAR(50),
    resolved_at TIMESTAMP,
    resolution_comment TEXT
);

COMMENT ON TABLE status_log IS 'История статусов аудиторий';

-- Индексы
CREATE INDEX idx_status_log_auditory ON status_log(auditory_id);
CREATE INDEX idx_status_log_date ON status_log(created_at);
CREATE INDEX idx_status_log_status ON status_log(status);

-- Права доступа (выполнять после создания пользователя bot_user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
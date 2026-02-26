-- ========================================
-- Версия: v0.4.0
-- Описание: Система уведомлений
-- Дата: 24.02.2026
-- ========================================

-- Таблица уведомлений
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES calendar_events(id) ON DELETE CASCADE,
    type VARCHAR(30) NOT NULL,
    sent_at TIMESTAMP DEFAULT NOW(),
    read_at TIMESTAMP,
    telegram_message_id BIGINT
);

COMMENT ON TABLE notifications IS 'Лог уведомлений';
COMMENT ON COLUMN notifications.type IS 'reminder, confirmation, replacement, manual_completion, early_completion';

-- Индексы
CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_event ON notifications(event_id);
CREATE INDEX idx_notifications_sent ON notifications(sent_at);

-- Обновляем таблицу event_assignments (увеличиваем длину поля status)
ALTER TABLE event_assignments ALTER COLUMN status TYPE VARCHAR(30);

-- Обновляем таблицу auditories (добавляем email для Evoko Liso)
ALTER TABLE auditories ADD COLUMN IF NOT EXISTS room_email VARCHAR(255);

COMMENT ON COLUMN auditories.room_email IS 'Email для отправки бронирований (Evoko Liso)';

-- Права доступа (выполнять после создания пользователя bot_user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
-- Миграция: Добавление поддержки VK ID в таблицы
-- Версия: 0.7.0
-- Дата: 17.03.2026

-- ============================================
-- 1. Добавляем поля VK в таблицу users
-- ============================================
ALTER TABLE users 
ADD COLUMN vk_id BIGINT UNIQUE,
ADD COLUMN vk_username VARCHAR(100);

-- Комментарии
COMMENT ON COLUMN users.vk_id IS 'ID пользователя в VK (для входа через ВКонтакте)';
COMMENT ON COLUMN users.vk_username IS 'Username пользователя в VK';

-- Индекс для быстрого поиска
CREATE INDEX idx_users_vk_id ON users(vk_id) WHERE vk_id IS NOT NULL;

-- ============================================
-- 2. Добавляем поля в event_assignments для поддержки VK
-- ============================================
ALTER TABLE event_assignments
ADD COLUMN source VARCHAR(20) DEFAULT 'telegram',
ADD COLUMN vk_assigned_to BIGINT;

-- Комментарии
COMMENT ON COLUMN event_assignments.source IS 'Источник назначения: telegram / vk / cross (оба)';
COMMENT ON COLUMN event_assignments.vk_assigned_to IS 'VK ID назначенного инженера (если назначение через VK)';

-- Индексы
CREATE INDEX idx_event_assignments_vk_assigned_to ON event_assignments(vk_assigned_to) WHERE vk_assigned_to IS NOT NULL;
CREATE INDEX idx_event_assignments_source ON event_assignments(source);

-- ============================================
-- 3. Функция для получения telegram_id по vk_id
-- ============================================
CREATE OR REPLACE FUNCTION get_telegram_id_by_vk(vk_id_param BIGINT)
RETURNS BIGINT AS $$
DECLARE
    result_id BIGINT;
BEGIN
    -- Пытаемся найти существующего пользователя
    SELECT telegram_id INTO result_id FROM users WHERE vk_id = vk_id_param;
    
    -- Если нашли, возвращаем
    IF result_id IS NOT NULL THEN
        RETURN result_id;
    END IF;
    
    -- Если нет, создаём нового пользователя с отрицательным telegram_id
    INSERT INTO users (telegram_id, vk_id, full_name, role, created_at, last_active, is_active)
    VALUES (-vk_id_param, vk_id_param, 'VK User ' || vk_id_param, 'engineer', NOW(), NOW(), true)
    RETURNING telegram_id INTO result_id;
    
    RETURN result_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 4. Функция для получения актуального assigned_to
-- ============================================
CREATE OR REPLACE FUNCTION get_assigned_to(event_id_param INTEGER, vk_id_param BIGINT)
RETURNS BIGINT AS $$
DECLARE
    telegram_id_result BIGINT;
BEGIN
    -- Пытаемся найти по vk_id
    SELECT telegram_id INTO telegram_id_result FROM users WHERE vk_id = vk_id_param;
    
    -- Если нашли, возвращаем
    IF telegram_id_result IS NOT NULL THEN
        RETURN telegram_id_result;
    END IF;
    
    -- Если нет, создаём нового
    INSERT INTO users (telegram_id, vk_id, full_name, role, created_at, last_active, is_active)
    VALUES (-vk_id_param, vk_id_param, 'VK User ' || vk_id_param, 'engineer', NOW(), NOW(), true)
    RETURNING telegram_id INTO telegram_id_result;
    
    RETURN telegram_id_result;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 5. Проверка миграции
-- ============================================
SELECT 'users' as table_name, 
       COUNT(*) as total, 
       COUNT(vk_id) as with_vk,
       COUNT(CASE WHEN telegram_id < 0 THEN 1 END) as vk_only_users
FROM users
UNION ALL
SELECT 'event_assignments', 
       COUNT(*), 
       COUNT(vk_assigned_to),
       0
FROM event_assignments;
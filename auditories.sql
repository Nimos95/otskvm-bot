DROP TABLE IF EXISTS auditories CASCADE;

CREATE TABLE auditories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    building VARCHAR(50),
    floor INTEGER,
    equipment TEXT,
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

INSERT INTO auditories (name, building, floor) VALUES
('118', 'ГУК', 1),
('130', 'ГУК', 1),
('Семенов', 'НИК', 2),
('Лекционный зал 1', 'НИК', 2),
('Лекционный зал 2', 'НИК', 2),
('Капица', 'НИК', 1),
('Г3.56', 'НИК', 3),
('МКЗ', 'НИК', 1),
('Г3.14', 'НИК', 3),
('335', '1УК', 3),
('Кабинет Ректора', 'ГУК', 1),
('Зеленый зал', 'НИК', 1);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
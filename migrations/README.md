# Миграции базы данных OTSKVM Bot

## 📋 Порядок применения миграций

1. **Подключитесь к базе данных**
   ```bash
   psql -U postgres -d otskvmbot
   ```
2. **Применяйте миграции по порядку**
   ```bash
   psql -U postgres -d otskvmbot -f migrations/v0.1.0_initial.sql
   psql -U postgres -d otskvmbot -f migrations/v0.2.0_calendar.sql
   psql -U postgres -d otskvmbot -f migrations/v0.3.0_assignments.sql
   psql -U postgres -d otskvmbot -f migrations/v0.4.0_notifications.sql
   ```
3. **После создания пользователя bot_user выполните**
   ```bash
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;
   ```

# 🔄 Откат миграций (если нужно)

   ```bash
   DROP TABLE IF EXISTS notifications CASCADE;
   DROP TABLE IF EXISTS event_assignments CASCADE;
   DROP TABLE IF EXISTS calendar_events CASCADE;
   DROP TABLE IF EXISTS status_log CASCADE;
   DROP TABLE IF EXISTS auditories CASCADE;
   DROP TABLE IF EXISTS users CASCADE;
   ```
   
# 📝 Примечания
   - Все миграции идемпотентны (используют IF NOT EXISTS)
   - После применения новой миграции не забудьте выдать права боту
   - Для локальной разработки используйте те же миграции в Docker-контейнере

# ✅ После создания
   ```bash
   git add migrations/
   git commit -m "Docs: добавлены SQL-миграции всех версий"
   git push origin main
   ```
"""Асинхронная работа с PostgreSQL через asyncpg."""

import logging
from typing import Any, Dict, List, Optional

import asyncpg

from config import config

logger = logging.getLogger(__name__)

_db_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> None:
    """
    Создаёт пул подключений к PostgreSQL и сохраняет его в глобальную переменную.

    Логирует успешное создание пула. В случае ошибки логирует и пробрасывает исключение.
    """
    global _db_pool
    try:
        _db_pool = await asyncpg.create_pool(config.DATABASE_URL)
        logger.info("Пул подключений к БД успешно создан")
    except Exception as e:
        logger.exception("Не удалось создать пул подключений к БД: %s", e)
        raise


async def close_db_pool() -> None:
    """
    Закрывает пул подключений, если он был инициализирован.
    """
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
        logger.info("Пул подключений к БД закрыт")


def get_db_pool() -> asyncpg.Pool:
    """
    Возвращает пул подключений к БД.

    Returns:
        asyncpg.Pool: Пул подключений.

    Raises:
        RuntimeError: Если пул не был инициализирован.
    """
    if _db_pool is None:
        raise RuntimeError(
            "Пул подключений к БД не инициализирован. Вызовите init_db_pool() перед использованием."
        )
    return _db_pool


class Database:
    """Класс для работы с базой данных."""

    VALID_STATUSES = ("green", "yellow", "red")

    @staticmethod
    async def add_user(
        telegram_id: int,
        full_name: str,
        username: Optional[str] = None,
    ) -> bool:
        """
        Добавляет пользователя в таблицу users.

        При конфликте по telegram_id обновляет full_name, username и last_active.

        Args:
            telegram_id: ID пользователя в Telegram.
            full_name: Полное имя пользователя.
            username: Имя пользователя (username) в Telegram, опционально.

        Returns:
            True при успехе, False при ошибке.
        """
        pool = get_db_pool()
        try:
            await pool.execute(
                """
                INSERT INTO users (telegram_id, full_name, username, last_active)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    username = EXCLUDED.username,
                    last_active = NOW()
                """,
                telegram_id,
                full_name,
                username,
            )
            logger.info("Пользователь %s (telegram_id=%s) добавлен/обновлён", full_name, telegram_id)
            return True
        except Exception as e:
            logger.error("Ошибка при добавлении пользователя %s: %s", telegram_id, e, exc_info=True)
            return False

    @staticmethod
    async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Возвращает пользователя по telegram_id.

        Args:
            telegram_id: ID пользователя в Telegram.

        Returns:
            Словарь с данными пользователя или None, если не найден.
        """
        pool = get_db_pool()
        try:
            row = await pool.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                telegram_id,
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("Ошибка при получении пользователя %s: %s", telegram_id, e, exc_info=True)
            return None

    @staticmethod
    async def update_user_last_active(telegram_id: int) -> bool:
        """
        Обновляет last_active = NOW() для пользователя.

        Args:
            telegram_id: ID пользователя в Telegram.

        Returns:
            True при успехе, False при ошибке.
        """
        pool = get_db_pool()
        try:
            await pool.execute(
                "UPDATE users SET last_active = NOW() WHERE telegram_id = $1",
                telegram_id,
            )
            logger.info("Обновлён last_active для пользователя telegram_id=%s", telegram_id)
            return True
        except Exception as e:
            logger.error(
                "Ошибка при обновлении last_active для %s: %s",
                telegram_id,
                e,
                exc_info=True,
            )
            return False

    @staticmethod
    async def get_auditory_by_name(name: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает аудиторию по имени.

        Args:
            name: Название аудитории (поле name уникально).

        Returns:
            Словарь с данными аудитории или None, если не найдена.
        """
        pool = get_db_pool()
        try:
            row = await pool.fetchrow(
                "SELECT * FROM auditories WHERE name = $1 AND is_active = TRUE",
                name,
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("Ошибка при получении аудитории '%s': %s", name, e, exc_info=True)
            return None

    @staticmethod
    async def add_status(
        telegram_id: int,
        auditory_name: str,
        status: str,
        comment: Optional[str] = None,
    ) -> bool:
        """
        Добавляет запись о статусе в status_log.

        Проверяет существование аудитории и допустимость значения status
        ('green', 'yellow', 'red').

        Args:
            telegram_id: ID пользователя в Telegram (reported_by).
            auditory_name: Название аудитории.
            status: Статус ('green', 'yellow', 'red').
            comment: Комментарий, опционально.

        Returns:
            True при успехе, False при ошибке или неудачной проверке.
        """
        pool = get_db_pool()
        try:
            auditory = await Database.get_auditory_by_name(auditory_name)
            if auditory is None:
                logger.error("Аудитория '%s' не найдена в БД", auditory_name)
                return False

            status_lower = status.lower()
            if status_lower not in Database.VALID_STATUSES:
                logger.error(
                    "Недопустимый статус '%s'. Допустимые: %s",
                    status,
                    ", ".join(Database.VALID_STATUSES),
                )
                return False

            auditory_id = auditory["id"]
            await pool.execute(
                """
                INSERT INTO status_log (auditory_id, status, comment, reported_by)
                VALUES ($1, $2, $3, $4)
                """,
                auditory_id,
                status_lower,
                comment,
                telegram_id,
            )
            logger.info(
                "Добавлен статус для пользователя %s, аудитория '%s': %s",
                telegram_id,
                auditory_name,
                status_lower,
            )
            return True
        except Exception as e:
            logger.error(
                "Ошибка при добавлении статуса (telegram_id=%s, auditory=%s): %s",
                telegram_id,
                auditory_name,
                e,
                exc_info=True,
            )
            return False

    @staticmethod
    async def get_today_events() -> List[Dict[str, Any]]:
        """
        Возвращает мероприятия на сегодня из календаря.

        Пока заглушка. В будущем будет получать данные из таблицы calendar_events.

        Returns:
            Пустой список.
        """
        return []

    @staticmethod
    async def get_latest_status(auditory_id: int) -> Optional[Dict[str, Any]]:
        """
        Возвращает последний статус аудитории.

        Args:
            auditory_id: ID аудитории.

        Returns:
            Словарь с данными последней записи status_log или None.
        """
        pool = get_db_pool()
        try:
            row = await pool.fetchrow(
                """
                SELECT * FROM status_log
                WHERE auditory_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                auditory_id,
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error(
                "Ошибка при получении последнего статуса auditory_id=%s: %s",
                auditory_id,
                e,
                exc_info=True,
            )
            return None

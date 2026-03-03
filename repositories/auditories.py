"""Репозиторий для работы с таблицей auditories.

Задачи модуля:
- инкапсулировать логику чтения активных аудиторий из базы;
- предоставить простой кэш «в памяти процесса» для частых операций;
- дать вспомогательные функции для получения аудитории и её имени по ID.

Кэширование:
    🔥 ВАЖНО: используется очень простой TTL‑кэш на несколько минут
    (см. `_AUDITORIES_CACHE_TTL`), чтобы снизить нагрузку на БД при частом
    показе списков аудиторий в интерфейсе бота. При обновлениях справочника
    аудиторий админ‑процессы могут вызывать `get_active_auditories(force_refresh=True)`,
    чтобы принудительно сбросить кэш.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from database import get_db_pool
from core.types import AuditoryRow


_AUDITORIES_CACHE_TTL = timedelta(minutes=5)
_auditories_cache: Optional[List[AuditoryRow]] = None
_auditories_cache_expires_at: Optional[datetime] = None


async def _load_active_auditories_from_db() -> List[AuditoryRow]:
    """
    Загружает из БД список активных аудиторий без использования кэша.

    Возвращает:
        Список словарей `AuditoryRow` с полями `id`, `name`, `building`.

    Примечания:
        ⚠️ ВНИМАНИЕ: эту функцию не следует вызывать напрямую из хендлеров,
        чтобы не обойти кэш. Используйте `get_active_auditories`.
    """
    pool = get_db_pool()
    rows = await pool.fetch(
        "SELECT id, name, building FROM auditories WHERE is_active = TRUE ORDER BY name"
    )
    return [dict(row) for row in rows]  # type: ignore[return-value]


async def get_active_auditories(force_refresh: bool = False) -> List[AuditoryRow]:
    """
    Возвращает список активных аудиторий, используя простой TTL‑кэш.

    Аргументы:
        force_refresh: если True — кэш игнорируется и данные перечитываются из БД.

    Возвращает:
        Список словарей `AuditoryRow` для всех активных аудиторий.

    Примечания:
        🔥 ВАЖНО: кэш живёт в памяти процесса бота. При рестарте приложения
        он очищается автоматически, поэтому TTL достаточно короткий (5 минут),
        чтобы данные не устаревали.
    """
    global _auditories_cache, _auditories_cache_expires_at

    now = datetime.now()
    if (
        not force_refresh
        and _auditories_cache is not None
        and _auditories_cache_expires_at is not None
        and now < _auditories_cache_expires_at
    ):
        return _auditories_cache

    _auditories_cache = await _load_active_auditories_from_db()
    _auditories_cache_expires_at = now + _AUDITORIES_CACHE_TTL
    return _auditories_cache


async def get_auditory_by_id(auditory_id: int) -> Optional[AuditoryRow]:
    """
    Возвращает аудиторию по ID, с приоритетным использованием кэша.

    Аргументы:
        auditory_id: первичный ключ аудитории.

    Возвращает:
        Cловарь `AuditoryRow` или None, если аудитория не найдена/не активна.

    Примечания:
        🔥 ВАЖНО: сначала проверяется кэш, затем, при отсутствии записи, выполняется
        прямой запрос в БД. Это позволяет находить недавно добавленные аудитории
        ещё до истечения TTL кэша.
    """
    # Сначала пробуем найти в кэше.
    auditories = await get_active_auditories()
    for a in auditories:
        if a.get("id") == auditory_id:
            return a

    # Если не нашли (например, аудитория была добавлена недавно) — читаем напрямую
    pool = get_db_pool()
    row = await pool.fetchrow(
        "SELECT id, name, building FROM auditories WHERE id = $1 AND is_active = TRUE",
        auditory_id,
    )
    return dict(row) if row else None  # type: ignore[return-value]


async def get_auditory_name_by_id(auditory_id: int) -> Optional[str]:
    """
    Возвращает техническое имя аудитории по ID.

    Аргументы:
        auditory_id: ID аудитории.

    Возвращает:
        Строку с техническим именем (поле `name`) или None.

    Использование:
        Функция полезна в обработчиках, где важно получить «сырой» код аудитории
        для внутренних связок, а человекочитаемое название уже строится через
        `utils.auditory_names.get_russian_name`.
    """
    auditory = await get_auditory_by_id(auditory_id)
    return auditory.get("name") if auditory else None


"""Репозиторий для работы с таблицей auditories.

Содержит кэширование часто используемого списка аудиторий,
чтобы уменьшить количество однотипных запросов к БД.
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
    pool = get_db_pool()
    rows = await pool.fetch(
        "SELECT id, name, building FROM auditories WHERE is_active = TRUE ORDER BY name"
    )
    return [dict(row) for row in rows]  # type: ignore[return-value]


async def get_active_auditories(force_refresh: bool = False) -> List[AuditoryRow]:
    """Возвращает список активных аудиторий с простым кэшем на несколько минут."""
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
    """Возвращает аудиторию по ID, используя кэш, если это возможно."""
    # Сначала пробуем найти в кэше
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
    """Возвращает техническое имя аудитории по ID."""
    auditory = await get_auditory_by_id(auditory_id)
    return auditory.get("name") if auditory else None


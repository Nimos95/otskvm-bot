"""Копия основных констант из core.constants для использования в Streamlit‑дашборде.

Важно:
- модуль не импортирует код бота, чтобы дашборд оставался полностью независимым;
- значения должны быть синхронизированы с core/constants.py при изменениях в боте.
"""

from __future__ import annotations

from typing import Final, Tuple


# Статусы аудиторий
STATUS_GREEN: Final[str] = "green"
STATUS_YELLOW: Final[str] = "yellow"
STATUS_RED: Final[str] = "red"

AUDITORY_STATUSES: Final[Tuple[str, ...]] = (
    STATUS_GREEN,
    STATUS_YELLOW,
    STATUS_RED,
)


# Статусы назначений мероприятий
ASSIGNMENT_STATUS_ASSIGNED: Final[str] = "assigned"
ASSIGNMENT_STATUS_ACCEPTED: Final[str] = "accepted"
ASSIGNMENT_STATUS_DONE: Final[str] = "done"
ASSIGNMENT_STATUS_CANCELLED: Final[str] = "cancelled"
ASSIGNMENT_STATUS_REPLACING: Final[str] = "replacing"
ASSIGNMENT_STATUS_REPLACEMENT_REQUESTED: Final[str] = "replacement_requested"

ASSIGNMENT_STATUSES_ACTIVE: Final[Tuple[str, ...]] = (
    ASSIGNMENT_STATUS_ASSIGNED,
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_REPLACING,
)


# Роли пользователей
ROLE_SUPERADMIN: Final[str] = "superadmin"
ROLE_ADMIN: Final[str] = "admin"
ROLE_MANAGER: Final[str] = "manager"
ROLE_ENGINEER: Final[str] = "engineer"
ROLE_VIEWER: Final[str] = "viewer"

ALL_ROLES: Final[Tuple[str, ...]] = (
    ROLE_SUPERADMIN,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_ENGINEER,
    ROLE_VIEWER,
)


# Типы уведомлений
NOTIFICATION_REMINDER: Final[str] = "reminder"
NOTIFICATION_COMPLETION_REMINDER: Final[str] = "completion_reminder"
NOTIFICATION_CONFIRMATION: Final[str] = "confirmation"
NOTIFICATION_MANUAL_COMPLETION: Final[str] = "manual_completion"
NOTIFICATION_EARLY_COMPLETION: Final[str] = "early_completion"


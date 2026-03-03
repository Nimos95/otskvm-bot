"""Общие типы данных (type hints) для проекта OTSKVM Bot."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional, TypedDict

from core.constants import (
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_ASSIGNED,
    ASSIGNMENT_STATUS_CANCELLED,
    ASSIGNMENT_STATUS_DONE,
    ASSIGNMENT_STATUS_REPLACEMENT_REQUESTED,
    STATUS_GREEN,
    STATUS_RED,
    STATUS_YELLOW,
)


StatusLiteral = Literal[STATUS_GREEN, STATUS_YELLOW, STATUS_RED]

AssignmentStatusLiteral = Literal[
    ASSIGNMENT_STATUS_ASSIGNED,
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_DONE,
    ASSIGNMENT_STATUS_CANCELLED,
    ASSIGNMENT_STATUS_REPLACEMENT_REQUESTED,
]


class UserRow(TypedDict, total=False):
    telegram_id: int
    full_name: str
    username: Optional[str]
    role: str
    created_at: datetime
    last_active: datetime
    is_active: bool


class AuditoryRow(TypedDict, total=False):
    id: int
    name: str
    building: Optional[str]
    floor: Optional[int]
    is_active: bool


class CalendarEventRow(TypedDict, total=False):
    id: int
    google_event_id: str
    auditory_id: Optional[int]
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    organizer: Optional[str]
    status: str
    last_sync: datetime


class EventAssignmentRow(TypedDict, total=False):
    id: int
    event_id: int
    assigned_to: int
    assigned_by: int
    assigned_at: datetime
    role: str
    status: str
    confirmed_at: Optional[datetime]
    completed_at: Optional[datetime]


JsonDict = Dict[str, object]
RowList = List[Dict[str, object]]


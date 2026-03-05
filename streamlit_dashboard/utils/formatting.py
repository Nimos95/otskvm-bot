from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd


def format_engineer_name(full_name: str, username: Optional[str] = None) -> str:
    """Возвращает человекочитаемое имя инженера для отображения в фильтрах и таблицах."""
    if username:
        return f"{full_name} (@{username})"
    return full_name


def format_date_range(start: date, end: date) -> str:
    """Форматирует диапазон дат в виде 'DD.MM.YYYY – DD.MM.YYYY'."""
    if start == end:
        return start.strftime("%d.%m.%Y")
    return f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}"


def format_datetime(dt: Optional[datetime]) -> str:
    """Форматирует дату/время для таблиц. При отсутствии значения возвращает дефис."""
    if dt is None:
        return "—"
    # Поддержка pandas.NaT и других «пустых» значений
    try:
        if pd.isna(dt):
            return "—"
    except Exception:
        pass
    return dt.strftime("%d.%m.%Y %H:%M")


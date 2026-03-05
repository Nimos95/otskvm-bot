from __future__ import annotations

import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import pandas as pd
import streamlit as st

from database.connection import get_connection
from utils.constants import ROLE_ENGINEER, ROLE_MANAGER, ROLE_SUPERADMIN


ENGINEER_ROLES: Sequence[str] = (ROLE_ENGINEER, ROLE_MANAGER, ROLE_SUPERADMIN)


def _query_to_dataframe(query: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """Выполняет SELECT и возвращает DataFrame без использования read_sql_query (нет ворнингов pandas)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def get_active_engineers() -> pd.DataFrame:
    """Возвращает список активных инженеров и менеджеров.

    Колонки: telegram_id, full_name, username, role.
    """
    query = """
        SELECT telegram_id, full_name, username, role
        FROM users
        WHERE is_active = TRUE
          AND role = ANY(%s)
        ORDER BY full_name
    """
    return _query_to_dataframe(query, (list(ENGINEER_ROLES),))


@st.cache_data(ttl=300)
def get_active_buildings() -> List[str]:
    """Возвращает список корпусов, в которых есть активные аудитории."""
    query = """
        SELECT DISTINCT building
        FROM auditories
        WHERE is_active = TRUE
          AND building IS NOT NULL
        ORDER BY building
    """
    df = _query_to_dataframe(query)
    return df["building"].dropna().astype(str).tolist()


@st.cache_data(ttl=300)
def get_activity(
    start_date: date,
    end_date: date,
    engineer_ids: Optional[Iterable[int]] = None,
    building: Optional[str] = None,
) -> pd.DataFrame:
    """Возвращает сырые записи активности инженеров из status_log.

    Фильтры:
        - по дате (включительно);
        - по списку telegram_id инженеров;
        - по корпусу (building) аудитории.

    Колонки:
        telegram_id, full_name, username, role,
        created_at, activity_date, activity_hour, activity_weekday,
        building.
    """
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    base_query = """
        SELECT
            sl.reported_by AS telegram_id,
            u.full_name,
            u.username,
            u.role,
            sl.created_at,
            DATE(sl.created_at) AS activity_date,
            EXTRACT(HOUR FROM sl.created_at) AS activity_hour,
            EXTRACT(DOW FROM sl.created_at) AS activity_weekday,
            a.building
        FROM status_log sl
        JOIN users u ON u.telegram_id = sl.reported_by
        LEFT JOIN auditories a ON a.id = sl.auditory_id
        WHERE sl.created_at >= %s
          AND sl.created_at < %s
          AND u.is_active = TRUE
          AND u.role = ANY(%s)
    """

    params: List[object] = [start_dt, end_dt_exclusive, list(ENGINEER_ROLES)]

    # Безопасно приводим список инженеров к int, отбрасывая мусорные значения.
    if engineer_ids:
        cleaned_ids: List[int] = []
        for value in engineer_ids:
            try:
                cleaned_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        if cleaned_ids:
            base_query += " AND sl.reported_by = ANY(%s)"
            params.append(cleaned_ids)

    if building:
        base_query += " AND a.building = %s"
        params.append(building)

    base_query += " ORDER BY sl.created_at"

    df = _query_to_dataframe(base_query, tuple(params))

    if df.empty:
        return df

    # Явно и устойчиво к ошибкам приводим типы (без ворнингов о формате).
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        if "activity_date" in df.columns:
            df["activity_date"] = pd.to_datetime(
                df["activity_date"],
                errors="coerce",
            ).dt.date
        else:
            df["activity_date"] = df["created_at"].dt.date

    if "activity_hour" in df.columns:
        df["activity_hour"] = pd.to_numeric(
            df["activity_hour"],
            errors="coerce",
        ).astype("Int64")
    else:
        df["activity_hour"] = df["created_at"].dt.hour.astype("Int64")

    if "activity_weekday" in df.columns:
        df["activity_weekday"] = pd.to_numeric(
            df["activity_weekday"],
            errors="coerce",
        ).astype("Int64")
    else:
        df["activity_weekday"] = df["created_at"].dt.dayofweek.astype("Int64")

    return df


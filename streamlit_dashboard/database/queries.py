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
from utils.constants import (
    ASSIGNMENT_STATUS_DONE,
    ROLE_ENGINEER,
    ROLE_MANAGER,
    ROLE_SUPERADMIN,
)


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


@st.cache_data(ttl=300)
def get_events_kpi(
    start_date: date,
    end_date: date,
    engineer_id: Optional[int] = None,
) -> dict:
    """Возвращает KPI по мероприятиям за период.

    Показатели:
        - total_events: всего мероприятий за период;
        - completed_events: мероприятий со статусом «done»;
        - active_engineers: количество уникальных инженеров;
        - avg_per_day: среднее количество мероприятий в день.
    """
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    base_query = """
        SELECT
            COUNT(DISTINCT ce.id) AS total_events,
            COUNT(DISTINCT CASE WHEN ea.status = %s THEN ce.id END) AS completed_events,
            COUNT(DISTINCT u.telegram_id) AS active_engineers
        FROM calendar_events ce
        JOIN event_assignments ea ON ce.id = ea.event_id
        JOIN users u ON ea.assigned_to = u.telegram_id
        WHERE ce.start_time >= %s
          AND ce.start_time < %s
          AND u.is_active = TRUE
          AND u.role = ANY(%s)
    """

    params: List[object] = [
        ASSIGNMENT_STATUS_DONE,
        start_dt,
        end_dt_exclusive,
        list(ENGINEER_ROLES),
    ]

    if engineer_id is not None:
        try:
            engineer_id_int = int(engineer_id)
        except (TypeError, ValueError):
            engineer_id_int = None
        if engineer_id_int is not None:
            base_query += " AND ea.assigned_to = %s"
            params.append(engineer_id_int)

    df = _query_to_dataframe(base_query, tuple(params))
    if df.empty:
        total_events = 0
        completed_events = 0
        active_engineers = 0
    else:
        row = df.iloc[0]
        total_events = int(row.get("total_events") or 0)
        completed_events = int(row.get("completed_events") or 0)
        active_engineers = int(row.get("active_engineers") or 0)

    period_days = max(1, (end_date - start_date).days + 1)
    avg_per_day = round(total_events / period_days, 1) if total_events else 0.0

    return {
        "total_events": total_events,
        "completed_events": completed_events,
        "active_engineers": active_engineers,
        "avg_per_day": avg_per_day,
    }


@st.cache_data(ttl=300)
def get_events_by_day(
    start_date: date,
    end_date: date,
    engineer_id: Optional[int] = None,
) -> pd.DataFrame:
    """Возвращает агрегированную по дням активность по мероприятиям."""
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    base_query = """
        SELECT
            DATE(ce.start_time) AS date,
            COUNT(ce.id) AS count
        FROM calendar_events ce
        JOIN event_assignments ea ON ce.id = ea.event_id
        JOIN users u ON ea.assigned_to = u.telegram_id
        WHERE ce.start_time >= %s
          AND ce.start_time < %s
          AND u.is_active = TRUE
          AND u.role = ANY(%s)
    """

    params: List[object] = [start_dt, end_dt_exclusive, list(ENGINEER_ROLES)]

    if engineer_id is not None:
        try:
            engineer_id_int = int(engineer_id)
        except (TypeError, ValueError):
            engineer_id_int = None
        if engineer_id_int is not None:
            base_query += " AND ea.assigned_to = %s"
            params.append(engineer_id_int)

    base_query += """
        GROUP BY DATE(ce.start_time)
        ORDER BY date
    """

    df = _query_to_dataframe(base_query, tuple(params))
    if df.empty:
        return df

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    return df


@st.cache_data(ttl=300)
def get_events_per_engineer_stats(
    start_date: date,
    end_date: date,
    engineer_id: Optional[int] = None,
) -> pd.DataFrame:
    """Возвращает агрегированную статистику по мероприятиям для каждого инженера.

    Колонки:
        - full_name — ФИО инженера;
        - events_count — количество мероприятий;
        - days_active — количество дней с мероприятиями;
        - first_activity — дата первой активности;
        - last_activity — дата последней активности.
    """
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    base_query = """
        SELECT
            u.full_name,
            COUNT(ce.id) AS events_count,
            COUNT(DISTINCT DATE(ce.start_time)) AS days_active,
            MIN(DATE(ce.start_time)) AS first_activity,
            MAX(DATE(ce.start_time)) AS last_activity
        FROM users u
        JOIN event_assignments ea ON u.telegram_id = ea.assigned_to
        JOIN calendar_events ce ON ea.event_id = ce.id
        WHERE ce.start_time >= %s
          AND ce.start_time < %s
          AND u.is_active = TRUE
          AND u.role = ANY(%s)
    """

    params: List[object] = [start_dt, end_dt_exclusive, list(ENGINEER_ROLES)]

    if engineer_id is not None:
        try:
            engineer_id_int = int(engineer_id)
        except (TypeError, ValueError):
            engineer_id_int = None
        if engineer_id_int is not None:
            base_query += " AND ea.assigned_to = %s"
            params.append(engineer_id_int)

    base_query += """
        GROUP BY u.telegram_id, u.full_name
        ORDER BY events_count DESC
    """

    df = _query_to_dataframe(base_query, tuple(params))
    if df.empty:
        return df

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for col in ("first_activity", "last_activity"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    return df


@st.cache_data(ttl=300)
def get_active_auditories_with_latest_status() -> pd.DataFrame:
    """Возвращает список активных аудиторий с их последним статусом.

    Колонки:
        - id — идентификатор аудитории;
        - building — корпус;
        - name — название аудитории;
        - floor — этаж;
        - equipment — оборудование;
        - current_status — последний статус (green/yellow/red/none);
        - comment — комментарий к последнему статусу;
        - last_update — дата/время последнего обновления;
        - last_reporter — ФИО инженера, оставившего последнюю отметку.
    """
    query = """
        WITH latest_status AS (
            SELECT DISTINCT ON (auditory_id)
                auditory_id,
                status,
                comment,
                created_at,
                reported_by
            FROM status_log
            ORDER BY auditory_id, created_at DESC
        )
        SELECT
            a.id,
            a.building,
            a.name,
            a.floor,
            a.equipment,
            COALESCE(ls.status, 'none') AS current_status,
            ls.comment,
            ls.created_at AS last_update,
            u.full_name AS last_reporter
        FROM auditories a
        LEFT JOIN latest_status ls ON a.id = ls.auditory_id
        LEFT JOIN users u ON ls.reported_by = u.telegram_id
        WHERE a.is_active = TRUE
        ORDER BY a.building, a.name
    """
    df = _query_to_dataframe(query)
    if df.empty:
        return df

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        if "last_update" in df.columns:
            df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")

    return df


def get_auditory_status_history(auditory_id: int) -> pd.DataFrame:
    """Возвращает полную историю статусов для выбранной аудитории за последние 90 дней.

    Колонки:
        - created_at — дата и время отметки;
        - status — статус (green/yellow/red);
        - comment — комментарий;
        - engineer — ФИО инженера.
    """
    query = """
        SELECT
            sl.created_at,
            sl.status,
            sl.comment,
            u.full_name AS engineer
        FROM status_log sl
        JOIN users u ON sl.reported_by = u.telegram_id
        WHERE sl.auditory_id = %s
          AND sl.created_at > NOW() - INTERVAL '90 days'
        ORDER BY sl.created_at DESC
    """
    df = _query_to_dataframe(query, (auditory_id,))
    if df.empty:
        return df

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    return df


def get_auditory_stats(auditory_id: int) -> dict:
    """Возвращает агрегированную статистику по аудитории за последние 90 дней."""
    query = """
        SELECT
            COUNT(*) AS total_marks,
            COUNT(CASE WHEN status = 'red' THEN 1 END) AS red_count,
            COUNT(CASE WHEN status = 'yellow' THEN 1 END) AS yellow_count,
            COUNT(CASE WHEN status = 'green' THEN 1 END) AS green_count,
            MIN(created_at) AS first_mark,
            MAX(created_at) AS last_mark
        FROM status_log
        WHERE auditory_id = %s
          AND created_at > NOW() - INTERVAL '90 days'
    """
    df = _query_to_dataframe(query, (auditory_id,))
    if df.empty:
        return {
            "total_marks": 0,
            "red_count": 0,
            "yellow_count": 0,
            "green_count": 0,
            "first_mark": None,
            "last_mark": None,
        }

    row = df.iloc[0]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        first_mark = pd.to_datetime(row.get("first_mark"), errors="coerce")
        last_mark = pd.to_datetime(row.get("last_mark"), errors="coerce")

    return {
        "total_marks": int(row.get("total_marks") or 0),
        "red_count": int(row.get("red_count") or 0),
        "yellow_count": int(row.get("yellow_count") or 0),
        "green_count": int(row.get("green_count") or 0),
        "first_mark": first_mark,
        "last_mark": last_mark,
    }


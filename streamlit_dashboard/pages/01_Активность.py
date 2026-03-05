"""Основная страница: активность инженеров за период с KPI, графиками и таблицей."""

from __future__ import annotations

import sys
from pathlib import Path

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import pandas as pd
import streamlit as st

from components.charts import render_events_daily_line_chart, render_events_top10_bar
from components.filters import render_filters
from components.metrics import render_metrics
from database.queries import (
    get_events_by_day,
    get_events_kpi,
    get_events_per_engineer_stats,
)
from utils.formatting import format_date_range


st.set_page_config(page_title="Активность | OTSKVM Bot", page_icon="📊", layout="wide")

st.title("Активность")

start_date, end_date, engineer_id, applied = render_filters()

st.caption(format_date_range(start_date, end_date))

# KPI по мероприятиям
kpi = get_events_kpi(start_date, end_date, engineer_id=engineer_id)
render_metrics(
    total_events=kpi["total_events"],
    completed_events=kpi["completed_events"],
    active_engineers=kpi["active_engineers"],
    avg_per_day=kpi["avg_per_day"],
)

# График 1: активность по дням
st.subheader("Активность по дням")
daily_df = get_events_by_day(start_date, end_date, engineer_id=engineer_id)
render_events_daily_line_chart(daily_df)

# График 2: топ-10 инженеров
st.subheader("Топ-10 инженеров за период")
stats_df = get_events_per_engineer_stats(start_date, end_date, engineer_id=engineer_id)
if stats_df.empty:
    st.info("Нет данных для отображения топ-10 инженеров.")
else:
    top10_df = stats_df.sort_values("events_count", ascending=True).tail(10)
    render_events_top10_bar(top10_df)

# Таблица с детализацией по инженерам
st.subheader("Детализация по инженерам")
if stats_df.empty:
    st.info("Нет данных за выбранный период.")
else:
    table_df = stats_df.copy()
    # Среднее количество мероприятий в день для каждого инженера
    table_df["avg_per_day"] = table_df.apply(
        lambda row: round(row["events_count"] / row["days_active"], 1)
        if row.get("days_active")
        else 0.0,
        axis=1,
    )

    # Форматируем даты в ДД.ММ.ГГГГ
    for col in ("first_activity", "last_activity"):
        table_df[col] = pd.to_datetime(table_df[col], errors="coerce").dt.strftime("%d.%m.%Y")
        table_df[col] = table_df[col].fillna("—")

    display_df = table_df[
        ["full_name", "events_count", "days_active", "avg_per_day", "first_activity", "last_activity"]
    ].copy()
    display_df.columns = [
        "Инженер",
        "Мероприятий",
        "Дней",
        "В среднем",
        "Первая активность",
        "Последняя активность",
    ]

    st.dataframe(display_df, width="stretch", hide_index=True)


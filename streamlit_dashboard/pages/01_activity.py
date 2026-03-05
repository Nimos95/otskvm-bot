"""Основная страница: активность инженеров за период с KPI, графиками и таблицей."""

from __future__ import annotations

import sys
from pathlib import Path

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import pandas as pd
import streamlit as st

from components.charts import render_heatmap, render_line_chart, render_top10_bar
from components.filters import render_filters
from components.metrics import render_metrics
from database.queries import get_activity
from utils.formatting import format_date_range, format_datetime


st.set_page_config(page_title="Активность | OTSKVM Bot", page_icon="📊", layout="wide")

st.title("Активность инженеров")

start_date, end_date, engineer_ids, building, applied = render_filters()

df = get_activity(start_date, end_date, engineer_ids=engineer_ids, building=building)

st.caption(format_date_range(start_date, end_date))
render_metrics(df, start_date, end_date)

st.subheader("Активность по дням")
group_by_engineer = st.checkbox("Группировать по инженерам", value=False, key="group_line")
render_line_chart(df, group_by_engineer=group_by_engineer)

st.subheader("Топ-10 инженеров за период")
render_top10_bar(df)

st.subheader("Активность по часам и дням недели")
render_heatmap(df)

st.subheader("Детализация по инженерам")
if df.empty:
    st.info("Нет данных за выбранный период.")
else:
    agg = (
        df.groupby(["telegram_id", "full_name"])
        .agg(
            marks=("created_at", "count"),
            days=("activity_date", "nunique"),
            first_activity=("created_at", "min"),
            last_activity=("created_at", "max"),
        )
        .reset_index()
    )
    agg.columns = ["telegram_id", "Имя", "Отметок", "Дней с активностью", "Первая активность", "Последняя активность"]
    agg["Первая активность"] = agg["Первая активность"].apply(format_datetime)
    agg["Последняя активность"] = agg["Последняя активность"].apply(format_datetime)

    display_cols = ["Имя", "Отметок", "Дней с активностью", "Первая активность", "Последняя активность"]
    st.dataframe(agg[display_cols], width="stretch", hide_index=True)

    st.caption("Подробная статистика по каждому инженеру — на странице «По инженерам».")
    if st.button("Перейти к детализации по инженерам"):
        st.switch_page("pages/02_engineers.py")

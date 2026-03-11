"""Детальная страница по инженерам: выбор инженера и его активность."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import pandas as pd
import streamlit as st

from database.queries import get_active_engineers, get_activity
from utils.formatting import format_engineer_name, format_datetime
from utils.auditory_names import get_russian_name


st.set_page_config(page_title="Инженеры | OTSKVM Bot", page_icon="👤", layout="wide")

st.title("Инженеры")

engineers_df = get_active_engineers()
if engineers_df.empty:
    st.warning("Нет активных инженеров в системе.")
    st.stop()

options = []
for _, row in engineers_df.iterrows():
    label = format_engineer_name(row["full_name"], row.get("username"))
    if row.get("role"):
        label += f" ({row['role']})"
    options.append((row["telegram_id"], label))

selected_label = st.selectbox(
    "Выберите инженера",
    options=[opt[1] for opt in options],
    key="engineer_select",
)
if not selected_label:
    st.stop()

id_by_label = {opt[1]: opt[0] for opt in options}
engineer_id = id_by_label[selected_label]
today = date.today()
start = today - timedelta(days=29)
end = today

df = get_activity(start, end, engineer_ids=[engineer_id], building=None)
if df.empty:
    st.info("Нет активности за последние 30 дней для выбранного инженера.")
    st.stop()

total_marks = len(df)
days_active = df["activity_date"].nunique()
first_ts = df["created_at"].min()
last_ts = df["created_at"].max()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Отметок за период", total_marks)
c2.metric("Дней с активностью", days_active)
c3.metric("Первая активность", format_datetime(first_ts))
c4.metric("Последняя активность", format_datetime(last_ts))

st.subheader("Записи активности")
df_display = df[["created_at", "activity_date", "activity_hour", "building"]].copy()
df_display["created_at"] = df_display["created_at"].apply(format_datetime)
df_display["building"] = df_display["building"].astype(str).apply(get_russian_name)
df_display.columns = ["Дата и время", "Дата", "Час", "Корпус"]
st.dataframe(df_display, width="stretch", hide_index=True)


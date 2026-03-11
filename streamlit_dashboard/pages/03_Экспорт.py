"""Экспорт данных активности в CSV."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import pandas as pd
import streamlit as st

from database.queries import get_activity
from utils.auditory_names import get_russian_name
from utils.formatting import format_date_range


st.set_page_config(page_title="Экспорт | OTSKVM Bot", page_icon="📥", layout="wide")

st.title("Экспорт")

start = st.date_input("Начало периода", value=date.today() - timedelta(days=6), key="export_start")
end = st.date_input("Конец периода", value=date.today(), key="export_end")
if start > end:
    start, end = end, start

df = get_activity(start, end, engineer_ids=None, building=None)

if df.empty:
    st.info("Нет данных за выбранный период.")
    st.stop()

if "building" in df.columns:
    df = df.copy()
    df["building"] = df["building"].astype(str).apply(get_russian_name)

st.caption(f"Период: {format_date_range(start, end)}. Записей: {len(df)}.")

csv = df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Скачать CSV",
    data=csv,
    file_name=f"activity_{start:%Y-%m-%d}_{end:%Y-%m-%d}.csv",
    mime="text/csv",
    key="download_csv",
)

st.dataframe(df.head(100), width="stretch", hide_index=True)
if len(df) > 100:
    st.caption("Показаны первые 100 записей. В CSV — все данные.")


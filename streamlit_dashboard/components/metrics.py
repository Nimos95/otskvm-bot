"""KPI-карточки: всего инженеров, отметок, дней с активностью, средняя активность в день."""

from __future__ import annotations

import sys
from pathlib import Path

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import pandas as pd
import streamlit as st


def render_metrics(df: pd.DataFrame, start_date, end_date) -> None:
    """Отрисовывает четыре KPI-карточки над основным контентом."""
    if df.empty:
        total_engineers = 0
        total_marks = 0
        days_with_activity = 0
        avg_per_day = 0.0
    else:
        total_engineers = df["telegram_id"].nunique()
        total_marks = len(df)
        days_with_activity = df["activity_date"].nunique()
        period_days = max(1, (end_date - start_date).days + 1)
        avg_per_day = round(total_marks / period_days, 1)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего инженеров", total_engineers)
    with col2:
        st.metric("Всего отметок за период", total_marks)
    with col3:
        st.metric("Дней с активностью", days_with_activity)
    with col4:
        st.metric("Средняя активность в день", avg_per_day)

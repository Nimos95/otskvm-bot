"""KPI-карточки: мероприятия за период и активные инженеры."""

from __future__ import annotations

import sys
from pathlib import Path

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import streamlit as st


def render_metrics(
    total_events: int,
    completed_events: int,
    active_engineers: int,
    avg_per_day: float,
) -> None:
    """Отрисовывает четыре KPI-карточки по мероприятиям."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего мероприятий за период", total_events)
    with col2:
        st.metric("Проведено мероприятий (done)", completed_events)
    with col3:
        st.metric("Активных инженеров", active_engineers)
    with col4:
        st.metric("В среднем в день", avg_per_day)

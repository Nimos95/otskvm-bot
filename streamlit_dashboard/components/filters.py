"""Боковая панель с фильтрами периода и инженера."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Tuple

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import streamlit as st

from database.queries import get_active_engineers
from utils.formatting import format_engineer_name


def render_filters() -> Tuple[date, date, Optional[int], bool]:
    """Отрисовывает боковую панель с фильтрами периода и инженера.

    Возвращает:
        (start_date, end_date, engineer_id_or_none, applied),
        где applied = True после нажатия «Применить».
    """
    engineers_df = get_active_engineers()

    with st.sidebar:
        st.subheader("Фильтры")

        # Период: предустановки + произвольный
        period_preset = st.selectbox(
            "Период",
            ["Сегодня", "Неделя", "Месяц", "Произвольный"],
            index=1,
            key="period_preset",
        )

        today = date.today()
        if period_preset == "Сегодня":
            start_date = end_date = today
            st.date_input("Начало", value=start_date, disabled=True, key="start_date")
            st.date_input("Конец", value=end_date, disabled=True, key="end_date")
        elif period_preset == "Неделя":
            start_date = today - timedelta(days=6)
            end_date = today
            st.date_input("Начало", value=start_date, disabled=True, key="start_date")
            st.date_input("Конец", value=end_date, disabled=True, key="end_date")
        elif period_preset == "Месяц":
            start_date = today - timedelta(days=29)
            end_date = today
            st.date_input("Начало", value=start_date, disabled=True, key="start_date")
            st.date_input("Конец", value=end_date, disabled=True, key="end_date")
        else:
            start_date = st.date_input("Начало", value=today - timedelta(days=6), key="start_date")
            end_date = st.date_input("Конец", value=today, key="end_date")
            if start_date and end_date and start_date > end_date:
                start_date, end_date = end_date, start_date

        # Выбор инженера
        options = []
        for _, row in engineers_df.iterrows():
            label = format_engineer_name(
                row["full_name"],
                row.get("username"),
            )
            if row.get("role"):
                label += f" ({row['role']})"
            options.append((row["telegram_id"], label))

        engineer_labels = ["Все инженеры"] + [opt[1] for opt in options]
        selected_label = st.selectbox(
            "Инженер",
            options=engineer_labels,
            key="engineer_selectbox",
        )
        engineer_id: Optional[int] = None
        if selected_label and selected_label != "Все инженеры":
            id_by_label = {opt[1]: opt[0] for opt in options}
            engineer_id = id_by_label.get(selected_label)

        applied = st.button("Применить", type="primary", key="apply_filters")

    # Если не нажали «Применить», возвращаем дефолтный период и пустые фильтры
    if not applied:
        if period_preset == "Сегодня":
            return today, today, None, False
        if period_preset == "Неделя":
            return today - timedelta(days=6), today, None, False
        if period_preset == "Месяц":
            return today - timedelta(days=29), today, None, False
        start_date = st.session_state.get("start_date", today - timedelta(days=6))
        end_date = st.session_state.get("end_date", today)
        return start_date, end_date, None, False

    return start_date, end_date, engineer_id, True


def get_period_dates_for_display(
    preset: str,
    custom_start: Optional[date] = None,
    custom_end: Optional[date] = None,
) -> Tuple[date, date]:
    """Возвращает (start_date, end_date) для отображения после применения фильтра."""
    today = date.today()
    if preset == "Сегодня":
        return today, today
    if preset == "Неделя":
        return today - timedelta(days=6), today
    if preset == "Месяц":
        return today - timedelta(days=29), today
    if custom_start and custom_end:
        return custom_start, custom_end
    return today - timedelta(days=6), today

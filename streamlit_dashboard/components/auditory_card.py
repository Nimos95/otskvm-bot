"""Карточка с подробной информацией об аудитории."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import streamlit as st


def render_auditory_card(
    name: str,
    building: str,
    floor: Optional[int] = None,
    equipment: Optional[str] = None,
    status_display: str = "",
    last_update_display: str = "—",
    reporter: Optional[str] = None,
    comment: Optional[str] = None,
) -> None:
    """Отрисовывает карточку с информацией об аудитории."""
    st.subheader(f"Аудитория {name}")

    with st.container():
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown(f"**Корпус:** {building or '—'}")
            if floor is not None:
                st.markdown(f"**Этаж:** {floor}")
            st.markdown(f"**Текущий статус:** {status_display or '⚪ Нет данных'}")

        with col_right:
            st.markdown(f"**Последнее обновление:** {last_update_display}")
            if reporter:
                st.markdown(f"**Кто отметил:** {reporter}")

        if equipment:
            st.markdown("**Оборудование:**")
            st.write(equipment)

        if comment:
            st.markdown("**Комментарий к последнему статусу:**")
            st.info(comment)


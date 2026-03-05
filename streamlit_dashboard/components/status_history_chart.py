"""График истории статусов аудитории."""

from __future__ import annotations

import sys
from pathlib import Path

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


STATUS_TO_LEVEL = {
    "green": 2,
    "yellow": 1,
    "red": 0,
    "none": -1,
}

LEVEL_TO_LABEL = {
    2: "🟢 Зеленый",
    1: "🟡 Желтый",
    0: "🔴 Красный",
    -1: "⚪ Нет данных",
}


def render_status_history_chart(history_df: pd.DataFrame) -> None:
    """Отрисовывает линейный график истории статусов за последние 30 дней."""
    if history_df.empty:
        st.info("Нет данных для графика истории статусов.")
        return

    df = history_df.copy()
    if "created_at" not in df.columns or "status" not in df.columns:
        st.info("Недостаточно данных для построения графика.")
        return

    with pd.option_context("mode.use_inf_as_na", True):
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    df = df.dropna(subset=["created_at"])
    if df.empty:
        st.info("Нет корректных данных для графика истории статусов.")
        return

    # Оставляем только последние 30 дней для визуализации
    max_date = df["created_at"].max()
    min_date = max_date.normalize() - pd.Timedelta(days=30)
    df = df[df["created_at"] >= min_date]

    df = df.sort_values("created_at")
    df["level"] = df["status"].map(STATUS_TO_LEVEL).fillna(-1)

    fig = go.Figure(
        data=go.Scatter(
            x=df["created_at"],
            y=df["level"],
            mode="lines+markers",
            line=dict(shape="hv", width=2),
            marker=dict(size=8),
            hovertemplate="Дата: %{x|%d.%m %H:%M}<br>Статус: %{customdata}<extra></extra>",
            customdata=[
                LEVEL_TO_LABEL.get(int(level), "⚪ Нет данных") for level in df["level"]
            ],
        )
    )

    fig.update_layout(
        title="История статусов за последние 30 дней",
        xaxis_title="Дата",
        yaxis_title="Статус",
        height=350,
        yaxis=dict(
            tickmode="array",
            tickvals=list(LEVEL_TO_LABEL.keys()),
            ticktext=list(LEVEL_TO_LABEL.values()),
            range=[-1.2, 2.2],
        ),
        xaxis=dict(tickformat="%d.%m"),
        margin=dict(l=60, r=20, t=60, b=40),
    )

    st.plotly_chart(fig, width="stretch")


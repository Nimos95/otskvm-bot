"""Графики: линейный по дням, топ-10 инженеров, тепловая карта по часам и дням недели."""

from __future__ import annotations

import sys
from pathlib import Path

_dash_root = Path(__file__).resolve().parents[1]
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def render_line_chart(df: pd.DataFrame, group_by_engineer: bool) -> None:
    """Линейный график активности по дням. При group_by_engineer — по каждому инженеру отдельная линия."""
    if df.empty:
        st.info("Нет данных для графика.")
        return

    if group_by_engineer:
        daily = df.groupby(["activity_date", "full_name"]).size().reset_index(name="count")
    else:
        daily = df.groupby("activity_date").size().reset_index(name="count")

    if group_by_engineer:
        fig = px.line(
            daily,
            x="activity_date",
            y="count",
            color="full_name",
            title="Активность по дням (по инженерам)",
            labels={"activity_date": "Дата", "count": "Количество отметок", "full_name": "Инженер"},
        )
    else:
        fig = px.line(
            daily,
            x="activity_date",
            y="count",
            title="Активность по дням",
            labels={"activity_date": "Дата", "count": "Количество отметок"},
        )
    fig.update_layout(xaxis_tickformat="%d.%m", height=350)
    st.plotly_chart(fig, width="stretch")


def render_top10_bar(df: pd.DataFrame) -> None:
    """Столбчатая диаграмма топ-10 инженеров за период."""
    if df.empty:
        st.info("Нет данных для графика.")
        return

    top = df.groupby("full_name").size().sort_values(ascending=True).tail(10)
    fig = px.bar(
        x=top.values,
        y=top.index,
        orientation="h",
        title="Топ-10 инженеров за период",
        labels={"x": "Количество отметок", "y": "Инженер"},
    )
    fig.update_layout(height=400, margin=dict(l=120))
    st.plotly_chart(fig, width="stretch")


def render_heatmap(df: pd.DataFrame) -> None:
    """Тепловая карта: часы (0–23) по оси X, дни недели (Пн–Вс) по Y."""
    if df.empty or "activity_hour" not in df.columns or "activity_weekday" not in df.columns:
        st.info("Нет данных для тепловой карты.")
        return

    # DOW в PostgreSQL: 0 = Sunday. Приводим к Пн=0.
    df = df.copy()
    df["weekday_shifted"] = (df["activity_weekday"] - 1) % 7
    cross = df.groupby(["weekday_shifted", "activity_hour"]).size().reset_index(name="count")
    pivot = cross.pivot(index="weekday_shifted", columns="activity_hour", values="count").fillna(0)

    # Упорядочиваем дни Пн–Вс и часы 0–23
    pivot = pivot.reindex(index=range(7), columns=range(24), fill_value=0)
    pivot.index = [WEEKDAY_NAMES[i] for i in range(7)]

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[str(i) for i in range(24)],
            y=pivot.index.tolist(),
            colorscale="Blues",
            hovertemplate="День: %{y}<br>Час: %{x}<br>Отметок: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Активность по часам и дням недели",
        xaxis_title="Час",
        yaxis_title="День недели",
        height=400,
    )
    st.plotly_chart(fig, width="stretch")


def render_events_daily_line_chart(daily_df: pd.DataFrame) -> None:
    """Линейный график количества мероприятий по дням."""
    if daily_df.empty:
        st.info("Нет данных для графика.")
        return

    fig = px.line(
        daily_df,
        x="date",
        y="count",
        title="Активность по дням",
        labels={"date": "Дата", "count": "Количество мероприятий"},
    )
    fig.update_layout(xaxis_tickformat="%d.%m", height=350)
    st.plotly_chart(fig, width="stretch")


def render_events_top10_bar(top_df: pd.DataFrame) -> None:
    """Горизонтальная диаграмма топ-10 инженеров по количеству мероприятий."""
    if top_df.empty:
        st.info("Нет данных для графика.")
        return

    # Сортируем от меньшего к большему, чтобы самые активные были сверху.
    top_sorted = top_df.sort_values("events_count", ascending=True)
    fig = px.bar(
        top_sorted,
        x="events_count",
        y="full_name",
        orientation="h",
        title="Топ-10 инженеров по мероприятиям",
        labels={"events_count": "Количество мероприятий", "full_name": "Инженер"},
    )
    fig.update_layout(height=400, margin=dict(l=120))
    st.plotly_chart(fig, width="stretch")

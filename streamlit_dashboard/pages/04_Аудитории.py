"""Страница dашборда: актуальное состояние аудиторий и история статусов."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

_dash_root = Path(__file__).resolve().parent
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

from components.auditory_card import render_auditory_card
from components.status_history_chart import render_status_history_chart
from database.queries import (
    get_active_auditories_with_latest_status,
    get_active_buildings,
    get_auditory_stats,
    get_auditory_status_history,
)
from utils.auditory_names import get_russian_name
from utils.translit import to_cyrillic


STATUS_LABELS: Dict[str, str] = {
    "green": "🟢 Зеленый",
    "yellow": "🟡 Желтый",
    "red": "🔴 Красный",
    "none": "⚪ Нет данных",
}


def _format_datetime_short(dt: Optional[datetime]) -> str:
    """Форматирует дату/время как DD.MM HH:MM."""
    if dt is None:
        return "—"
    try:
        if pd.isna(dt):
            return "—"
    except Exception:
        pass
    return dt.strftime("%d.%m %H:%M")


def _status_to_label(status_code: Optional[str]) -> str:
    code = (status_code or "none").lower()
    return STATUS_LABELS.get(code, STATUS_LABELS["none"])


def _highlight_problem_auditories(row: pd.Series) -> list[str]:
    """Подсветка строк с проблемными (красными) аудиториями."""
    status = str(row.get("current_status") or "").lower()
    if status == "red":
        return ["background-color: rgba(255, 0, 0, 0.12)"] * len(row)
    return [""] * len(row)


st.set_page_config(
    page_title="OTSKVM Bot — Аудитории",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏢 СОСТОЯНИЕ АУДИТОРИЙ")


# Фильтры
try:
    buildings = get_active_buildings()
except Exception:
    st.error("Не удалось получить список корпусов из базы данных. Проверьте подключение к БД.")
    st.stop()

with st.sidebar:
    st.subheader("Фильтры по аудиториям")

    search_text = st.text_input("Поиск по названию аудитории", key="auditory_search").strip()

    building_options = ["Все корпуса"] + buildings
    selected_building = st.selectbox(
        "Корпус",
        options=building_options,
        index=0,
        key="auditory_building",
        format_func=lambda x: x if x == "Все корпуса" else get_russian_name(str(x)),
    )

    status_filter_options = {
        "all": "Все статусы",
        "green": "🟢 Зеленый",
        "yellow": "🟡 Желтый",
        "red": "🔴 Красный",
    }
    selected_status_label = st.selectbox(
        "Текущий статус",
        options=list(status_filter_options.values()),
        index=0,
        key="auditory_status",
    )
    # Обратное отображение лейбла в код статуса
    label_to_code = {v: k for k, v in status_filter_options.items()}
    selected_status_code = label_to_code.get(selected_status_label, "all")

    apply_filters = st.button("Применить фильтры", type="primary", key="apply_auditory_filters")


# Основные данные по аудиториям
try:
    aud_df = get_active_auditories_with_latest_status()
except Exception:
    st.error("Не удалось получить данные по аудиториям из базы данных. Проверьте подключение к БД.")
    st.stop()

if aud_df.empty:
    st.info("Нет активных аудиторий в базе данных.")
    st.stop()

# Применение фильтров
filtered_df = aud_df.copy()

if search_text:
    mask = (
        filtered_df["name"]
        .astype(str)
        .apply(get_russian_name)
        .str.contains(search_text, case=False, na=False)
    )
    filtered_df = filtered_df[mask]

if selected_building != "Все корпуса":
    filtered_df = filtered_df[filtered_df["building"].astype(str) == str(selected_building)]

if selected_status_code in {"green", "yellow", "red"}:
    filtered_df = filtered_df[filtered_df["current_status"].astype(str).str.lower() == selected_status_code]

if filtered_df.empty:
    st.warning("Нет аудиторий, соответствующих фильтрам.")
    st.stop()


col_left, col_right = st.columns([0.4, 0.6])

with col_left:
    st.subheader("Список аудиторий")

    display_df = filtered_df.copy()
    display_df["Статус"] = display_df["current_status"].apply(_status_to_label)
    display_df["Последнее обновление"] = display_df["last_update"].apply(_format_datetime_short)
    display_df["Корпус"] = display_df["building"].astype(str).apply(get_russian_name)
    display_df["Аудитория"] = display_df["name"].astype(str).apply(get_russian_name)

    display_columns = [
        "Корпус",
        "Аудитория",
        "Статус",
        "Последнее обновление",
        "last_reporter",
    ]
    rename_map: Dict[str, str] = {
        "last_reporter": "Кто отметил",
    }
    table_df = display_df[display_columns].rename(columns=rename_map)

    styled_table = table_df.style.apply(_highlight_problem_auditories, axis=1)
    st.dataframe(styled_table, height=450)

    # Выбор аудитории для подробного просмотра
    options = []
    for _, row in filtered_df.iterrows():
        label = (
            f"{get_russian_name(str(row.get('building', '') or ''))}"
            f" — {get_russian_name(str(row.get('name', '') or ''))}"
        )
        options.append((row["id"], label))

    if options:
        option_labels = ["Не выбрано"] + [opt[1] for opt in options]
        selected_label = st.selectbox("Выберите аудиторию для просмотра истории", options=option_labels)
        selected_auditory_id: Optional[int] = None
        if selected_label != "Не выбрано":
            id_by_label: Dict[str, Any] = {opt[1]: opt[0] for opt in options}
            selected_auditory_id = id_by_label.get(selected_label)
    else:
        selected_auditory_id = None


with col_right:
    if not "selected_auditory_id" in locals() or selected_auditory_id is None:
        st.info("Выберите аудиторию из списка слева.")
    else:
        selected_row = filtered_df[filtered_df["id"] == selected_auditory_id]
        if selected_row.empty:
            st.warning("Не удалось найти данные по выбранной аудитории.")
        else:
            row = selected_row.iloc[0]

            # Блок 1: карточка аудитории
            status_display = _status_to_label(row.get("current_status"))
            last_update_display = _format_datetime_short(row.get("last_update"))

            render_auditory_card(
                name=get_russian_name(str(row.get("name") or "")),
                building=get_russian_name(str(row.get("building") or "")),
                floor=row.get("floor"),
                equipment=row.get("equipment"),
                status_display=status_display,
                last_update_display=last_update_display,
                reporter=row.get("last_reporter"),
                comment=row.get("comment"),
            )

            # Блок 2 и 3: история статусов
            try:
                history_df = get_auditory_status_history(int(selected_auditory_id))
            except Exception:
                st.error("Не удалось загрузить историю статусов для выбранной аудитории.")
                history_df = pd.DataFrame()

            st.markdown("---")
            st.subheader("История статусов")

            if history_df.empty:
                st.info("Нет данных истории статусов для выбранной аудитории за последние 90 дней.")
            else:
                # Блок 2: график истории
                render_status_history_chart(history_df)

                # Блок 3: таблица истории
                history_table = history_df.copy()
                history_table["Дата и время"] = history_table["created_at"].apply(_format_datetime_short)
                history_table["Статус"] = history_table["status"].apply(_status_to_label)
                if "event_title" in history_table.columns:
                    history_table["Мероприятие"] = history_table["event_title"].apply(
                        lambda x: to_cyrillic(x) if x else ""
                    )
                    cols = ["Дата и время", "Статус", "Мероприятие", "comment", "engineer"]
                else:
                    cols = ["Дата и время", "Статус", "comment", "engineer"]

                history_table = history_table[cols].rename(
                    columns={
                        "comment": "Комментарий",
                        "engineer": "Инженер",
                    }
                )
                st.dataframe(history_table, height=300)

            # Блок 4: статистика по аудитории
            st.markdown("---")
            st.subheader("Статистика по аудитории (последние 90 дней)")

            try:
                stats = get_auditory_stats(int(selected_auditory_id))
            except Exception:
                st.error("Не удалось загрузить статистику по выбранной аудитории.")
                stats = None

            if not stats or stats.get("total_marks", 0) == 0:
                st.info("За последние 90 дней по этой аудитории нет отметок.")
            else:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Всего отметок", stats.get("total_marks", 0))
                with col2:
                    st.metric("🔴 Красных", stats.get("red_count", 0))
                with col3:
                    st.metric("🟡 Жёлтых", stats.get("yellow_count", 0))
                with col4:
                    st.metric("🟢 Зелёных", stats.get("green_count", 0))


"""Главная точка входа Streamlit-дашборда OTSKVM Bot.

Запуск из корня проекта:
  streamlit run streamlit_dashboard/app.py --server.port 8502

Дашборд полностью независим от бота: не импортирует handlers, services, core.
Подключение к БД — через переменные окружения (.env).
"""

import sys
from pathlib import Path

# Чтобы импорты database/utils/components работали при любом способе запуска
_dash_root = Path(__file__).resolve().parent
if str(_dash_root) not in sys.path:
    sys.path.insert(0, str(_dash_root))

import streamlit as st


st.set_page_config(
    page_title="OTSKVM Bot — Дашборд",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("OTSKVM Bot — Дашборд активности инженеров")
st.markdown(
    "Выберите страницу в боковой панели: **Активность**, **По инженерам** или **Экспорт**."
)
st.info(
    "Фильтры и период задаются на странице «Активность». "
    "Данные кэшируются на 5 минут."
)

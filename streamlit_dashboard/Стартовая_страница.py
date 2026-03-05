"""Стартовая страница Streamlit-дашборда OTSKVM Bot.

Запуск из корня проекта:
  streamlit run streamlit_dashboard/Стартовая_страница.py --server.port 8503

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

st.title("Стартовая страница дашборда OTSKVM Bot")
st.markdown(
    "Используйте левое меню для перехода на страницы: "
    "**Активность**, **Инженеры** и **Экспорт**."
)
st.info(
    "Фильтры и период задаются на странице «Активность». "
    "Данные кэшируются на 5 минут."
)


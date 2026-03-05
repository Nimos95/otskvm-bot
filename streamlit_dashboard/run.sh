#!/usr/bin/env bash
cd "$(dirname "$0")/.."
streamlit run "streamlit_dashboard/Стартовая_страница.py" --server.port 8503

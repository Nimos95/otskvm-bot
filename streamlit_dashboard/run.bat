@echo off
cd /d "%~dp0\.."
streamlit run "streamlit_dashboard/Стартовая_страница.py" --server.port 8503

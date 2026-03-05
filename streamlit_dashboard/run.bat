@echo off
cd /d "%~dp0\.."
streamlit run streamlit_dashboard/app.py --server.port 8503

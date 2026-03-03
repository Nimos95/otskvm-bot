#!/usr/bin/env bash
cd "$(dirname "$0")/.."
streamlit run streamlit_dashboard/app.py --server.port 8503

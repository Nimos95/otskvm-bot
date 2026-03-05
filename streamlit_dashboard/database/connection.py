from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


_BASE_DIR = Path(__file__).resolve().parents[2]
_ENV_PATH = _BASE_DIR / ".env"

# Загружаем переменные окружения из .env в корне проекта,
# не импортируя конфиг и код бота.
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


def get_connection() -> Any:
    """Создаёт новое подключение к PostgreSQL на основе DATABASE_URL.

    Подключение создаётся на каждый вызов и должно закрываться вызывающим кодом
    (используйте контекстный менеджер `with get_connection() as conn:`).
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "Переменная окружения DATABASE_URL не задана. "
            "Проверьте файл .env в корне проекта."
        )

    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)


"""Конфигурация бота. Загружает переменные окружения из .env."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Загружаем .env из корня проекта
load_dotenv(Path(__file__).parent / ".env")


class Config:
    """Конфигурация приложения из переменных окружения."""

    BOT_TOKEN: str
    DATABASE_URL: str
    GROUP_CHAT_ID: Optional[int]
    TOPIC_ID: Optional[int]
    LOG_LEVEL: str

    def __init__(self) -> None:
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
        self.DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
        
        _group_id = os.getenv("GROUP_CHAT_ID", "").strip()
        self.GROUP_CHAT_ID = int(_group_id) if _group_id else None
        
        _topic_id = os.getenv("TOPIC_ID", "").strip()
        self.TOPIC_ID = int(_topic_id) if _topic_id else None
        
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip()

        self._validate()

    def _validate(self) -> None:
        """Проверяет наличие обязательных переменных."""
        missing: list[str] = []
        if not self.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")

        if missing:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}. "
                "Проверьте файл .env"
            )


config = Config()
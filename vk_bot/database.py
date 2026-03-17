"""
Подключение к базе данных для VK бота
"""

import os
import sys
from pathlib import Path
import asyncpg
from dotenv import load_dotenv
from loguru import logger

# Добавляем путь к корневой папке проекта
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

class Database:
    _pool = None

    @classmethod
    async def connect(cls):
        """Создаёт пул соединений с БД"""
        if cls._pool is None:
            try:
                cls._pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("✅ Подключение к БД установлено")
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к БД: {e}")
                raise
        return cls._pool

    @classmethod
    async def disconnect(cls):
        """Закрывает пул соединений"""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("🔌 Подключение к БД закрыто")

    @classmethod
    def get_pool(cls):
        """Возвращает пул соединений"""
        if cls._pool is None:
            raise Exception("База данных не подключена. Сначала вызовите Database.connect()")
        return cls._pool
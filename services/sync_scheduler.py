"""Планировщик синхронизации календаря."""

import asyncio
import logging

from services.google_calendar import calendar_client, sync_calendar

logger = logging.getLogger(__name__)


async def sync_loop():
    """Бесконечный цикл синхронизации (запускать в отдельной задаче)."""
    while True:
        try:
            logger.info("Запуск плановой синхронизации календаря")
            # Используем функцию sync_calendar, а не методы calendar_client напрямую
            await sync_calendar(days=30)
            logger.info("Синхронизация завершена")
        except Exception as e:
            logger.error(f"Ошибка при синхронизации: {e}")
        
        # Ждём 6 часов до следующей синхронизации
        await asyncio.sleep(6 * 60 * 60)
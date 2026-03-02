"""Фоновая синхронизация с Google Calendar."""

import asyncio
import logging
from datetime import datetime, timedelta

from database import get_db_pool
from services.google_calendar import calendar_client, sync_calendar

logger = logging.getLogger(__name__)


async def force_sync(days: int = 30) -> int:
    """
    Принудительная синхронизация с Google Calendar.
    
    Returns:
        int: Количество обработанных событий
    """
    logger.info("Запуск принудительной синхронизации")
    
    try:
        # Получаем события из календаря
        events = await calendar_client.fetch_events(days=days)
        
        if not events:
            logger.info("Нет новых событий для синхронизации")
            return 0
        
        # Сохраняем в БД
        await calendar_client.save_events_to_db(events)
        
        logger.info(f"Принудительная синхронизация завершена. Обработано: {len(events)} событий")
        return len(events)
        
    except Exception as e:
        logger.error(f"Ошибка при принудительной синхронизации: {e}", exc_info=True)
        raise


async def sync_loop():
    """
    Бесконечный цикл фоновой синхронизации (каждые 6 часов).
    """
    while True:
        try:
            logger.info("Запуск плановой синхронизации")
            await sync_calendar(days=30)
            logger.info("Плановая синхронизация завершена")
        except Exception as e:
            logger.error(f"Ошибка в цикле синхронизации: {e}", exc_info=True)
        
        # Ждём 6 часов
        await asyncio.sleep(6 * 60 * 60)
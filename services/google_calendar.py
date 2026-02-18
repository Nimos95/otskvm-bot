"""Модуль для работы с Google Calendar API."""

import datetime
import logging
import os
from typing import List, Dict, Any, Optional

import cyrtranslit
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import config
from database import get_db_pool

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class GoogleCalendarClient:
    """Клиент для работы с Google Calendar API."""
    
    def __init__(self):
        self.service = None
        self.calendar_id = config.GOOGLE_CALENDAR_ID if hasattr(config, 'GOOGLE_CALENDAR_ID') else "primary"
        self._authenticate()
        logger.info(f"Используется календарь с ID: {self.calendar_id}")
    
    def _authenticate(self):
        """Аутентификация через OAuth 2.0."""
        creds = None
        
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info("Токен обновлён")
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0, open_browser=False)
                logger.info("Новая авторизация выполнена")
            
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        
        self.service = build("calendar", "v3", credentials=creds)
        logger.info("Google Calendar клиент инициализирован")
    
    async def fetch_events(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Получает события из календаря на указанное количество дней вперёд.
        
        Args:
            days: количество дней от сегодня
            
        Returns:
            Список событий
        """
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            time_min = now.isoformat()
            time_max = (now + datetime.timedelta(days=days)).isoformat()
            
            logger.info(f"Запрашиваем события с {time_min} по {time_max} из календаря {self.calendar_id}")
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            events = events_result.get("items", [])
            logger.info(f"Получено {len(events)} событий из Google Calendar")
            return events
            
        except HttpError as error:
            logger.error(f"Ошибка при получении событий: {error}")
            return []
    
    def _extract_auditory_from_event(self, event: Dict) -> Optional[str]:
        """
        Извлекает название аудитории из события.
        Сначала ищет в location, потом в description, потом в summary.
        """
        location = event.get("location", "")
        if location and location.strip():
            return location.strip()
        
        description = event.get("description", "")
        if description and description.strip():
            return description.strip()
        
        return None
    
    async def save_events_to_db(self, events: List[Dict[str, Any]]):
        """Сохраняет события в базу данных."""
        pool = get_db_pool()
        saved_count = 0
        
        for event in events:
            try:
                # Получаем строки с датами из события
                start_str = event["start"].get("dateTime", event["start"].get("date"))
                end_str = event["end"].get("dateTime", event["end"].get("date"))
                
                # Конвертируем строки в datetime объекты и удаляем информацию о часовом поясе
                if 'T' in start_str:
                    # Это событие с конкретным временем
                    start_str = start_str.replace('Z', '+00:00')
                    end_str = end_str.replace('Z', '+00:00')
                    start = datetime.datetime.fromisoformat(start_str)
                    end = datetime.datetime.fromisoformat(end_str)
                    # Удаляем информацию о часовом поясе (делаем naive)
                    if start.tzinfo is not None:
                        start = start.replace(tzinfo=None)
                    if end.tzinfo is not None:
                        end = end.replace(tzinfo=None)
                else:
                    # Это событие на целый день
                    start = datetime.datetime.fromisoformat(start_str)
                    end = datetime.datetime.fromisoformat(end_str)
                
                # Получаем русское название из календаря
                ru_title = event.get("summary", "Без названия")
                
                # Транслитерируем в английское для хранения в БД
                en_title = cyrtranslit.to_latin(ru_title)
                
                # Пытаемся определить аудиторию
                auditory_name = self._extract_auditory_from_event(event)
                auditory_id = None
                
                if auditory_name:
                    # Транслитерируем название аудитории для поиска в БД
                    en_auditory = cyrtranslit.to_latin(auditory_name)
                    row = await pool.fetchrow(
                        "SELECT id FROM auditories WHERE name = $1",
                        en_auditory
                    )
                    if row:
                        auditory_id = row["id"]
                        logger.debug(f"Найдена аудитория {auditory_name} (ID: {auditory_id})")
                
                # Вставляем или обновляем событие
                await pool.execute(
                    """
                    INSERT INTO calendar_events 
                    (google_event_id, auditory_id, title, description, 
                     start_time, end_time, organizer, status, last_sync)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ON CONFLICT (google_event_id) DO UPDATE SET
                        auditory_id = EXCLUDED.auditory_id,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        organizer = EXCLUDED.organizer,
                        status = EXCLUDED.status,
                        last_sync = NOW()
                    """,
                    event["id"],
                    auditory_id,
                    en_title,
                    event.get("description", ""),
                    start,
                    end,
                    event.get("organizer", {}).get("email", ""),
                    event.get("status", "confirmed")
                )
                
                saved_count += 1
                logger.debug(f"Событие {event['id']} сохранено (было: '{ru_title}' -> стало: '{en_title}')")
                
            except Exception as e:
                logger.error(f"Ошибка при сохранении события {event.get('id')}: {e}")
        
        logger.info(f"Сохранено {saved_count} событий в базу данных")


# Создаём глобальный экземпляр клиента
calendar_client = GoogleCalendarClient()


async def sync_calendar(days: int = 30):
    """Синхронизирует календарь с базой данных."""
    logger.info("Начинаем синхронизацию календаря")
    try:
        events = await calendar_client.fetch_events(days)
        await calendar_client.save_events_to_db(events)
        logger.info(f"Синхронизация завершена. Обработано {len(events)} событий")
    except Exception as e:
        logger.error(f"Ошибка при синхронизации календаря: {e}")
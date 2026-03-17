"""
Вспомогательные функции для VK бота (переименовано во избежание конфликтов)
"""

import sys
import os
from pathlib import Path

# Абсолютный путь к корню проекта
ROOT_DIR = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

# Импортируем общие модули из src (обратите внимание на полный путь)
try:
    from utils.translit import to_cyrillic
    from utils.auditory_names import get_russian_name
    from core.constants import (
        STATUS_GREEN, STATUS_YELLOW, STATUS_RED,
        ASSIGNMENT_STATUS_ACCEPTED, ASSIGNMENT_STATUS_ASSIGNED,
        ASSIGNMENT_STATUS_DONE, ASSIGNMENT_STATUS_CANCELLED
    )
    print(f"✅ Модули src успешно импортированы")
except ImportError as e:
    print(f"❌ Ошибка импорта модулей src: {e}")
    print(f"Python path: {sys.path}")
    raise

# Реэкспортируем для удобства
__all__ = [
    'to_cyrillic',
    'get_russian_name',
    'STATUS_GREEN',
    'STATUS_YELLOW',
    'STATUS_RED',
    'ASSIGNMENT_STATUS_ACCEPTED',
    'ASSIGNMENT_STATUS_ASSIGNED',
    'ASSIGNMENT_STATUS_DONE',
    'ASSIGNMENT_STATUS_CANCELLED'
]
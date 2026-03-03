"""Утилиты для работы с транслитерацией.

Обёртки над cyrtranslit, чтобы в одном месте контролировать
поведение и защититься от неожиданных ошибок.
"""

from __future__ import annotations

import logging
from typing import Optional

import cyrtranslit

logger = logging.getLogger(__name__)


def to_cyrillic(text: Optional[str]) -> str:
    """Безопасно конвертирует строку в кириллицу.

    Если text == None или произошла ошибка транслитерации,
    возвращает исходное значение или пустую строку.
    """
    if text is None:
        return ""
    try:
        return cyrtranslit.to_cyrillic(text)
    except Exception as exc:  # pragma: no cover - крайне редкий сценарий
        logger.error("Ошибка транслитерации в кириллицу: %s", exc)
        return text


def to_latin(text: Optional[str]) -> str:
    """Безопасно конвертирует строку в латиницу.

    Если text == None или произошла ошибка транслитерации,
    возвращает исходное значение или пустую строку.
    """
    if text is None:
        return ""
    try:
        return cyrtranslit.to_latin(text)
    except Exception as exc:  # pragma: no cover - крайне редкий сценарий
        logger.error("Ошибка транслитерации в латиницу: %s", exc)
        return text


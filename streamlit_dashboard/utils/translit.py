import logging

import cyrtranslit

logger = logging.getLogger(__name__)


def to_cyrillic(text: str) -> str:
    """Преобразует текст из латиницы в кириллицу."""
    if not text or not isinstance(text, str):
        return ""
    try:
        return cyrtranslit.to_cyrillic(text)
    except Exception as e:
        logger.error(f"Ошибка транслитерации в кириллицу: {e}")
        return text


def to_latin(text: str) -> str:
    """Преобразует текст из кириллицы в латиницу."""
    if not text or not isinstance(text, str):
        return ""
    try:
        return cyrtranslit.to_latin(text)
    except Exception as e:
        logger.error(f"Ошибка транслитерации в латиницу: {e}")
        return text


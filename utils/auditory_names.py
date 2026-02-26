"""Словарь для отображения английских названий аудиторий в русские."""

AUDITORY_NAMES = {
    # Английское название (из БД) : Русское название (для Telegram)
    '118': '118',
    '130': '130',
    'Semenov': 'Семенов',
    'Lekcionnyj zal 1': 'Лекционный зал 1',
    'Lekcionnyj zal 2': 'Лекционный зал 2',
    'Kapica': 'Капица',
    'G3.56': 'Г3.56',
    'MKZ': 'МКЗ',
    'G3.14': 'Г3.14',
    '335': '335',
    'Kabinet Rektora': 'Кабинет Ректора',
    'SKC': 'СКЦ',
    # названия корпусов
    'GUK': 'ГУК',
    'NIK': 'НИК',
    '1UK': '1УК',
}

def get_russian_name(english_name: str) -> str:
    """Возвращает русское название аудитории или корпуса."""
    return AUDITORY_NAMES.get(english_name, english_name)

def get_english_name(russian_name: str) -> str:
    """Возвращает английское название аудитории или корпуса (для поиска в БД)."""
    # Создаём обратный словарь
    reverse_map = {v: k for k, v in AUDITORY_NAMES.items()}
    return reverse_map.get(russian_name, russian_name)
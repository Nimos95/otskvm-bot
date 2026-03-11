"""Словарь для отображения английских названий аудиторий в русские."""

AUDITORY_NAMES = {
    # Аудитории с особыми названиями
    "Semenov": "Семенов",
    "Kapica": "Капица",
    "G3.56": "Г3.56",
    "MKZ": "МКЗ",
    "G3.14": "Г3.14",
    "Kabinet Rektora": "Кабинет Ректора",
    "SKC": "СКЦ",
    "A2.28": "А2.28",
    "Holl": "Холл",
    # Названия корпусов
    "GUK": "ГУК",
    "NIK": "НИК",
    "1UK": "1УК",
    # Специальные названия залов
    "Lekcionnый zal 1": "Лекционный зал 1",
    "Lekcionnый zal 2": "Лекционный зал 2",
    "Belый zal": "Белый зал",
}


def get_russian_name(english_name: str) -> str:
    """Возвращает русское название аудитории или корпуса."""
    if not english_name:
        return english_name
    return AUDITORY_NAMES.get(english_name, english_name)


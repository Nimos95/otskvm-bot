"""Модуль нормализации названий аудиторий.

Как добавлять новые варианты: найди в логах warning,
определи правильную аудиторию, добавь запись в ALIASES.
"""

from __future__ import annotations

from typing import Dict


def _normalize_key(name: str) -> str:
    """
    Приводит строку к нормализованному ключу для словаря синонимов.

    Нормализация:
    - обрезка пробелов по краям;
    - приведение к нижнему регистру;
    - замена «ё» на «е»;
    - удаление точек;
    - схлопывание последовательностей пробелов в один.
    """
    cleaned = name.strip().lower()
    cleaned = cleaned.replace("ё", "е")
    cleaned = cleaned.replace(".", "")
    # Схлопываем повторяющиеся пробелы
    parts = cleaned.split()
    return " ".join(parts)


class AuditoryNormalizer:
    """
    Нормализатор названий аудиторий на основе словаря синонимов.

    Идея:
    - из Google Calendar приходят «сырые» русские названия аудиторий;
    - нормализатор приводит их к каноническому виду, совпадающему
      с названиями в справочнике аудиторий (например, «Семенов»,
      «Лекционный зал 1», «118» и т.п.);
    - пополнение словаря выполняется по логам warning.
    """

    # Словарь синонимов: вариант написания -> правильное название (на русском)
    # Ключи заранее нормализованы через `_normalize_key`.
    ALIASES: Dict[str, str] = {
        # Семенов
        _normalize_key("семенов"): "Семенов",
        _normalize_key("семёнов"): "Семенов",
        _normalize_key("зал семенов"): "Семенов",
        _normalize_key("зал семёнова"): "Семенов",

        # Капица
        _normalize_key("капица"): "Капица",
        _normalize_key("зал капица"): "Капица",
        _normalize_key("зал капицы"): "Капица",

        # Белый зал
        _normalize_key("белый зал"): "Белый зал",
        _normalize_key("белый"): "Белый зал",

        # Лекционный зал 1
        _normalize_key("лекционный 1"): "Лекционный зал 1",
        _normalize_key("лекционный зал 1"): "Лекционный зал 1",
        _normalize_key("лекц 1"): "Лекционный зал 1",
        _normalize_key("лекц. 1"): "Лекционный зал 1",

        # Лекционный зал 2
        _normalize_key("лекционный 2"): "Лекционный зал 2",
        _normalize_key("лекционный зал 2"): "Лекционный зал 2",
        _normalize_key("лекц 2"): "Лекционный зал 2",
        _normalize_key("лекц. 2"): "Лекционный зал 2",

        # МКЗ
        _normalize_key("мкз"): "МКЗ",
        _normalize_key("м к з"): "МКЗ",
        _normalize_key("Мкз"): "МКЗ",

        # СКЦ
        _normalize_key("скц"): "СКЦ",
        _normalize_key("с к ц"): "СКЦ",
        _normalize_key("Скц"): "СКЦ",

        # Аудитория 118 (разные варианты с корпусами/сокращениями)
        _normalize_key("118"): "118",
        _normalize_key("гук 118"): "118",
        _normalize_key("118 гз"): "118",
        _normalize_key("118 гук"): "118",
        _normalize_key("ауд 118"): "118",
        _normalize_key("ауд. 118"): "118",
        _normalize_key("зал 118"): "118",

        # Г3.56
        _normalize_key("г3.56"): "Г3.56",
        _normalize_key("г356"): "Г3.56",
        _normalize_key("г 3.56"): "Г3.56",
        _normalize_key("г 3 56"): "Г3.56",
        _normalize_key("г3 56"): "Г3.56",

        # Г3.14
        _normalize_key("г3.14"): "Г3.14",
        _normalize_key("г314"): "Г3.14",
        _normalize_key("г 3.14"): "Г3.14",
        _normalize_key("г 3 14"): "Г3.14",
        _normalize_key("г3 14"): "Г3.14",

        # Аудитория 130 (разные варианты с корпусами/сокращениями)
        _normalize_key("130"): "130",
        _normalize_key("гук 130"): "130",
        _normalize_key("130 гз"): "130",
        _normalize_key("130 гук"): "130",
        _normalize_key("ауд 130"): "130",
        _normalize_key("ауд. 130"): "130",
        _normalize_key("зал 130"): "130",

        # Кабинет Ректора
        _normalize_key("кабинет ректора"): "Кабинет Ректора",
        _normalize_key("кабинет Ректора"): "Кабинет Ректора",
        _normalize_key("ректор"): "Кабинет Ректора",
        _normalize_key("Ректор"): "Кабинет Ректора",

        # Холл
        _normalize_key("холл"): "Холл",
        _normalize_key("хол"): "Холл",
        _normalize_key("Хол"): "Холл",
    }

    @classmethod
    def normalize(cls, raw_name: str) -> str:
        """
        Нормализует «сырое» название аудитории.

        Аргументы:
            raw_name: исходная строка из Google Calendar.

        Возвращает:
            Каноническое название аудитории (на русском),
            либо исходное значение, если синоним не найден.
        """
        if not raw_name:
            return raw_name

        key = _normalize_key(raw_name)
        return cls.ALIASES.get(key, raw_name.strip())

    @classmethod
    def add_alias(cls, variant: str, correct_name: str) -> None:
        """
        Добавляет новый вариант написания в словарь синонимов.

        Аргументы:
            variant: новый вариант написания (как приходит из календаря);
            correct_name: каноническое название аудитории.
        """
        norm_key = _normalize_key(variant)
        cls.ALIASES[norm_key] = correct_name

    @classmethod
    def get_all_aliases(cls) -> Dict[str, str]:
        """
        Возвращает копию словаря синонимов.

        Используется для отладки и анализа покрытия вариантов названий.
        """
        return dict(cls.ALIASES)


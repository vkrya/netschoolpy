"""Справочник регионов и их URL-адресов «Сетевого города».

Использование::

    from netschoolpy.regions import REGIONS, get_url, list_regions

    url = get_url("Челябинская область")       # "https://sgo.edu-74.ru"
    url = get_url("челябинская")                # нечёткий поиск — тоже найдёт
    regions = list_regions()                     # отсортированный список имён

Некоторые регионы имеют несколько независимых серверов (Свердловская,
Иркутская, Ростовская область).  Для них нужно указывать URL явно —
в справочнике их нет.
"""

from __future__ import annotations

__all__ = ["REGIONS", "get_url", "list_regions"]


# region → base URL  (отсортировано по алфавиту, 26 регионов)
REGIONS: dict[str, str] = {
    "Алтайский край": "https://netschool.edu22.info",
    "Амурская область": "https://region.obramur.ru",
    "Забайкальский край": "https://region.zabedu.ru",
    "Калужская область": "https://edu.admoblkaluga.ru:444",
    "Камчатский край": "https://school.sgo41.ru",
    "Костромская область": "https://netschool.eduportal44.ru",
    "Краснодарский край": "https://sgo.rso23.ru",
    "Ленинградская область": "https://e-school.obr.lenreg.ru",
    "Приморский край": "https://sgo.prim-edu.ru",
    "Республика Алтай": "https://sgo.altaiobr04.ru",
    "Республика Бурятия": "https://deti.obr03.ru",
    "Республика Ингушетия": "https://sgo.edu-ri.ru",
    "Республика Коми": "https://giseo.rkomi.ru",
    "Республика Марий Эл": "https://sgo.mari-el.gov.ru",
    "Республика Мордовия": "https://sgo.e-mordovia.ru",
    "Республика Саха (Якутия)": "https://sgo.e-yakutia.ru",
    "Рязанская область": "https://e-school.ryazan.gov.ru",
    "Самарская область": "https://asurso.ru",
    "Сахалинская область": "https://netcity.admsakhalin.ru:11111",
    "Тверская область": "https://sgo.tvobr.ru",
    "Томская область": "https://sgo.tomedu.ru",
    "Ульяновская область": "https://sgo.cit73.ru",
    "Челябинская область": "https://sgo.edu-74.ru",
    "Черноголовка": "https://journal.nschg.ru",
    "Чувашская Республика": "http://net-school.cap.ru",
    "Ямало-Ненецкий автономный округ": "https://sgo.yanao.ru",
}


def list_regions() -> list[str]:
    """Возвращает отсортированный список названий регионов."""
    return sorted(REGIONS)


def get_url(query: str) -> str | None:
    """Ищет URL по точному или частичному названию региона.

    Поиск регистронезависимый.  Если *query* является подстрокой
    ровно одного ключа — он будет возвращён.  При неоднозначности
    возвращается ``None``.

    >>> get_url("Челябинская область")
    'https://sgo.edu-74.ru'
    >>> get_url("челябинская")
    'https://sgo.edu-74.ru'
    >>> get_url("Респ")          # неоднозначно → None
    """
    q = query.lower()

    # 1. Точное совпадение
    for name, url in REGIONS.items():
        if name.lower() == q:
            return url

    # 2. Подстрока
    matches = [
        (name, url) for name, url in REGIONS.items() if q in name.lower()
    ]
    if len(matches) == 1:
        return matches[0][1]

    return None

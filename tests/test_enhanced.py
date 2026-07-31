"""Тесты для новых функций библиотеки netschoolpy (Pydantic v2, iCal, TTL-кэш, CLI, прокси, события)."""

from datetime import date, datetime
import pytest
from netschoolpy.cache import TTLCache
from netschoolpy.client import NetSchool
from netschoolpy.events import NewAnnouncementEvent, NewMarkEvent
from netschoolpy.models import (
    Assignment,
    Day,
    Diary,
    Lesson,
    LoginMethods,
    Student,
)
from netschoolpy.regions import get_url, list_regions


def test_pydantic_v2_models():
    """Тестирование Pydantic v2 моделей данных."""
    student = Student(id=101, name="Иван Иванов", group_name="10А")
    assert student.id == 101
    assert student.name == "Иван Иванов"
    assert "Иван Иванов" in str(student)

    json_str = student.model_dump_json()
    assert '"id":101' in json_str or '"id": 101' in json_str

    lm = LoginMethods(esia=True, esia_main=True)
    assert "Госуслуги" in lm.summary


def test_ical_export():
    """Тестирование экспорта расписания в формат iCalendar (.ics)."""
    now = datetime(2026, 9, 1, 9, 0, 0)
    end = datetime(2026, 9, 1, 9, 45, 0)
    lesson = Lesson(
        number=1,
        subject="Математика",
        start=now,
        end=end,
        room="301",
        assignments=[
            Assignment(id=1, title="Решить №10", mark=5, type_name="Домашнее задание")
        ],
    )

    day = Day(date=date(2026, 9, 1), lessons=[lesson])
    diary = Diary(start=date(2026, 9, 1), end=date(2026, 9, 7), days=[day])

    ical_str = diary.to_ical()
    assert "BEGIN:VCALENDAR" in ical_str
    assert "END:VCALENDAR" in ical_str
    assert "SUMMARY:1. Математика" in ical_str
    assert "LOCATION:301" in ical_str
    assert "• Решить №10 [Домашнее задание] — Оценка: 5" in ical_str


def test_ttl_cache():
    """Тестирование TTL-кэша."""
    cache = TTLCache(default_ttl=0.1)
    cache.set("key1", ["Предмет1", "Предмет2"])

    assert cache.get("key1") == ["Предмет1", "Предмет2"]
    cache.clear()
    assert cache.get("key1") is None


def test_netschool_init_options():
    """Тестирование новых опций клиентов (прокси, auto_relogin, cache_ttl)."""
    client = NetSchool(
        "https://sgo.edu-74.ru",
        proxy="http://127.0.0.1:8080",
        auto_relogin=True,
        cache_ttl=1800.0,
    )
    assert client._proxy == "http://127.0.0.1:8080"
    assert client._auto_relogin is True
    assert client._cache.default_ttl == 1800.0


def test_event_models():
    """Тестирование моделей событий SignalR."""
    mark_event = NewMarkEvent(subject="Физика", mark="5", assignment_name="Контрольная")
    assert mark_event.event_type == "NEW_MARK"
    assert mark_event.subject == "Физика"

    ann_event = NewAnnouncementEvent(title="Собрание", description="В 18:00")
    assert ann_event.event_type == "NEW_ANNOUNCEMENT"
    assert ann_event.title == "Собрание"


def test_regions_registry():
    """Тестирование справочника регионов."""
    assert len(list_regions()) >= 26
    assert get_url("Челябинская область") == "https://sgo.edu-74.ru"
    assert get_url("челябинская") == "https://sgo.edu-74.ru"

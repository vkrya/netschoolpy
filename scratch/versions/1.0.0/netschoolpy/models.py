"""Модели данных netschoolpy — plain dataclasses с ручным парсингом JSON."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _parse_date(value: Any) -> datetime.date:
    """Парсит дату из ISO-строки (``2024-01-15T00:00:00``)."""
    if isinstance(value, datetime.date):
        return value
    s = str(value).split("T")[0]
    return datetime.date.fromisoformat(s)


def _parse_datetime(value: Any) -> datetime.datetime:
    """Парсит datetime из ISO-строки."""
    if isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(str(value))


def _parse_time(value: Any) -> datetime.time:
    """Парсит время из строки ``HH:MM`` или ``HH:MM:SS``."""
    if isinstance(value, datetime.time):
        return value
    parts = str(value).split(":")
    return datetime.time(int(parts[0]), int(parts[1]),
                         int(parts[2]) if len(parts) > 2 else 0)


# ──────────────────────────── Вложения ────────────────────────────

@dataclass(frozen=True)
class Attachment:
    id: int
    name: str
    description: str = ""

    @classmethod
    def from_raw(cls, data: dict) -> Attachment:
        return cls(
            id=data["id"],
            name=data.get("originalFileName", ""),
            description=data.get("description") or "",
        )


# ───────────────────────────── Автор ──────────────────────────────

@dataclass(frozen=True)
class Author:
    id: int
    full_name: str
    nickname: str

    @classmethod
    def from_raw(cls, data: dict) -> Author:
        return cls(
            id=data["id"],
            full_name=data.get("fio", ""),
            nickname=data.get("nickName", ""),
        )


# ─────────────────────────── Объявления ───────────────────────────

@dataclass(frozen=True)
class Announcement:
    name: str
    author: Author
    content: str
    post_date: datetime.datetime
    attachments: List[Attachment] = field(default_factory=list)

    @classmethod
    def from_raw(cls, data: dict) -> Announcement:
        return cls(
            name=data["name"],
            author=Author.from_raw(data["author"]),
            content=data.get("description", ""),
            post_date=_parse_datetime(data["postDate"]),
            attachments=[
                Attachment.from_raw(a) for a in data.get("attachments", [])
            ],
        )


# ─────────────────────────── Задания ─────────────────────────────

@dataclass(frozen=True)
class Assignment:
    id: int
    comment: str
    kind: str  # тип задания (из справочника)
    content: str
    mark: Optional[int]
    is_duty: bool
    deadline: datetime.date

    @classmethod
    def from_raw(cls, data: dict, type_mapping: Dict[int, str] | None = None) -> Assignment:
        """Собирает ``Assignment`` из «сырого» JSON SGO.

        SGO вкладывает оценку в подобъект ``mark``:
            ``{"mark": {"mark": 5, "dutyMark": false}, "markComment": {"name": "..."}, ...}``
        Здесь это «разворачивается» в плоские поля.
        """
        raw_mark = data.get("mark")
        if isinstance(raw_mark, dict):
            mark_value: Optional[int] = raw_mark.get("mark")
            duty: bool = raw_mark.get("dutyMark", False)
        else:
            mark_value = None
            duty = False

        mark_comment = data.get("markComment")
        comment = mark_comment["name"] if isinstance(mark_comment, dict) and "name" in mark_comment else ""

        kind_id = data.get("typeId", 0)
        kind = (type_mapping or {}).get(kind_id, str(kind_id))

        return cls(
            id=data["id"],
            comment=comment,
            kind=kind,
            content=data.get("assignmentName", ""),
            mark=mark_value,
            is_duty=duty,
            deadline=_parse_date(data["dueDate"]),
        )


# ──────────────────────────── Уроки ──────────────────────────────

@dataclass(frozen=True)
class Lesson:
    day: datetime.date
    start: datetime.time
    end: datetime.time
    room: str
    number: int
    subject: str
    assignments: List[Assignment] = field(default_factory=list)

    @classmethod
    def from_raw(cls, data: dict, type_mapping: Dict[int, str] | None = None) -> Lesson:
        return cls(
            day=_parse_date(data["day"]),
            start=_parse_time(data["startTime"]),
            end=_parse_time(data["endTime"]),
            room=data.get("room") or "",
            number=data["number"],
            subject=data.get("subjectName", ""),
            assignments=[
                Assignment.from_raw(a, type_mapping)
                for a in data.get("assignments", [])
            ],
        )


# ──────────────────────────── День ───────────────────────────────

@dataclass(frozen=True)
class Day:
    day: datetime.date
    lessons: List[Lesson]

    @classmethod
    def from_raw(cls, data: dict, type_mapping: Dict[int, str] | None = None) -> Day:
        return cls(
            day=_parse_date(data["date"]),
            lessons=[Lesson.from_raw(l, type_mapping) for l in data.get("lessons", [])],
        )


# ─────────────────────────── Дневник ─────────────────────────────

@dataclass(frozen=True)
class Diary:
    start: datetime.date
    end: datetime.date
    schedule: List[Day]

    @classmethod
    def from_raw(cls, data: dict, type_mapping: Dict[int, str] | None = None) -> Diary:
        return cls(
            start=_parse_date(data["weekStart"]),
            end=_parse_date(data["weekEnd"]),
            schedule=[Day.from_raw(d, type_mapping) for d in data.get("weekDays", [])],
        )


# ─────────────────────────── Школы ───────────────────────────────

@dataclass(frozen=True)
class ShortSchool:
    name: str
    id: int
    address: str

    @classmethod
    def from_raw(cls, data: dict) -> ShortSchool:
        return cls(
            name=data["name"],
            id=data["id"],
            address=data.get("addressString", ""),
        )


@dataclass(frozen=True)
class School:
    name: str
    about: str
    address: str
    email: str
    site: str
    phone: str
    director: str
    ahc: str
    it_head: str
    uvr: str

    @classmethod
    def from_raw(cls, data: dict) -> School:
        """Собирает ``School`` из JSON ``/schools/{id}/card``.

        SGO хранит поля во вложенных объектах
        ``commonInfo``, ``contactInfo``, ``managementInfo`` —
        здесь они достаются и объединяются.
        """
        common = data.get("commonInfo", {})
        contact = data.get("contactInfo", {})
        mgmt = data.get("managementInfo", {})

        address = contact.get("juridicalAddress") or contact.get("postAddress", "")

        return cls(
            name=common.get("fullSchoolName", ""),
            about=common.get("about", ""),
            address=address,
            email=contact.get("email", ""),
            site=contact.get("web", ""),
            phone=contact.get("phones", ""),
            director=mgmt.get("director", ""),
            ahc=mgmt.get("principalAHC", ""),
            it_head=mgmt.get("principalIT", ""),
            uvr=mgmt.get("principalUVR", ""),
        )

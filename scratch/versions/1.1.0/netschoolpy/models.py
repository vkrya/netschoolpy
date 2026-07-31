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
    """Парсит datetime из ISO-строки.

    SGO может возвращать дробные секунды с различным количеством
    цифр (например ``10:51:34.99``), что ломает ``fromisoformat``
    в Python < 3.11.  Нормализуем до 6 цифр (микросекунды).
    """
    if isinstance(value, datetime.datetime):
        return value
    s = str(value)
    # Нормализуем дробную часть секунд до 6 цифр
    import re as _re
    m = _re.match(r'^(.+\.\d{1,6}?)(\d*)(.*)$', s)
    if m:
        frac = m.group(1)
        # дополняем до 6 цифр после точки
        dot_idx = frac.rfind('.')
        digits_after = frac[dot_idx + 1:]
        frac = frac[:dot_idx + 1] + digits_after.ljust(6, '0')
        s = frac + m.group(3)
    return datetime.datetime.fromisoformat(s)


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
        # В заданиях имя файла в "originalFileName",
        # в почтовых вложениях — в "name".
        name = data.get("originalFileName") or data.get("name") or ""
        return cls(
            id=data["id"],
            name=name,
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
    kind: str  # тип задания (из справочника), напр. «Контрольная работа»
    kind_abbr: str  # сокращение типа задания, напр. «К»
    content: str
    mark: Optional[int]
    weight: int  # коэффициент (вес) оценки
    is_duty: bool
    deadline: datetime.date
    attachments: List[Attachment] = field(default_factory=list)

    @classmethod
    def from_raw(
        cls,
        data: dict,
        type_mapping: Dict[int, dict] | None = None,
    ) -> Assignment:
        """Собирает ``Assignment`` из «сырого» JSON SGO.

        SGO вкладывает оценку в подобъект ``mark``:
            ``{"mark": {"mark": 5, "dutyMark": false}, "markComment": {"name": "..."}, ...}``
        Здесь это «разворачивается» в плоские поля.

        ``weight`` (коэффициент оценки) берётся прямо из задания.
        ``kind`` / ``kind_abbr`` берутся из справочника ``type_mapping``.
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
        type_info = (type_mapping or {}).get(kind_id, {})
        if isinstance(type_info, str):
            # обратная совместимость: старый формат {id: name}
            kind = type_info
            kind_abbr = ""
        else:
            kind = type_info.get("name", str(kind_id))
            kind_abbr = type_info.get("abbr", "")

        return cls(
            id=data["id"],
            comment=comment,
            kind=kind,
            kind_abbr=kind_abbr,
            content=data.get("assignmentName", ""),
            mark=mark_value,
            weight=data.get("weight", 1),
            is_duty=duty,
            deadline=_parse_date(data["dueDate"]),
            attachments=[Attachment.from_raw(a) for a in data.get("attachments", [])],
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
    def from_raw(cls, data: dict, type_mapping: Dict[int, dict] | None = None) -> Lesson:
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
    def from_raw(cls, data: dict, type_mapping: Dict[int, dict] | None = None) -> Day:
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
    def from_raw(cls, data: dict, type_mapping: Dict[int, dict] | None = None) -> Diary:
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


# ─────────────────────────── Почта / сообщения ─────────────────────

@dataclass(frozen=True)
class MailEntry:
    """Краткая запись о письме (из списка/реестра)."""
    id: int
    subject: str
    author: str
    sent: datetime.datetime
    to_names: Optional[str]

    @classmethod
    def from_raw(cls, data: dict) -> MailEntry:
        return cls(
            id=int(data["id"]),
            subject=data.get("subject", ""),
            author=data.get("author", ""),
            sent=_parse_datetime(data["sent"]),
            to_names=data.get("toNames"),
        )


@dataclass(frozen=True)
class MailPage:
    """Страница списка писем из реестра."""
    entries: List[MailEntry]
    page: int
    total_items: int

    @classmethod
    def from_raw(cls, data: dict) -> MailPage:
        return cls(
            entries=[MailEntry.from_raw(r) for r in data.get("rows", [])],
            page=data.get("page", 1),
            total_items=data.get("totalItems", 0),
        )


@dataclass(frozen=True)
class MailRecipient:
    """Получатель письма / контакт."""
    id: str  # base64-кодированный идентификатор
    name: str
    organization_name: str

    @classmethod
    def from_raw(cls, data: dict) -> MailRecipient:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            organization_name=data.get("organizationName") or "",
        )


@dataclass(frozen=True)
class Message:
    """Письмо внутренней почты SGO."""
    id: int
    subject: str
    text: str
    sent: datetime.datetime
    author_id: int
    author_name: str
    to_names: str  # кому адресовано (текст)
    is_read: bool
    mailbox: str  # "Inbox", "Sent", "Draft", "Deleted"
    can_reply: bool
    can_forward: bool
    file_attachments: List[Attachment] = field(default_factory=list)

    @classmethod
    def from_raw(cls, data: dict) -> Message:
        author = data.get("author", {})
        return cls(
            id=data["id"],
            subject=data.get("subject", ""),
            text=data.get("text", ""),
            sent=_parse_datetime(data["sent"]),
            author_id=author.get("id", 0),
            author_name=author.get("name", ""),
            to_names=data.get("toNames", ""),
            is_read=data.get("read", False),
            mailbox=data.get("mailBox", "Inbox"),
            can_reply=data.get("canReplyAll", False) or not data.get("noReply", True),
            can_forward=data.get("canForward", False),
            file_attachments=[
                Attachment.from_raw(a)
                for a in data.get("fileAttachments", [])
            ],
        )

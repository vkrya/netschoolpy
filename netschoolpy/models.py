from __future__ import annotations

import re
from datetime import date as DateType, datetime as DateTimeType, time as TimeType
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field


def _parse_date(val: Any) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val.split("T")[0])
    return date.today()


def _parse_time(val: Any) -> time:
    if isinstance(val, time):
        return val
    if isinstance(val, datetime):
        return val.time()
    if isinstance(val, str):
        parts = val.split(":")
        return time(int(parts[0]), int(parts[1]))
    return time(0, 0)


class Student(BaseModel):
    """Информация об ученике."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int = 0
    name: str = "Ученик"
    nick_name: Optional[str] = None
    user_type: Optional[str] = None
    group_name: Optional[str] = None

    @classmethod
    def from_raw(cls, data: dict) -> Student:
        return cls(
            id=data.get("id", 0),
            name=data.get("name") or data.get("nickName") or "Неизвестно",
            nick_name=data.get("nickName"),
            user_type=data.get("userType"),
            group_name=data.get("groupName"),
        )

    def __str__(self) -> str:
        return f"{self.name} (ID: {self.id})"


class LoginMethods(BaseModel):
    """Доступные способы авторизации на сервере SGO."""
    password: bool = True
    esia: bool = False
    esia_main: bool = False
    esia_button: bool = False
    signature: bool = False
    windows_auth: bool = False
    sms: bool = False
    esa: bool = False
    version: str = ""
    product_name: str = ""

    @classmethod
    def from_raw(cls, data: dict) -> LoginMethods:
        return cls(
            password=bool(data.get("schoolLogin", False)),
            esia=bool(data.get("esiaLogin", False)),
            esia_main=bool(data.get("esiaMainAuth", False)),
            esia_button=bool(data.get("esiaButton", False)),
            signature=bool(data.get("signatureLogin", False)),
            windows_auth=bool(data.get("windowsAuth", False)),
            sms=bool(data.get("enableSms", False)),
            esa=bool(data.get("esaLogin", False)),
            version=data.get("version", ""),
            product_name=data.get("productName", ""),
        )

    @property
    def summary(self) -> str:
        parts: list[str] = []
        if self.password and not self.esia_main:
            parts.append("логин/пароль")
        if self.esia:
            if self.esia_main:
                parts.append("только Госуслуги")
            else:
                parts.append("Госуслуги")
        if self.signature:
            parts.append("ЭП")
        if self.sms:
            parts.append("SMS")
        if self.esa:
            parts.append("ЕСА")
        if self.windows_auth:
            parts.append("Windows")
        return " + ".join(parts) if parts else "неизвестно"


class SchoolYear(BaseModel):
    """Учебный год."""
    id: int = 0
    name: str = ""

    @classmethod
    def from_raw(cls, data: dict) -> SchoolYear:
        return cls(
            id=data.get("id", 0),
            name=data.get("name") or str(data.get("id", "")),
        )


class ReportingPeriod(BaseModel):
    """Учебный период."""
    id: int = 0
    name: str = ""
    start: Optional[date] = None
    end: Optional[date] = None

    @classmethod
    def from_filter_source(
        cls, item: dict, *, date_range: Optional[dict] = None
    ) -> ReportingPeriod:
        s_date = None
        e_date = None
        if date_range:
            if date_range.get("start"):
                try:
                    s_date = date.fromisoformat(date_range["start"].split("T")[0])
                except Exception:
                    pass
            if date_range.get("end"):
                try:
                    e_date = date.fromisoformat(date_range["end"].split("T")[0])
                except Exception:
                    pass

        return cls(
            id=item.get("id", 0),
            name=item.get("name") or str(item.get("id", "")),
            start=s_date,
            end=e_date,
        )


class SubjectInfo(BaseModel):
    """Информация о предмете."""
    id: int = 0
    name: str = ""

    @classmethod
    def from_filter_item(cls, item: dict) -> SubjectInfo:
        return cls(
            id=item.get("id", 0),
            name=item.get("name") or "",
        )


class SubjectGrades(BaseModel):
    """Статистика оценок по предмету."""
    subject: str = ""
    marks: List[Tuple[int, int]] = Field(default_factory=list)
    average: float = 0.0

    @classmethod
    def compute(cls, subject: str, marks: List[Tuple[int, int]]) -> SubjectGrades:
        total_sum = sum(m * w for m, w in marks)
        total_weight = sum(w for _, w in marks)
        avg = round(total_sum / total_weight, 2) if total_weight > 0 else 0.0
        return cls(subject=subject, marks=marks, average=avg)


class SubjectTotalMark(BaseModel):
    """Итоговая оценка по предмету."""
    subject: str = ""
    period_marks: Dict[str, str] = Field(default_factory=dict)
    final_mark: Optional[str] = None


class AssignedMark(BaseModel):
    """Оценка за задание."""
    subject: str = ""
    assignment_name: str = ""
    mark: str = ""
    weight: int = 1
    date: DateType = Field(default_factory=DateType.today)
    assignment_id: Optional[int] = None


class Attachment(BaseModel):
    """Вложение к заданию."""
    id: int = 0
    name: str = ""

    @classmethod
    def from_raw(cls, data: dict) -> Attachment:
        return cls(
            id=data.get("id", 0),
            name=data.get("name") or data.get("fileName") or "Без имени",
        )


class Assignment(BaseModel):
    """Задание / Домашняя работа."""
    id: int = 0
    title: str = ""
    type_name: str = "Домашнее задание"
    comment: Optional[str] = None
    kind: Optional[str] = None
    kind_abbr: Optional[str] = None
    content: Optional[str] = None
    weight: int = 1
    is_duty: bool = False
    deadline: Optional[date] = None
    mark: Optional[int] = None
    duty_mark: bool = False
    attachments: List[Attachment] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, data: dict, type_mapping: Optional[Dict[int, dict]] = None) -> Assignment:
        assign_type_id = data.get("typeId")
        t_name = "Задание"
        t_weight = 1

        if type_mapping and assign_type_id in type_mapping:
            t_info = type_mapping[assign_type_id]
            t_name = t_info.get("name", t_name)
            t_weight = t_info.get("weight", t_weight)

        raw_mark = data.get("mark")
        mark_val = None
        if isinstance(raw_mark, dict):
            m = raw_mark.get("mark")
            if m is not None:
                try:
                    mark_val = int(m)
                except (ValueError, TypeError):
                    pass
        elif raw_mark is not None:
            try:
                mark_val = int(raw_mark)
            except (ValueError, TypeError):
                pass

        raw_atts = data.get("attachments") or []
        atts = [Attachment.from_raw(a) for a in raw_atts if isinstance(a, dict)]

        return cls(
            id=data.get("id", 0),
            title=data.get("assignmentName") or data.get("name") or "Задание",
            type_name=t_name,
            weight=t_weight,
            mark=mark_val,
            duty_mark=bool(data.get("dutyMark", False)),
            comment=data.get("comment"),
            attachments=atts,
        )


class Lesson(BaseModel):
    """Урок в расписании."""
    number: int = 1
    subject: str = ""
    start: Union[datetime, time, str] = Field(default_factory=datetime.now)
    end: Union[datetime, time, str] = Field(default_factory=datetime.now)
    room: Optional[str] = None
    day: Optional[date] = None
    assignments: List[Assignment] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, data: dict, type_mapping: Optional[Dict[int, dict]] = None) -> Lesson:
        s_val = data.get("start") or data.get("startTime") or datetime.now()
        e_val = data.get("end") or data.get("endTime") or datetime.now()

        raw_assigns = data.get("assignments") or []
        assigns = [Assignment.from_raw(a, type_mapping) for a in raw_assigns if isinstance(a, dict)]

        return cls(
            number=data.get("number", 1),
            subject=data.get("subjectName") or data.get("subject") or "Предмет",
            start=s_val,
            end=e_val,
            room=data.get("room"),
            assignments=assigns,
        )

    def to_ical_event(self) -> str:
        dt_format = "%Y%m%dT%H%M%SZ"
        if isinstance(self.start, datetime):
            start_str = self.start.strftime(dt_format)
            uid_ts = int(self.start.timestamp())
        else:
            start_str = datetime.now().strftime(dt_format)
            uid_ts = int(datetime.now().timestamp())

        if isinstance(self.end, datetime):
            end_str = self.end.strftime(dt_format)
        else:
            end_str = datetime.now().strftime(dt_format)

        summary = f"{self.number}. {self.subject}"
        desc = []
        if self.room:
            desc.append(f"Кабинет: {self.room}")
        for a in self.assignments:
            assign_str = f"• {a.title} [{a.type_name}]"
            if a.mark:
                assign_str += f" — Оценка: {a.mark}"
            desc.append(assign_str)
        description_str = "\n".join(desc)

        lines = [
            "BEGIN:VEVENT",
            f"UID:netschool-lesson-{uid_ts}-{self.number}@netschoolpy",
            f"DTSTAMP:{datetime.now().strftime(dt_format)}",
            f"DTSTART:{start_str}",
            f"DTEND:{end_str}",
            f"SUMMARY:{summary}",
        ]
        if self.room:
            lines.append(f"LOCATION:{self.room}")
        if description_str:
            lines.append(f"DESCRIPTION:{description_str}")
        lines.append("END:VEVENT")
        return "\n".join(lines)


class Day(BaseModel):
    """День в расписании."""
    date: DateType = Field(default_factory=DateType.today)
    lessons: List[Lesson] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, data: dict, type_mapping: Optional[Dict[int, dict]] = None) -> Day:
        d_val = _parse_date(data.get("date") or data.get("day"))
        raw_lessons = data.get("lessons") or []
        lessons_list = [Lesson.from_raw(l, type_mapping) for l in raw_lessons if isinstance(l, dict)]
        return cls(date=d_val, lessons=lessons_list)


class Diary(BaseModel):
    """Дневник."""
    start: date = Field(default_factory=date.today)
    end: date = Field(default_factory=date.today)
    days: List[Day] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, data: dict, type_mapping: Optional[Dict[int, dict]] = None) -> Diary:
        s_date = _parse_date(data.get("weekStart") or data.get("start"))
        e_date = _parse_date(data.get("weekEnd") or data.get("end"))

        raw_days = data.get("weekDays") or data.get("days") or []
        days_list = [Day.from_raw(d, type_mapping) for d in raw_days if isinstance(d, dict)]
        return cls(start=s_date, end=e_date, days=days_list)

    def to_ical(self) -> str:
        events = []
        for day in self.days:
            for lesson in day.lessons:
                events.append(lesson.to_ical_event())

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//netschoolpy//NetSchool Diary//RU",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Сетевой Город - Дневник",
        ]
        lines.extend(events)
        lines.append("END:VCALENDAR")
        return "\n".join(lines)


class Announcement(BaseModel):
    """Объявление."""
    id: int = 0
    title: str = ""
    description: str = ""
    author: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_raw(cls, data: dict) -> Announcement:
        dt = None
        if data.get("postDate"):
            try:
                dt = datetime.fromisoformat(data["postDate"].replace("Z", "+00:00"))
            except Exception:
                pass
        return cls(
            id=data.get("id", 0),
            title=data.get("name") or data.get("title") or "Объявление",
            description=data.get("description") or "",
            author=data.get("author", {}).get("name") if isinstance(data.get("author"), dict) else data.get("author"),
            created_at=dt,
        )


class ShortSchool(BaseModel):
    """Школа."""
    id: int = 0
    name: str = ""


class School(BaseModel):
    """Информация о школе."""
    id: int = 0
    name: str = ""
    full_name: Optional[str] = None

    @classmethod
    def from_raw(cls, data: dict) -> School:
        return cls(
            id=data.get("id", 0),
            name=data.get("name") or "Школа",
            full_name=data.get("fullName"),
        )


SchoolInfo = School


class MailEntry(BaseModel):
    """Письмо во внутренней почте."""
    id: int = 0
    subject: str = ""
    author: Optional[str] = None
    date: Optional[datetime] = None

    @classmethod
    def from_raw(cls, data: dict) -> MailEntry:
        dt = None
        if data.get("date"):
            try:
                dt = datetime.fromisoformat(data["date"].replace("Z", "+00:00"))
            except Exception:
                pass
        return cls(
            id=data.get("id", 0),
            subject=data.get("subject") or data.get("name") or "Без темы",
            author=data.get("authorName") or data.get("author"),
            date=dt,
        )


class MailPage(BaseModel):
    """Страница писем."""
    entries: List[MailEntry] = Field(default_factory=list)
    total_count: int = 0

    @classmethod
    def from_raw(cls, data: dict) -> MailPage:
        raw_rows = data.get("rows") or data.get("entries") or []
        entries = [MailEntry.from_raw(r) for r in raw_rows if isinstance(r, dict)]
        return cls(
            entries=entries,
            total_count=data.get("totalCount") or len(entries),
        )


class MailRecipient(BaseModel):
    id: int = 0
    name: str = ""


class Message(BaseModel):
    id: int = 0
    subject: str = ""
    text: str = ""


class Author(BaseModel):
    id: int = 0
    name: str = ""


class TotalMarksReportLine(BaseModel):
    subject: str = ""
    period_marks: Dict[str, str] = Field(default_factory=dict)

SPECIAL_MARK_DESCRIPTIONS: Dict[str, str] = {
    "УП": "Пропуск по уважительной причине",
    "Б": "Пропустил по болезни",
    "НП": "Пропуск по неуважительной причине",
    "ОТ": "Отсутствовал",
    "ОП": "Опоздал",
    "ОСВ": "Освобожден от посещения",
}

"""Модели данных netschoolpy — plain dataclasses с ручным парсингом JSON."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


SPECIAL_MARK_DESCRIPTIONS: Dict[str, str] = {
    "УП": "Пропуск по уважительной причине",
    "Б": "Пропустил по болезни",
    "НП": "Пропуск по неуважительной причине",
    "ОТ": "Отсутствовал",
    "ОП": "Опоздал",
    "ОСВ": "Освобожден от посещения",
}


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
    m = _re.match(r'^(.+\.\d{1,6})(\d*)(.*)$', s)
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


# ──────────────────────────── Ученик ──────────────────────────────

@dataclass(frozen=True)
class Student:
    """Ученик (ребёнок), привязанный к аккаунту.

    Для родительских аккаунтов может быть несколько учеников.
    """
    id: int
    name: str

    @classmethod
    def from_raw(cls, data: dict) -> Student:
        return cls(
            id=data["studentId"],
            name=data.get("nickName") or data.get("name") or "",
        )

    def __str__(self) -> str:
        return self.name or str(self.id)


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
    mark_text: Optional[str] = None
    special_mark_code: Optional[str] = None
    special_mark_description: Optional[str] = None
    mark_set_date: Optional[datetime.date] = None
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
        mark_text: Optional[str] = None
        if isinstance(raw_mark, dict):
            raw_mark_value = raw_mark.get("mark")
            mark_value: Optional[int] = raw_mark_value if isinstance(raw_mark_value, int) else None
            if raw_mark_value is not None and str(raw_mark_value).strip():
                mark_text = str(raw_mark_value).strip()

            # В разных инсталляциях SGO спец-пометки могут лежать
            # в name/abbr/value вместо mark.
            if not mark_text:
                for key in ("abbr", "shortName", "name", "value"):
                    candidate = raw_mark.get(key)
                    if candidate is None:
                        continue
                    text = str(candidate).strip()
                    if text:
                        mark_text = text
                        break
            duty: bool = raw_mark.get("dutyMark", False)
        elif isinstance(raw_mark, int):
            mark_value = raw_mark
            mark_text = str(raw_mark)
            duty = False
        elif isinstance(raw_mark, str):
            mark_value = int(raw_mark) if raw_mark.isdigit() else None
            mark_text = raw_mark.strip() or None
            duty = False
        else:
            mark_value = None
            duty = False

        mark_comment = data.get("markComment")
        comment = mark_comment["name"] if isinstance(mark_comment, dict) and "name" in mark_comment else ""

        if mark_text and mark_text.isdigit() and mark_value is None:
            mark_value = int(mark_text)

        special_mark_code = mark_text.upper() if mark_text and mark_text.upper() in SPECIAL_MARK_DESCRIPTIONS else None
        special_mark_description = SPECIAL_MARK_DESCRIPTIONS.get(special_mark_code) if special_mark_code else None

        mark_set_date: Optional[datetime.date] = None
        for mark_date_key in (
            "markDate",
            "setDate",
            "markSetDate",
            "dateSet",
            "gradeDate",
            "gradeSetDate",
        ):
            raw_mark_date = data.get(mark_date_key)
            if raw_mark_date:
                mark_set_date = _parse_date(raw_mark_date)
                break

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
            mark_text=mark_text,
            special_mark_code=special_mark_code,
            special_mark_description=special_mark_description,
            mark_set_date=mark_set_date,
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


# ─────────────────────── Итоговые отметки ───────────────────────

@dataclass(frozen=True)
class SubjectTotalMark:
    """Строка из отчета «Итоговые отметки».

    ``period_marks`` содержит оценки по учебным периодам
    (четверти/триместры и т.д.) в порядке следования в отчете.
    """

    order: int
    subject: str
    period_marks: List[Optional[str]]
    year_mark: Optional[str]
    exam_mark: Optional[str]
    final_mark: Optional[str]


@dataclass(frozen=True)
class AssignedMark:
    """Строка из отчета «Успеваемость ученика» (StudentGrades)."""

    subject: str
    assignment_type: str
    topic: str
    lesson_date: datetime.date
    mark_set_date: datetime.date
    mark_text: str
    numeric_mark: Optional[int]
    special_mark_code: Optional[str]
    special_mark_description: Optional[str]


# ─────────────────────────── Школы ───────────────────────────────

@dataclass(frozen=True)
class ShortSchool:
    name: str
    id: int
    short_name: str = ""
    address: str = ""

    @classmethod
    def from_raw(cls, data: dict) -> ShortSchool:
        return cls(
            name=data["name"],
            id=data["id"],
            short_name=data.get("shortName", ""),
            address=data.get("addressString") or data.get("address") or "",
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


# ─────────────────────────── Способы входа ───────────────────────────

@dataclass(frozen=True)
class LoginMethods:
    """Доступные способы авторизации на сервере SGO.

    Поля:
        password: Вход по логину и паролю SGO.
        esia: Вход через Госуслуги (ЕСИА) доступен.
        esia_main: Госуслуги — основной/обязательный способ входа.
        esia_button: Кнопка «Войти через Госуслуги» отображается.
        signature: Вход по электронной подписи.
        windows_auth: Вход через Windows-аутентификацию.
        sms: Вход по SMS.
        esa: Вход через ЕСА (Единая система авторизации).
        version: Версия сервера «Сетевой Город».
        product_name: Название продукта.

    Свойство :attr:`summary` возвращает человекочитаемое описание.
    """
    password: bool
    esia: bool
    esia_main: bool
    esia_button: bool
    signature: bool = False
    windows_auth: bool = False
    sms: bool = False
    esa: bool = False
    version: str = ""
    product_name: str = ""

    @classmethod
    def from_raw(cls, data: dict) -> LoginMethods:
        """Собирает ``LoginMethods`` из JSON ``/logindata``."""
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
        """Человекочитаемое описание способов входа.

        Примеры::

            "только Госуслуги"
            "логин/пароль + Госуслуги"
            "логин/пароль"
        """
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


# ─────────────────────── Учебные периоды / оценки ────────────────────

@dataclass(frozen=True)
class ReportingPeriod:
    """Учебный период (четверть, полугодие, год и т.п.).

    Поля:
        id: Идентификатор периода на сервере SGO.
        name: Название, например ``"1 четверть"`` или ``"Произвольный интервал"``.
        start: Дата начала периода (``None``, если период — произвольный интервал).
        end: Дата окончания периода.
    """
    id: int
    name: str
    start: Optional[datetime.date] = None
    end: Optional[datetime.date] = None

    @classmethod
    def from_filter_source(cls, item: dict, *, date_range: Optional[dict] = None) -> ReportingPeriod:
        period_id = int(item["value"])
        start = end = None
        if date_range:
            raw_start = date_range.get("start")
            raw_end = date_range.get("end")
            if raw_start:
                start = _parse_date(raw_start)
            if raw_end:
                end = _parse_date(raw_end)
        return cls(id=period_id, name=item["title"], start=start, end=end)


@dataclass(frozen=True)
class SubjectInfo:
    """Предмет ученика.

    Поля:
        id: Идентификатор предмета в SGO.
        name: Название, например ``"Алгебра"``.
    """
    id: int
    name: str

    @classmethod
    def from_filter_item(cls, item: dict) -> SubjectInfo:
        return cls(id=int(item["value"]), name=item["title"])


@dataclass(frozen=True)
class SubjectGrades:
    """Оценки по одному предмету за период.

    Поля:
        subject: Название предмета.
        marks: Список пар ``(оценка, вес)``.
        average: Простой средний балл.
        weighted_average: Средневзвешенный балл.
    """
    subject: str
    marks: List[Tuple[int, int]]
    average: float
    weighted_average: float

    @classmethod
    def compute(cls, subject: str, marks: List[Tuple[int, int]]) -> SubjectGrades:
        """Подсчитать средний и средневзвешенный баллы из списка ``(оценка, вес)``."""
        if not marks:
            return cls(subject=subject, marks=[], average=0.0, weighted_average=0.0)
        avg = sum(m for m, _ in marks) / len(marks)
        total_w = sum(w for _, w in marks)
        wavg = sum(m * w for m, w in marks) / total_w if total_w else 0.0
        return cls(subject=subject, marks=marks, average=avg, weighted_average=wavg)


@dataclass(frozen=True)
class SchoolYear:
    """Учебный год.

    Поля:
        id: Идентификатор года (``schoolYearId``).
        name: Название, например ``"2025/2026"``.
        start: Дата начала.
        end: Дата окончания.
    """
    id: int
    name: str
    start: datetime.date
    end: datetime.date

    @classmethod
    def from_raw(cls, data: dict) -> SchoolYear:
        gy = data.get("globalYear", data)
        return cls(
            id=data.get("id", gy.get("id", 0)),
            name=gy.get("name", ""),
            start=_parse_date(data.get("startDate", gy.get("startDate", ""))),
            end=_parse_date(data.get("endDate", gy.get("endDate", ""))),
        )



@dataclass
class TotalMarksReportLine:
    """Строка отчёта 'Итоговые оценки'."""
    order: int
    subject: str
    period_marks: list[str]
    year_mark: str | None = None
    exam_mark: str | None = None
    final_mark: str | None = None

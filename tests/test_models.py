"""Тесты парсинга моделей данных."""

import datetime

from netschoolpy.models import (
    Announcement,
    Assignment,
    Attachment,
    Author,
    Day,
    Diary,
    Lesson,
    LoginMethods,
    MailEntry,
    MailPage,
    MailRecipient,
    Message,
    School,
    ShortSchool,
    Student,
    _parse_date,
    _parse_datetime,
    _parse_time,
)


# ═══════════════════════════════════════════════════════════
#  _parse_date
# ═══════════════════════════════════════════════════════════


class TestParseDate:
    def test_iso_with_time(self):
        assert _parse_date("2024-01-15T00:00:00") == datetime.date(2024, 1, 15)

    def test_iso_date_only(self):
        assert _parse_date("2024-12-31") == datetime.date(2024, 12, 31)

    def test_passthrough(self):
        d = datetime.date(2025, 6, 1)
        assert _parse_date(d) is d


# ═══════════════════════════════════════════════════════════
#  _parse_datetime
# ═══════════════════════════════════════════════════════════


class TestParseDatetime:
    def test_simple_iso(self):
        dt = _parse_datetime("2024-01-15T10:30:00")
        assert dt == datetime.datetime(2024, 1, 15, 10, 30, 0)

    def test_fractional_seconds_short(self):
        """SGO иногда возвращает .99 вместо .990000."""
        dt = _parse_datetime("2024-01-15T10:51:34.99")
        assert dt.second == 34
        assert dt.microsecond == 990000

    def test_fractional_seconds_full(self):
        dt = _parse_datetime("2024-01-15T10:51:34.123456")
        assert dt.microsecond == 123456

    def test_fractional_seconds_3_digits(self):
        dt = _parse_datetime("2024-01-15T10:51:34.123")
        assert dt.microsecond == 123000

    def test_passthrough(self):
        dt = datetime.datetime(2025, 1, 1, 12, 0)
        assert _parse_datetime(dt) is dt


# ═══════════════════════════════════════════════════════════
#  _parse_time
# ═══════════════════════════════════════════════════════════


class TestParseTime:
    def test_hh_mm(self):
        assert _parse_time("08:30") == datetime.time(8, 30, 0)

    def test_hh_mm_ss(self):
        assert _parse_time("14:05:30") == datetime.time(14, 5, 30)

    def test_passthrough(self):
        t = datetime.time(9, 0)
        assert _parse_time(t) is t


# ═══════════════════════════════════════════════════════════
#  Attachment
# ═══════════════════════════════════════════════════════════


class TestAttachment:
    def test_from_raw_assignment_style(self):
        raw = {"id": 1, "originalFileName": "homework.pdf", "description": "ДЗ"}
        a = Attachment.from_raw(raw)
        assert a.id == 1
        assert a.name == "homework.pdf"
        assert a.description == "ДЗ"

    def test_from_raw_mail_style(self):
        raw = {"id": 2, "name": "photo.jpg"}
        a = Attachment.from_raw(raw)
        assert a.name == "photo.jpg"
        assert a.description == ""

    def test_from_raw_no_name(self):
        raw = {"id": 3}
        a = Attachment.from_raw(raw)
        assert a.name == ""


# ═══════════════════════════════════════════════════════════
#  Author
# ═══════════════════════════════════════════════════════════


class TestAuthor:
    def test_from_raw(self):
        raw = {"id": 42, "fio": "Иванов И.И.", "nickName": "teacher"}
        a = Author.from_raw(raw)
        assert a.id == 42
        assert a.full_name == "Иванов И.И."
        assert a.nickname == "teacher"

    def test_from_raw_missing_fields(self):
        raw = {"id": 1}
        a = Author.from_raw(raw)
        assert a.full_name == ""
        assert a.nickname == ""


# ═══════════════════════════════════════════════════════════
#  Announcement
# ═══════════════════════════════════════════════════════════


class TestAnnouncement:
    def test_from_raw(self):
        raw = {
            "name": "Собрание",
            "author": {"id": 1, "fio": "Директор", "nickName": "dir"},
            "description": "Завтра в 18:00",
            "postDate": "2024-09-01T12:00:00",
            "attachments": [
                {"id": 10, "originalFileName": "plan.docx"},
            ],
        }
        ann = Announcement.from_raw(raw)
        assert ann.name == "Собрание"
        assert ann.author.full_name == "Директор"
        assert ann.content == "Завтра в 18:00"
        assert ann.post_date == datetime.datetime(2024, 9, 1, 12, 0, 0)
        assert len(ann.attachments) == 1
        assert ann.attachments[0].name == "plan.docx"

    def test_from_raw_no_attachments(self):
        raw = {
            "name": "Тест",
            "author": {"id": 1, "fio": "", "nickName": ""},
            "postDate": "2024-01-01T00:00:00",
        }
        ann = Announcement.from_raw(raw)
        assert ann.attachments == []
        assert ann.content == ""


# ═══════════════════════════════════════════════════════════
#  Assignment
# ═══════════════════════════════════════════════════════════


class TestAssignment:
    def test_from_raw_with_mark(self):
        raw = {
            "id": 100,
            "typeId": 1,
            "assignmentName": "Упражнение 5",
            "mark": {"mark": 5, "dutyMark": False},
            "markComment": {"name": "Отлично"},
            "weight": 2,
            "dueDate": "2024-09-15T00:00:00",
            "attachments": [],
        }
        mapping = {1: {"name": "Домашняя работа", "abbr": "Д"}}
        a = Assignment.from_raw(raw, mapping)
        assert a.id == 100
        assert a.mark == 5
        assert a.mark_text == "5"
        assert a.weight == 2
        assert a.is_duty is False
        assert a.kind == "Домашняя работа"
        assert a.kind_abbr == "Д"
        assert a.comment == "Отлично"
        assert a.content == "Упражнение 5"
        assert a.deadline == datetime.date(2024, 9, 15)

    def test_from_raw_no_mark(self):
        raw = {
            "id": 101,
            "typeId": 99,
            "assignmentName": "Задание",
            "dueDate": "2024-09-16T00:00:00",
        }
        a = Assignment.from_raw(raw)
        assert a.mark is None
        assert a.mark_text is None
        assert a.is_duty is False
        assert a.kind == "99"  # fallback to str(kind_id)
        assert a.weight == 1

    def test_from_raw_with_special_mark(self):
        raw = {
            "id": 104,
            "typeId": 1,
            "assignmentName": "Посещение",
            "mark": {"mark": "УП", "dutyMark": False},
            "dueDate": "2024-09-18T00:00:00",
            "markDate": "2024-09-19T00:00:00",
        }
        a = Assignment.from_raw(raw)
        assert a.mark is None
        assert a.mark_text == "УП"
        assert a.special_mark_code == "УП"
        assert a.special_mark_description == "Пропуск по уважительной причине"
        assert a.mark_set_date == datetime.date(2024, 9, 19)

    def test_from_raw_duty_mark(self):
        raw = {
            "id": 102,
            "typeId": 1,
            "assignmentName": "Долг",
            "mark": {"mark": 2, "dutyMark": True},
            "dueDate": "2024-09-17T00:00:00",
        }
        a = Assignment.from_raw(raw)
        assert a.is_duty is True
        assert a.mark == 2

    def test_from_raw_old_mapping_format(self):
        """Обратная совместимость: старый формат {id: name}."""
        raw = {
            "id": 103,
            "typeId": 5,
            "assignmentName": "Тест",
            "dueDate": "2024-09-18T00:00:00",
        }
        mapping = {5: "Контрольная"}  # type: ignore[dict-item]
        a = Assignment.from_raw(raw, mapping)
        assert a.kind == "Контрольная"
        assert a.kind_abbr == ""


# ═══════════════════════════════════════════════════════════
#  Lesson
# ═══════════════════════════════════════════════════════════


class TestLesson:
    def test_from_raw(self):
        raw = {
            "day": "2024-09-02T00:00:00",
            "startTime": "08:30",
            "endTime": "09:15",
            "room": "301",
            "number": 1,
            "subjectName": "Математика",
            "assignments": [
                {
                    "id": 200,
                    "typeId": 1,
                    "assignmentName": "§5",
                    "dueDate": "2024-09-02T00:00:00",
                },
            ],
        }
        lesson = Lesson.from_raw(raw)
        assert lesson.day == datetime.date(2024, 9, 2)
        assert lesson.start == datetime.time(8, 30, 0)
        assert lesson.end == datetime.time(9, 15, 0)
        assert lesson.room == "301"
        assert lesson.number == 1
        assert lesson.subject == "Математика"
        assert len(lesson.assignments) == 1

    def test_from_raw_no_room(self):
        raw = {
            "day": "2024-09-02T00:00:00",
            "startTime": "09:25",
            "endTime": "10:10",
            "number": 2,
            "subjectName": "Физика",
        }
        lesson = Lesson.from_raw(raw)
        assert lesson.room == ""
        assert lesson.assignments == []


# ═══════════════════════════════════════════════════════════
#  Day
# ═══════════════════════════════════════════════════════════


class TestDay:
    def test_from_raw(self):
        raw = {
            "date": "2024-09-02T00:00:00",
            "lessons": [
                {
                    "day": "2024-09-02T00:00:00",
                    "startTime": "08:30",
                    "endTime": "09:15",
                    "number": 1,
                    "subjectName": "Русский язык",
                },
            ],
        }
        day = Day.from_raw(raw)
        assert day.day == datetime.date(2024, 9, 2)
        assert len(day.lessons) == 1

    def test_from_raw_empty(self):
        raw = {"date": "2024-09-03T00:00:00"}
        day = Day.from_raw(raw)
        assert day.lessons == []


# ═══════════════════════════════════════════════════════════
#  Diary
# ═══════════════════════════════════════════════════════════


class TestDiary:
    def test_from_raw(self):
        raw = {
            "weekStart": "2024-09-02T00:00:00",
            "weekEnd": "2024-09-07T00:00:00",
            "weekDays": [
                {
                    "date": "2024-09-02T00:00:00",
                    "lessons": [],
                },
                {
                    "date": "2024-09-03T00:00:00",
                    "lessons": [],
                },
            ],
        }
        diary = Diary.from_raw(raw)
        assert diary.start == datetime.date(2024, 9, 2)
        assert diary.end == datetime.date(2024, 9, 7)
        assert len(diary.schedule) == 2

    def test_from_raw_empty_week(self):
        raw = {
            "weekStart": "2024-09-02T00:00:00",
            "weekEnd": "2024-09-07T00:00:00",
        }
        diary = Diary.from_raw(raw)
        assert diary.schedule == []


# ═══════════════════════════════════════════════════════════
#  ShortSchool / School
# ═══════════════════════════════════════════════════════════


class TestShortSchool:
    def test_from_raw(self):
        raw = {"name": "Школа №1", "id": 42, "addressString": "ул. Ленина, 1"}
        s = ShortSchool.from_raw(raw)
        assert s.name == "Школа №1"
        assert s.id == 42
        assert s.address == "ул. Ленина, 1"
        assert s.short_name == ""

    def test_from_raw_no_address(self):
        raw = {"name": "Школа №2", "id": 43}
        s = ShortSchool.from_raw(raw)
        assert s.address == ""
        assert s.short_name == ""

    def test_from_raw_search_api(self):
        """Формат ответа /schools/search."""
        raw = {
            "provinceId": 0,
            "cityId": 1259,
            "inn": "1326135767",
            "ogrn": "1021300981767",
            "address": None,
            "shortName": 'МОУ "Средняя школа № 24"',
            "id": 1110,
            "name": 'МОУ "Средняя школа № 24" (г. Саранск)',
        }
        s = ShortSchool.from_raw(raw)
        assert s.id == 1110
        assert s.name == 'МОУ "Средняя школа № 24" (г. Саранск)'
        assert s.short_name == 'МОУ "Средняя школа № 24"'
        assert s.address == ""  # address=None → ""


class TestSchool:
    def test_from_raw(self):
        raw = {
            "commonInfo": {
                "fullSchoolName": "МБОУ «Школа №1»",
                "about": "Описание",
            },
            "contactInfo": {
                "juridicalAddress": "г. Город, ул. Мира, 1",
                "email": "school@example.ru",
                "web": "https://school1.ru",
                "phones": "+7(123)456-78-90",
            },
            "managementInfo": {
                "director": "Иванов И.И.",
                "principalAHC": "Петров П.П.",
                "principalIT": "Сидоров С.С.",
                "principalUVR": "Козлова К.К.",
            },
        }
        s = School.from_raw(raw)
        assert s.name == "МБОУ «Школа №1»"
        assert s.about == "Описание"
        assert s.email == "school@example.ru"
        assert s.director == "Иванов И.И."

    def test_from_raw_minimal(self):
        s = School.from_raw({})
        assert s.name == ""
        assert s.email == ""


# ═══════════════════════════════════════════════════════════
#  LoginMethods
# ═══════════════════════════════════════════════════════════


class TestLoginMethods:
    def _mordovia_raw(self) -> dict:
        """Типичный ответ /logindata (Мордовия)."""
        return {
            "productName": "Сетевой Город. Образование",
            "version": "5.47.0",
            "schoolLogin": True,
            "emLogin": True,
            "esiaLogin": True,
            "esiaLoginPage": "/webapi/sso/esia/crosslogin",
            "esiaMainAuth": False,
            "esiaButton": True,
            "signatureLogin": False,
            "windowsAuth": False,
            "enableSms": False,
            "esaLogin": False,
        }

    def test_password_and_esia(self):
        """Мордовия: логин/пароль + Госуслуги."""
        m = LoginMethods.from_raw(self._mordovia_raw())
        assert m.password is True
        assert m.esia is True
        assert m.esia_main is False
        assert m.esia_button is True
        assert m.version == "5.47.0"
        assert "логин/пароль" in m.summary
        assert "Госуслуги" in m.summary

    def test_esia_only(self):
        """Сервер, где только Госуслуги (esiaMainAuth=True)."""
        raw = self._mordovia_raw()
        raw["esiaMainAuth"] = True
        raw["esiaButton"] = False
        m = LoginMethods.from_raw(raw)
        assert m.esia_main is True
        assert "только Госуслуги" in m.summary
        # логин/пароль не должен быть в summary когда esia_main
        assert "логин/пароль" not in m.summary

    def test_password_only(self):
        """Сервер только с логин/пароль."""
        raw = {
            "schoolLogin": True,
            "esiaLogin": False,
            "esiaMainAuth": False,
            "esiaButton": False,
        }
        m = LoginMethods.from_raw(raw)
        assert m.password is True
        assert m.esia is False
        assert m.summary == "логин/пароль"

    def test_empty_raw(self):
        m = LoginMethods.from_raw({})
        assert m.password is False
        assert m.esia is False
        assert m.summary == "неизвестно"

    def test_all_flags(self):
        """Все флаги включены."""
        raw = {
            "schoolLogin": True,
            "esiaLogin": True,
            "esiaMainAuth": False,
            "esiaButton": True,
            "signatureLogin": True,
            "enableSms": True,
            "esaLogin": True,
            "windowsAuth": True,
        }
        m = LoginMethods.from_raw(raw)
        assert m.signature is True
        assert m.sms is True
        assert m.esa is True
        assert m.windows_auth is True
        assert "ЭП" in m.summary
        assert "SMS" in m.summary


# ═══════════════════════════════════════════════════════════
#  Mail models
# ═══════════════════════════════════════════════════════════


class TestMailEntry:
    def test_from_raw(self):
        raw = {
            "id": "123",
            "subject": "Тема",
            "author": "Учитель",
            "sent": "2024-09-10T14:30:00",
            "toNames": "Ученик",
        }
        e = MailEntry.from_raw(raw)
        assert e.id == 123
        assert e.subject == "Тема"
        assert e.author == "Учитель"
        assert e.to_names == "Ученик"


class TestMailPage:
    def test_from_raw(self):
        raw = {
            "rows": [
                {
                    "id": "1",
                    "subject": "A",
                    "author": "X",
                    "sent": "2024-01-01T00:00:00",
                },
                {
                    "id": "2",
                    "subject": "B",
                    "author": "Y",
                    "sent": "2024-01-02T00:00:00",
                },
            ],
            "page": 1,
            "totalItems": 50,
        }
        mp = MailPage.from_raw(raw)
        assert len(mp.entries) == 2
        assert mp.page == 1
        assert mp.total_items == 50

    def test_from_raw_empty(self):
        mp = MailPage.from_raw({})
        assert mp.entries == []
        assert mp.total_items == 0


class TestMailRecipient:
    def test_from_raw(self):
        raw = {
            "id": "abc123==",
            "name": "Учитель Математики",
            "organizationName": "Школа №1",
        }
        r = MailRecipient.from_raw(raw)
        assert r.id == "abc123=="
        assert r.name == "Учитель Математики"
        assert r.organization_name == "Школа №1"


class TestMessage:
    def test_from_raw(self):
        raw = {
            "id": 999,
            "subject": "Важно!",
            "text": "<p>Текст сообщения</p>",
            "sent": "2024-09-10T15:00:00",
            "author": {"id": 1, "name": "Директор"},
            "toNames": "Родитель",
            "read": True,
            "mailBox": "Inbox",
            "canReplyAll": True,
            "canForward": True,
            "fileAttachments": [
                {"id": 50, "name": "doc.pdf"},
            ],
        }
        m = Message.from_raw(raw)
        assert m.id == 999
        assert m.subject == "Важно!"
        assert m.text == "<p>Текст сообщения</p>"
        assert m.author_id == 1
        assert m.author_name == "Директор"
        assert m.is_read is True
        assert m.mailbox == "Inbox"
        assert m.can_reply is True
        assert m.can_forward is True
        assert len(m.file_attachments) == 1

    def test_from_raw_minimal(self):
        raw = {
            "id": 1,
            "sent": "2024-01-01T00:00:00",
        }
        m = Message.from_raw(raw)
        assert m.subject == ""
        assert m.text == ""
        assert m.author_id == 0
        assert m.is_read is False
        assert m.file_attachments == []


# ═══════════════════════════════════════════════════════════
#  Student
# ═══════════════════════════════════════════════════════════


class TestStudent:
    def test_from_raw(self):
        raw = {"studentId": 123, "nickName": "Иванов Иван"}
        s = Student.from_raw(raw)
        assert s.id == 123
        assert s.name == "Иванов Иван"

    def test_from_raw_name_fallback(self):
        raw = {"studentId": 456, "name": "Фамилия Имя"}
        s = Student.from_raw(raw)
        assert s.name == "Фамилия Имя"

    def test_from_raw_no_name(self):
        raw = {"studentId": 789}
        s = Student.from_raw(raw)
        assert s.name == ""

    def test_str(self):
        s = Student(id=1, name="Тест")
        assert str(s) == "Тест"

    def test_str_no_name(self):
        s = Student(id=42, name="")
        assert str(s) == "42"

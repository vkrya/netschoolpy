"""Тесты клиентских утилит (cookies, session store, exceptions)."""

import datetime
import json

import pytest

from netschoolpy import NetSchool
from netschoolpy.client import get_login_methods, get_total_marks, search_schools
from netschoolpy.exceptions import (
    ESIAError,
    LoginError,
    MFAError,
    NetSchoolError,
    SchoolNotFound,
    SessionExpired,
)


# ═══════════════════════════════════════════════════════════
#  _extract_access_token_from_session_store
# ═══════════════════════════════════════════════════════════


class TestExtractAccessToken:
    def test_active_entry_in_list(self):
        payload = [{"active": True, "accessToken": "token-123"}]
        token = NetSchool._extract_access_token_from_session_store(
            json.dumps(payload),
        )
        assert token == "token-123"

    def test_stringified_list(self):
        payload = [{"active": True, "accessToken": "token-456"}]
        token = NetSchool._extract_access_token_from_session_store(
            json.dumps(json.dumps(payload)),
        )
        assert token == "token-456"

    def test_dict_with_access_token(self):
        payload = {"accessToken": "tok-dict"}
        token = NetSchool._extract_access_token_from_session_store(
            json.dumps(payload),
        )
        assert token == "tok-dict"

    def test_dict_with_at(self):
        payload = {"at": "tok-at"}
        token = NetSchool._extract_access_token_from_session_store(
            json.dumps(payload),
        )
        assert token == "tok-at"

    def test_list_no_active_fallback(self):
        payload = [{"accessToken": "fallback-tok"}]
        token = NetSchool._extract_access_token_from_session_store(
            json.dumps(payload),
        )
        assert token == "fallback-tok"

    def test_invalid_json(self):
        assert NetSchool._extract_access_token_from_session_store("not json") is None

    def test_empty_list(self):
        assert NetSchool._extract_access_token_from_session_store("[]") is None

    def test_empty_dict(self):
        assert NetSchool._extract_access_token_from_session_store("{}") is None


# ═══════════════════════════════════════════════════════════
#  _parse_cookies
# ═══════════════════════════════════════════════════════════


class TestParseCookies:
    def test_full_cookie_string(self):
        result = NetSchool._parse_cookies(
            "NSSESSIONID=abc123; other=val",
        )
        assert result == {"NSSESSIONID": "abc123", "other": "val"}

    def test_hex_session_id(self):
        result = NetSchool._parse_cookies("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        assert result == {"NSSESSIONID": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"}

    def test_empty_string(self):
        assert NetSchool._parse_cookies("") == {}

    def test_no_nssessionid(self):
        assert NetSchool._parse_cookies("foo=bar; baz=qux") == {}

    def test_whitespace(self):
        result = NetSchool._parse_cookies("  NSSESSIONID=xyz  ; foo=bar  ")
        assert result["NSSESSIONID"] == "xyz"


# ═══════════════════════════════════════════════════════════
#  Exception hierarchy
# ═══════════════════════════════════════════════════════════


class TestExceptions:
    def test_login_error_is_netschool_error(self):
        assert issubclass(LoginError, NetSchoolError)

    def test_mfa_error_is_login_error(self):
        assert issubclass(MFAError, LoginError)

    def test_esia_error_is_login_error(self):
        assert issubclass(ESIAError, LoginError)

    def test_school_not_found_is_login_error(self):
        assert issubclass(SchoolNotFound, LoginError)

    def test_session_expired_is_netschool_error(self):
        assert issubclass(SessionExpired, NetSchoolError)

    def test_session_expired_not_login_error(self):
        """SessionExpired — отдельная ветка, не LoginError."""
        assert not issubclass(SessionExpired, LoginError)

    def test_catch_esia_as_login(self):
        """ESIAError должна ловиться как LoginError."""
        with pytest.raises(LoginError):
            raise ESIAError("test")

    def test_catch_mfa_as_login(self):
        """MFAError должна ловиться как LoginError."""
        with pytest.raises(LoginError):
            raise MFAError("test")


# ═══════════════════════════════════════════════════════════
#  NetSchool.__repr__
# ═══════════════════════════════════════════════════════════


class TestNetSchoolRepr:
    def test_repr_default(self):
        ns = NetSchool.__new__(NetSchool)
        ns._http = type("H", (), {"base_url": "https://sgo.example.ru/webapi"})()
        ns._student_id = -1
        r = repr(ns)
        assert "NetSchool" in r
        assert "sgo.example.ru" in r


# ═══════════════════════════════════════════════════════════
#  Session export
# ═══════════════════════════════════════════════════════════


class TestSessionExport:
    def test_export_session_json(self):
        """export_session() возвращает валидный JSON."""
        ns = NetSchool.__new__(NetSchool)
        ns._access_token = "tok123"
        ns._student_id = 42
        ns._year_id = 10
        ns._school_id = 5

        # Минимальный мок http client
        class FakeCookies:
            def __iter__(self):
                return iter({"NSSESSIONID": "abc"}.items())
            def items(self):
                return [("NSSESSIONID", "abc")]

        class FakeClient:
            cookies = FakeCookies()

        class FakeHttp:
            client = FakeClient()

        ns._http = FakeHttp()  # type: ignore[assignment]

        data = json.loads(ns.export_session())
        assert data["version"] == 1
        assert data["access_token"] == "tok123"
        assert data["student_id"] == 42


# ═══════════════════════════════════════════════════════════
#  search_schools — валидация аргументов
# ═══════════════════════════════════════════════════════════


class TestSearchSchoolsArgs:
    @pytest.mark.asyncio
    async def test_unknown_region_raises(self):
        """Несуществующий регион → ValueError."""
        with pytest.raises(ValueError, match="Не удалось определить URL"):
            await search_schools("Неизвестная область", "школа")

    @pytest.mark.asyncio
    async def test_url_passthrough(self):
        """URL начинающийся с http(s):// не проходит через get_url."""
        # Ожидаем ошибку подключения, но не ValueError —
        # значит URL был принят как есть.
        with pytest.raises(Exception) as exc_info:
            await search_schools("https://127.0.0.1:1", "школа", timeout=1)
        assert not isinstance(exc_info.value, ValueError)

# ═══════════════════════════════════════════════════════════
#  get_login_methods — валидация аргументов
# ═══════════════════════════════════════════════════════════


class TestGetLoginMethodsArgs:
    @pytest.mark.asyncio
    async def test_unknown_region_raises(self):
        """Несуществующий регион → ValueError."""
        with pytest.raises(ValueError, match="Не удалось определить URL"):
            await get_login_methods("Неизвестная область")

    @pytest.mark.asyncio
    async def test_url_passthrough(self):
        """УРЛ начинающийся с http(s):// не проходит через get_url."""
        with pytest.raises(Exception) as exc_info:
            await get_login_methods("https://127.0.0.1:1", timeout=1)
        assert not isinstance(exc_info.value, ValueError)


class TestGetTotalMarksHelper:
    @pytest.mark.asyncio
    async def test_get_total_marks_calls_login_and_total_marks(self, monkeypatch):
        called = {}

        def fake_init(self, url, *, timeout=None, proxy=None):
            called["init"] = (url, timeout, proxy)

        async def fake_login(self, user_name, password, school, *, timeout=None):
            called["login"] = (user_name, password, school, timeout)

        async def fake_total_marks(self, *, subject=None, timeout=None):
            called["total_marks"] = (subject, timeout)
            return ["ok"]

        async def fake_close(self, *, timeout=None):
            called["close"] = timeout

        monkeypatch.setattr(NetSchool, "__init__", fake_init)
        monkeypatch.setattr(NetSchool, "login", fake_login)
        monkeypatch.setattr(NetSchool, "total_marks", fake_total_marks)
        monkeypatch.setattr(NetSchool, "close", fake_close)

        result = await get_total_marks(
            "https://example.com",
            "user",
            "pass",
            1110,
            subject="Алгебра",
            timeout=7,
        )

        assert result == ["ok"]
        assert called["init"] == ("https://example.com", 7, None)
        assert called["login"] == ("user", "pass", 1110, 7)
        assert called["total_marks"] == ("Алгебра", 7)
        assert called["close"] == 7

    @pytest.mark.asyncio
    async def test_get_total_marks_ignores_close_error(self, monkeypatch):
        def fake_init(self, url, *, timeout=None, proxy=None):
            return None

        async def fake_login(self, user_name, password, school, *, timeout=None):
            return None

        async def fake_total_marks(self, *, subject=None, timeout=None):
            return ["ok"]

        async def fake_close(self, *, timeout=None):
            raise RuntimeError("close failed")

        monkeypatch.setattr(NetSchool, "__init__", fake_init)
        monkeypatch.setattr(NetSchool, "login", fake_login)
        monkeypatch.setattr(NetSchool, "total_marks", fake_total_marks)
        monkeypatch.setattr(NetSchool, "close", fake_close)

        result = await get_total_marks("https://example.com", "user", "pass", 1)
        assert result == ["ok"]


# ═══════════════════════════════════════════════════════════
#  total marks HTML parser
# ═══════════════════════════════════════════════════════════


class TestTotalMarksHtmlParser:
        def test_parse_total_marks_row(self):
                html = """
                <table>
                    <tr>
                        <th>№</th><th>Предмет</th><th>1 четверть</th><th>2 четверть</th>
                        <th>3 четверть</th><th>4 четверть</th><th>Год. оценка</th>
                        <th>Экз. оценка</th><th>Итог. оценка</th>
                    </tr>
                    <tr>
                        <td>1</td><td>Алгебра</td><td>4</td><td>4</td><td>5</td><td></td>
                        <td>5</td><td></td><td>5</td>
                    </tr>
                </table>
                """
                rows = NetSchool._parse_total_marks_report_html(html)
                assert len(rows) == 1
                row = rows[0]
                assert row.order == 1
                assert row.subject == "Алгебра"
                assert row.period_marks == ["4", "4", "5", None]
                assert row.year_mark == "5"
                assert row.exam_mark is None
                assert row.final_mark == "5"


class TestAssignedMarksHtmlParser:
        def test_parse_assigned_marks_rows(self):
                html = """
                <table>
                    <tr>
                        <th>Тип задания</th><th>Тема задания</th><th>Дата выполнения</th>
                        <th>Дата выставления оценки</th><th>Оценка</th>
                    </tr>
                    <tr>
                        <td>Самостоятельная работа</td><td>Тема 1</td><td>12.01.26</td><td>13.01.26</td><td>5</td>
                    </tr>
                    <tr>
                        <td>Ответ на уроке</td><td>Тема 2</td><td>20.01.26</td><td>20.01.26</td><td>УП</td>
                    </tr>
                </table>
                """
                rows = NetSchool._parse_assigned_marks_report_html(html, subject_label="Алгебра")
                assert len(rows) == 2

                numeric = rows[0]
                assert numeric.subject == "Алгебра"
                assert numeric.lesson_date == datetime.date(2026, 1, 12)
                assert numeric.mark_set_date == datetime.date(2026, 1, 13)
                assert numeric.mark_text == "5"
                assert numeric.numeric_mark == 5
                assert numeric.special_mark_code is None

                special = rows[1]
                assert special.mark_text == "УП"
                assert special.numeric_mark is None
                assert special.special_mark_code == "УП"
                assert special.special_mark_description == "Пропуск по уважительной причине"

# ═══════════════════════════════════════════════════════════
#  _init_students
# ═══════════════════════════════════════════════════════════


class TestInitStudents:
    def _make_ns(self) -> NetSchool:
        ns = NetSchool.__new__(NetSchool)
        ns._student_id = -1
        ns._students = []
        return ns

    def test_single_student(self):
        ns = self._make_ns()
        ns._init_students({
            "students": {
                0: {"studentId": 100, "nickName": "Иванов Иван"},
            },
            "currentStudentId": 0,
        })
        assert len(ns._students) == 1
        assert ns._student_id == 100
        assert ns._students[0].name == "Иванов Иван"

    def test_multiple_students(self):
        ns = self._make_ns()
        ns._init_students({
            "students": {
                0: {"studentId": 100, "nickName": "Иванов Иван"},
                1: {"studentId": 200, "nickName": "Иванова Мария"},
            },
            "currentStudentId": 0,
        })
        assert len(ns._students) == 2
        assert ns._student_id == 100
        assert ns._students[1].name == "Иванова Мария"

    def test_current_student_id_picks_correct(self):
        ns = self._make_ns()
        ns._init_students({
            "students": {
                0: {"studentId": 100, "nickName": "Первый"},
                1: {"studentId": 200, "nickName": "Второй"},
            },
            "currentStudentId": 1,
        })
        assert ns._student_id == 200

    def test_empty_students(self):
        ns = self._make_ns()
        ns._init_students({"students": {}, "currentStudentId": None})
        assert ns._students == []
        assert ns._student_id == -1


# ═══════════════════════════════════════════════════════════
#  _pick_parent_role
# ═══════════════════════════════════════════════════════════


class TestPickParentRole:
    def test_parent_auto_selected(self):
        roles = [
            {"id": 1, "name": "Сотрудник"},
            {"id": 2, "name": "Родитель"},
        ]
        assert NetSchool._pick_parent_role(roles) == 2

    def test_parent_english(self):
        roles = [
            {"id": 10, "name": "Employee"},
            {"id": 20, "name": "Parent"},
        ]
        assert NetSchool._pick_parent_role(roles) == 20

    def test_single_role_fallback(self):
        roles = [{"id": 5, "name": "Ученик"}]
        assert NetSchool._pick_parent_role(roles) == 5

    def test_empty_roles(self):
        assert NetSchool._pick_parent_role([]) is None

    def test_no_parent_uses_first(self):
        roles = [
            {"id": 1, "name": "Сотрудник"},
            {"id": 3, "name": "Администратор"},
        ]
        assert NetSchool._pick_parent_role(roles) == 1


# ═══════════════════════════════════════════════════════════
#  switch_student
# ═══════════════════════════════════════════════════════════


class TestSwitchStudent:
    def _make_ns(self) -> NetSchool:
        ns = NetSchool.__new__(NetSchool)
        ns._student_id = -1
        ns._students = []
        return ns

    @pytest.mark.asyncio
    async def test_switch_by_index(self):
        ns = self._make_ns()
        ns._init_students({
            "students": {
                0: {"studentId": 100, "nickName": "Иванов"},
                1: {"studentId": 200, "nickName": "Иванова"},
            },
            "currentStudentId": 0,
        })
        result = await ns.switch_student(1)
        assert result.id == 200
        assert ns._student_id == 200

    @pytest.mark.asyncio
    async def test_switch_by_id(self):
        ns = self._make_ns()
        ns._init_students({
            "students": {
                0: {"studentId": 100, "nickName": "Иванов"},
                1: {"studentId": 200, "nickName": "Иванова"},
            },
            "currentStudentId": 0,
        })
        result = await ns.switch_student(100)
        assert result.id == 100

    @pytest.mark.asyncio
    async def test_switch_invalid_raises(self):
        ns = self._make_ns()
        ns._init_students({
            "students": {
                0: {"studentId": 100, "nickName": "Один"},
            },
            "currentStudentId": 0,
        })
        with pytest.raises(ValueError, match="не найден"):
            await ns.switch_student(999)

    def test_students_property(self):
        ns = self._make_ns()
        ns._init_students({
            "students": {
                0: {"studentId": 100, "nickName": "А"},
                1: {"studentId": 200, "nickName": "Б"},
            },
            "currentStudentId": 0,
        })
        students = ns.students
        assert len(students) == 2
        # Возвращает копию
        students.clear()
        assert len(ns.students) == 2

    def test_current_student_property(self):
        ns = self._make_ns()
        ns._init_students({
            "students": {
                0: {"studentId": 100, "nickName": "А"},
                1: {"studentId": 200, "nickName": "Б"},
            },
            "currentStudentId": 1,
        })
        current = ns.current_student
        assert current is not None
        assert current.id == 200
        assert current.name == "Б"
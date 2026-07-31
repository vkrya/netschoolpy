"""Асинхронный клиент «Сетевого города»."""

from __future__ import annotations

import asyncio
import json
import re
import ssl as _ssl
from datetime import date, timedelta
from hashlib import md5
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

import httpx

from netschoolpy import exceptions
from netschoolpy.http import HttpSession
from netschoolpy.models import (
    Announcement,
    Assignment,
    Attachment,
    Diary,
    MailEntry,
    MailPage,
    MailRecipient,
    Message,
    School,
    ShortSchool,
)

__all__ = ["NetSchool"]


class NetSchool:
    """Асинхронный клиент для API «Сетевого города».

    Пример::

        async with NetSchool("https://sgo.example.ru") as ns:
            await ns.login("user", "pass", "Школа №1")
            diary = await ns.diary()
    """

    def __init__(self, url: str, *, timeout: int | None = None):
        self._http = HttpSession(url, timeout=timeout)

        self._student_id: int = -1
        self._year_id: int = -1
        self._school_id: int = -1

        self._assignment_types: Dict[int, dict] = {}
        self._credentials: tuple = ()
        self._access_token: Optional[str] = None

        self._keepalive_task: Optional[asyncio.Task] = None
        self._keepalive_interval: int = 300  # 5 мин

    # ── контекстный менеджер ─────────────────────────────────

    async def __aenter__(self) -> NetSchool:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ═══════════════════════════════════════════════════════════
    #  Авторизация по логину/паролю SGO
    # ═══════════════════════════════════════════════════════════

    async def login(
        self,
        user_name: str,
        password: str,
        school: Union[int, str],
        *,
        timeout: int | None = None,
    ) -> None:
        """Вход по логину/паролю «Сетевого города»."""

        # Получаем cookie NSSESSIONID
        await self._http.get("logindata", timeout=timeout)

        # Получаем salt для хеширования
        resp = await self._http.post("auth/getdata", timeout=timeout)
        meta = resp.json()
        salt = meta.pop("salt")

        pw_hash = md5(password.encode("windows-1251")).hexdigest().encode()
        pw2 = md5(salt.encode() + pw_hash).hexdigest()
        pw = pw2[: len(password)]

        school_id = (
            await self._resolve_school(school, timeout=timeout)
            if isinstance(school, str)
            else school
        )
        self._school_id = school_id

        try:
            resp = await self._http.post(
                "login",
                data={
                    "loginType": 1,
                    "scid": school_id,
                    "un": user_name,
                    "pw": pw,
                    "pw2": pw2,
                    **meta,
                },
                timeout=timeout,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.CONFLICT:
                try:
                    body = exc.response.json()
                except Exception:
                    raise exceptions.LoginError() from None
                raise exceptions.LoginError(
                    body.get("message", "Ошибка авторизации")
                ) from None
            raise

        result = resp.json()
        if "at" not in result:
            raise exceptions.LoginError(result.get("message", "Нет токена"))

        self._access_token = result["at"]
        self._http.set_header("at", result["at"])

        # diary/init → student
        resp = await self._http.get("student/diary/init", timeout=timeout)
        info = resp.json()
        student = info["students"][info["currentStudentId"]]
        self._student_id = student["studentId"]

        # year
        resp = await self._http.get("years/current", timeout=timeout)
        self._year_id = resp.json()["id"]

        # assignment types (name + abbreviation)
        resp = await self._http.get(
            "grade/assignment/types", params={"all": False}, timeout=timeout,
        )
        self._assignment_types = {
            a["id"]: {"name": a["name"], "abbr": a.get("abbr", "")}
            for a in resp.json()
        }

        self._credentials = (user_name, password, school)
        self._start_keepalive()

    # ═══════════════════════════════════════════════════════════
    #  Госуслуги: общий URL
    # ═══════════════════════════════════════════════════════════

    async def get_gosuslugi_auth_url(self) -> str:
        """Возвращает ссылку для входа через Госуслуги (crosslogin)."""
        base = self._http.base_url.rstrip("/")
        return f"{base}/sso/esia/crosslogin"

    # ═══════════════════════════════════════════════════════════
    #  Госуслуги: логин + пароль ЕСИА
    # ═══════════════════════════════════════════════════════════

    async def login_via_gosuslugi(
        self,
        esia_login: str | None = None,
        esia_password: str | None = None,
        *,
        timeout: int | None = None,
    ) -> None:
        """Полноценный вход через Госуслуги (ESIA).

        Программно проходит всю OAuth2-цепочку:
          SGO crosslogin → esiasgo → esia.gosuslugi.ru →
          вводим логин/пароль → (MFA если нужно) →
          callback → SGO IDP login → сессия.

        :param esia_login: Логин Госуслуг (телефон, email или СНИЛС).
                           Если не указан — спросит через input().
        :param esia_password: Пароль Госуслуг.
                              Если не указан — спросит через input().
        """
        if esia_login is None:
            esia_login = input("Логин Госуслуг (телефон/email/СНИЛС): ").strip()
        if esia_password is None:
            import getpass
            esia_password = getpass.getpass("Пароль Госуслуг: ").strip()

        if not esia_login or not esia_password:
            raise exceptions.LoginError("Логин и пароль не могут быть пустыми")

        base_url = self._http.base_url.rstrip("/")
        sgo_origin = base_url.rsplit("/webapi", 1)[0]

        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except _ssl.SSLError:
            # Некоторые сборки OpenSSL не поддерживают указанный набор шифров.
            # В этом случае продолжаем с настройками по умолчанию.
            pass
        ctx.options |= _ssl.OP_NO_TLSv1_3

        async with httpx.AsyncClient(
            headers={
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            },
            follow_redirects=False,
            verify=ctx,
            timeout=timeout or 30,
        ) as esia_client:
            from urllib.parse import urljoin

            # === ШАГ 1: Инициировать OAuth2 цепочку ===
            await esia_client.get(f"{sgo_origin}/webapi/logindata")

            url = f"{sgo_origin}/webapi/sso/esia/crosslogin"
            for _ in range(20):
                r = await esia_client.get(url)
                for h in r.headers.get_list("set-cookie"):
                    p = h.split(";")[0].split("=", 1)
                    if len(p) == 2:
                        esia_client.cookies.set(p[0].strip(), p[1].strip())
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("location", "")
                    if not loc.startswith("http"):
                        loc = urljoin(str(r.url), loc)
                    url = loc
                else:
                    break

            if "esia.gosuslugi.ru" not in url:
                raise exceptions.LoginError(
                    f"Не удалось добраться до страницы ESIA. "
                    f"Финальный URL: {url}"
                )

            # === ШАГ 2: Отправить логин/пароль в ESIA API ===
            esia_headers = {
                "content-type": "application/json",
                "origin": "https://esia.gosuslugi.ru",
                "referer": "https://esia.gosuslugi.ru/login/",
            }
            login_resp = await esia_client.post(
                "https://esia.gosuslugi.ru/aas/oauth2/api/login",
                json={"login": esia_login, "password": esia_password},
                headers=esia_headers,
            )

            login_data = login_resp.json()

            if "failed" in login_data:
                error_code = login_data["failed"]
                error_messages = {
                    "INVALID_PASSWORD": "Неверный пароль",
                    "INVALID_LOGIN": "Неверный логин",
                    "ACCOUNT_LOCKED": "Аккаунт заблокирован",
                    "ACCOUNT_NOT_FOUND": "Аккаунт не найден",
                    "CAPTCHA_REQUIRED": (
                        "Требуется captcha (слишком много попыток)"
                    ),
                }
                msg = error_messages.get(error_code, error_code)
                raise exceptions.LoginError(f"Ошибка ESIA: {msg}")

            # === ШАГ 3: Обработка ответа ESIA ===
            redirect_url = login_data.get("redirect_url")
            if not redirect_url:
                # возможные варианты ключей
                redirect_url = (
                    login_data.get("redirectUrl")
                    or login_data.get("redirectURL")
                    or login_data.get("url")
                    or login_data.get("redirect")
                )
            if not redirect_url and isinstance(login_data.get("data"), dict):
                redirect_url = (
                    login_data["data"].get("redirect_url")
                    or login_data["data"].get("redirectUrl")
                    or login_data["data"].get("redirectURL")
                    or login_data["data"].get("url")
                )
            action = login_data.get("action", "")

            if redirect_url:
                pass
            elif action == "ENTER_MFA":
                redirect_url = await self._handle_esia_mfa(
                    esia_client, login_data,
                )
            elif action == "DONE":
                redirect_url = login_data.get("redirect_url")
            elif action in ("MAX_QUIZ", "CHANGE_PASSWORD"):
                redirect_url = await self._handle_esia_post_mfa(
                    esia_client, login_data,
                )
            else:
                raise exceptions.LoginError(
                    f"Неожиданный ответ ESIA: "
                    f"{json.dumps(login_data, ensure_ascii=False)}"
                )

            if not redirect_url:
                raise exceptions.LoginError(
                    "Не удалось получить redirect_url от ESIA"
                )

            # === ШАГ 4: Следуем по callback chain обратно в SGO ===
            login_state = None
            url = redirect_url
            for _ in range(15):
                r = await esia_client.get(url)
                for h in r.headers.get_list("set-cookie"):
                    p = h.split(";")[0].split("=", 1)
                    if len(p) == 2:
                        esia_client.cookies.set(p[0].strip(), p[1].strip())
                m = re.search(
                    r"loginState=([a-f0-9-]+)",
                    str(r.url) + r.headers.get("location", ""),
                )
                if m:
                    login_state = m.group(1)
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("location", "")
                    if not loc.startswith("http"):
                        loc = urljoin(str(r.url), loc)
                    url = loc
                else:
                    break

            if not login_state:
                raise exceptions.LoginError(
                    "Не удалось получить loginState из callback"
                )

            # === ШАГ 5: Получить информацию об аккаунте ===
            await esia_client.get(f"{sgo_origin}/webapi/logindata")

            r = await esia_client.get(
                f"{sgo_origin}/webapi/sso/esia/account-info",
                params={"loginState": login_state},
            )
            if r.status_code != 200:
                raise exceptions.LoginError(
                    f"Не удалось получить account-info: "
                    f"{r.status_code} {r.text[:200]}"
                )

            account_info = r.json()
            users = account_info.get("users", [])
            if not users:
                raise exceptions.LoginError(
                    "Нет привязанных пользователей SGO. "
                    "Привяжите аккаунт Госуслуг к Сетевому Городу."
                )

            user = users[0]
            user_id = user["id"]
            roles = user.get("roles", [])
            role = roles[0]["id"] if roles else None

            # === ШАГ 6: IDP-логин в SGO ===
            auth_params: dict[str, Any] = {
                "loginType": 8,
                "lscope": user_id,
                "idp": "esia",
                "loginState": login_state,
            }
            if role is not None:
                auth_params["rolegroup"] = role

            r = await esia_client.post(
                f"{sgo_origin}/webapi/auth/login",
                data=auth_params,
                headers={
                    "Content-Type":
                        "application/x-www-form-urlencoded; charset=UTF-8",
                },
            )
            if r.status_code != 200:
                raise exceptions.LoginError(
                    f"IDP-логин в SGO не удался: "
                    f"{r.status_code} {r.text[:300]}"
                )

            auth_result = r.json()
            at = auth_result.get("at", "")
            if not at:
                raise exceptions.LoginError("SGO не вернул access token (at)")

            # === ШАГ 7: Перенести сессию в основной клиент ===
            self._access_token = at
            self._http.set_header("at", at)

            for cookie in esia_client.cookies.jar:
                if "sgo" in (cookie.domain or "") or not cookie.domain:
                    self._http.set_cookie(cookie.name, cookie.value)

        # === ШАГ 8: Инициализировать сессию SGO ===
        resp = await self._http.get("student/diary/init", timeout=timeout)
        info = resp.json()
        student = info["students"][info["currentStudentId"]]
        self._student_id = student["studentId"]

        await self._finish_login(timeout=timeout)
        self._credentials = ()
        self._start_keepalive()

    # ═══════════════════════════════════════════════════════════
    #  Госуслуги: QR-код
    # ═══════════════════════════════════════════════════════════

    async def login_via_gosuslugi_qr(
        self,
        qr_callback=None,
        qr_timeout: int = 120,
        *,
        timeout: int | None = None,
    ) -> str:
        """Вход через Госуслуги по QR-коду.

        Генерирует QR-код, передаёт deep-link строку
        ``gosuslugi://auth/signed_token=...`` в *qr_callback*
        (или печатает в терминал), а затем ожидает сканирования
        в мобильном приложении «Госуслуги».

        :param qr_callback: ``async def(qr_data: str)`` — колбэк,
            который будет вызван сразу после генерации QR-кода.
            В ``qr_data`` передаётся строка для кодирования в QR
            (deep-link ``gosuslugi://auth/signed_token=...``).
            Если ``None`` — QR печатается в stdout.
        :param qr_timeout: Таймаут ожидания сканирования (сек, по-умолчанию 120).
        :return: signed_token (строка для QR-кода).

        Пример::

            async with NetSchool("https://sgo.example.ru") as ns:
                async def show_qr(qr_data: str):
                    import qrcode
                    qrcode.make(qr_data).save("qr.png")
                    print("QR сохранён в qr.png, отсканируйте!")

                await ns.login_via_gosuslugi_qr(qr_callback=show_qr)
        """
        base_url = self._http.base_url.rstrip("/")
        sgo_origin = base_url.rsplit("/webapi", 1)[0]

        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except _ssl.SSLError:
            # Некоторые сборки OpenSSL не поддерживают указанный набор шифров.
            # В этом случае продолжаем с настройками по умолчанию.
            pass
        ctx.options |= _ssl.OP_NO_TLSv1_3

        async with httpx.AsyncClient(
            headers={
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            },
            follow_redirects=False,
            verify=ctx,
            timeout=timeout or 30,
        ) as esia_client:
            from urllib.parse import urljoin

            # === ШАГ 1: Инициировать OAuth2 цепочку (crosslogin) ===
            await esia_client.get(f"{sgo_origin}/webapi/logindata")

            url = f"{sgo_origin}/webapi/sso/esia/crosslogin"
            for _ in range(20):
                r = await esia_client.get(url)
                for h in r.headers.get_list("set-cookie"):
                    p = h.split(";")[0].split("=", 1)
                    if len(p) == 2:
                        esia_client.cookies.set(p[0].strip(), p[1].strip())
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("location", "")
                    if not loc.startswith("http"):
                        loc = urljoin(str(r.url), loc)
                    url = loc
                else:
                    break

            if "esia.gosuslugi.ru" not in url:
                raise exceptions.LoginError(
                    f"Не удалось добраться до страницы ESIA. "
                    f"Финальный URL: {url}"
                )

            # Получаем ESIA_SESSION из cookies
            esia_session = None
            for cookie in esia_client.cookies.jar:
                if cookie.name == "ESIA_SESSION":
                    esia_session = cookie.value
                    break

            # === ШАГ 2–3: Сгенерировать QR и ждать сканирования (с retry) ===
            esia_headers = {
                "content-type": "application/json",
                "origin": "https://esia.gosuslugi.ru",
                "referer": "https://esia.gosuslugi.ru/login/",
            }

            max_qr_retries = 5
            login_data: dict = {}
            signed_token = ""

            for qr_attempt in range(1, max_qr_retries + 1):
                if qr_attempt > 1:
                    # Переинициализировать crosslogin (ESIA_SESSION протухает после ошибки SSE)
                    esia_client.cookies.clear()
                    await esia_client.get(f"{sgo_origin}/webapi/logindata")
                    url = f"{sgo_origin}/webapi/sso/esia/crosslogin"
                    for _ in range(20):
                        r = await esia_client.get(url)
                        for h in r.headers.get_list("set-cookie"):
                            p = h.split(";")[0].split("=", 1)
                            if len(p) == 2:
                                esia_client.cookies.set(p[0].strip(), p[1].strip())
                        if r.status_code in (301, 302, 303, 307, 308):
                            loc = r.headers.get("location", "")
                            if not loc.startswith("http"):
                                loc = urljoin(str(r.url), loc)
                            url = loc
                        else:
                            break
                    esia_session = None
                    for cookie in esia_client.cookies.jar:
                        if cookie.name == "ESIA_SESSION":
                            esia_session = cookie.value
                            break

                body = None
                if esia_session:
                    body = {"esia_session": esia_session}

                qr_resp = await esia_client.post(
                    "https://esia.gosuslugi.ru/qr-delegate/qr/generate",
                    json=body,
                    headers=esia_headers,
                )
                if qr_resp.status_code != 200:
                    raise exceptions.LoginError(
                        f"Не удалось сгенерировать QR-код: "
                        f"{qr_resp.status_code} {qr_resp.text[:300]}"
                    )

                qr_data = qr_resp.json()
                signed_token = qr_data.get("signed_token", "")
                qr_id = qr_data.get("qr_id", "")
                if not signed_token or not qr_id:
                    raise exceptions.LoginError(
                        f"ESIA не вернула QR данные: {qr_data}"
                    )

                # Deep-link для мобильного приложения «Госуслуги»
                qr_content = f"gosuslugi://auth/signed_token={signed_token}"

                # Показываем QR пользователю ДО ожидания сканирования
                if qr_callback is not None:
                    if asyncio.iscoroutinefunction(qr_callback):
                        await qr_callback(qr_content)
                    else:
                        qr_callback(qr_content)
                else:
                    try:
                        import qrcode as _qr
                        q = _qr.QRCode(error_correction=_qr.constants.ERROR_CORRECT_L)
                        q.add_data(qr_content)
                        q.make(fit=True)
                        print("\n📱 Отсканируйте QR-код в приложении «Госуслуги»:")
                        q.print_ascii(invert=True)
                    except ImportError:
                        print(
                            f"\n📱 Отсканируйте QR-код в приложении «Госуслуги».\n"
                            f"   Содержимое для QR: {qr_content[:80]}...\n"
                        )

                # Подписаться на SSE и ждать сканирования
                sse_url = (
                    f"https://esia.gosuslugi.ru"
                    f"/qr-delegate/qr/subscribe/{qr_id}"
                )

                try:
                    login_data = await self._poll_esia_qr_sse(
                        esia_client, sse_url, qr_timeout,
                    )
                    break  # Успешно получили данные
                except exceptions.LoginError as e:
                    if "ESIA-007110" in str(e) and qr_attempt < max_qr_retries:
                        delay = qr_attempt * 2  # 2, 4, 6, 8 сек
                        print(
                            f"\n⚠️  ESIA вернула ошибку 007110, "
                            f"повтор {qr_attempt}/{max_qr_retries} "
                            f"через {delay}с..."
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise

            redirect_url = login_data.get("redirect_url")
            action = login_data.get("action", "")

            if redirect_url:
                pass
            elif action == "ENTER_MFA":
                redirect_url = await self._handle_esia_mfa(
                    esia_client, login_data,
                )
            elif action == "DONE":
                redirect_url = login_data.get("redirect_url")
            elif action in ("MAX_QUIZ", "CHANGE_PASSWORD"):
                redirect_url = await self._handle_esia_post_mfa(
                    esia_client, login_data,
                )

            if not redirect_url:
                raise exceptions.LoginError(
                    f"Не удалось получить redirect_url после QR: {login_data}"
                )

            # === ШАГ 4: Callback chain → loginState ===
            login_state = None
            url = redirect_url
            for _ in range(15):
                r = await esia_client.get(url)
                for h in r.headers.get_list("set-cookie"):
                    p = h.split(";")[0].split("=", 1)
                    if len(p) == 2:
                        esia_client.cookies.set(p[0].strip(), p[1].strip())
                m = re.search(
                    r"loginState=([a-f0-9-]+)",
                    str(r.url) + r.headers.get("location", ""),
                )
                if m:
                    login_state = m.group(1)
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("location", "")
                    if not loc.startswith("http"):
                        loc = urljoin(str(r.url), loc)
                    url = loc
                else:
                    break

            if not login_state:
                raise exceptions.LoginError(
                    "Не удалось получить loginState из callback"
                )

            # === ШАГ 5: Получить информацию об аккаунте ===
            await esia_client.get(f"{sgo_origin}/webapi/logindata")

            r = await esia_client.get(
                f"{sgo_origin}/webapi/sso/esia/account-info",
                params={"loginState": login_state},
            )
            if r.status_code != 200:
                raise exceptions.LoginError(
                    f"Не удалось получить account-info: "
                    f"{r.status_code} {r.text[:200]}"
                )

            account_info = r.json()
            users = account_info.get("users", [])
            if not users:
                raise exceptions.LoginError(
                    "Нет привязанных пользователей SGO. "
                    "Привяжите аккаунт Госуслуг к Сетевому Городу."
                )

            user = users[0]
            user_id = user["id"]
            roles = user.get("roles", [])
            role = roles[0]["id"] if roles else None

            # === ШАГ 6: IDP-логин в SGO ===
            auth_params: dict[str, Any] = {
                "loginType": 8,
                "lscope": user_id,
                "idp": "esia",
                "loginState": login_state,
            }
            if role is not None:
                auth_params["rolegroup"] = role

            r = await esia_client.post(
                f"{sgo_origin}/webapi/auth/login",
                data=auth_params,
                headers={
                    "Content-Type":
                        "application/x-www-form-urlencoded; charset=UTF-8",
                },
            )
            if r.status_code != 200:
                raise exceptions.LoginError(
                    f"IDP-логин в SGO не удался: "
                    f"{r.status_code} {r.text[:300]}"
                )

            auth_result = r.json()
            at = auth_result.get("at", "")
            if not at:
                raise exceptions.LoginError("SGO не вернул access token (at)")

            # === ШАГ 7: Перенести сессию в основной клиент ===
            self._access_token = at
            self._http.set_header("at", at)

            for cookie in esia_client.cookies.jar:
                if "sgo" in (cookie.domain or "") or not cookie.domain:
                    self._http.set_cookie(cookie.name, cookie.value)

        # === ШАГ 8: Инициализировать сессию SGO ===
        resp = await self._http.get("student/diary/init", timeout=timeout)
        info = resp.json()
        student = info["students"][info["currentStudentId"]]
        self._student_id = student["studentId"]

        await self._finish_login(timeout=timeout)
        self._credentials = ()
        self._start_keepalive()

        return signed_token

    # ── SSE-поллинг QR ───────────────────────────────────────

    @staticmethod
    async def _poll_esia_qr_sse(
        esia_client: httpx.AsyncClient,
        sse_url: str,
        timeout: int = 120,
    ) -> dict:
        """Подключается к SSE-потоку ESIA QR и ждёт события сканирования.

        ESIA SSE не отправляет HTTP-заголовки до первого события,
        поэтому httpx stream / aiohttp зависают.
        Используем raw asyncio SSL-сокет.
        """
        from urllib.parse import urlparse

        parsed = urlparse(sse_url)
        host = parsed.hostname
        path = parsed.path

        cookie_parts = []
        for cookie in esia_client.cookies.jar:
            domain = cookie.domain or ""
            if "esia" in domain or "gosuslugi" in domain or not domain:
                cookie_parts.append(f"{cookie.name}={cookie.value}")
        cookie_header = "; ".join(cookie_parts)

        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE

        reader, writer = await asyncio.open_connection(host, 443, ssl=ctx)

        try:
            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Accept: text/event-stream\r\n"
                f"Cache-Control: no-cache\r\n"
                f"User-Agent: Mozilla/5.0\r\n"
                f"Cookie: {cookie_header}\r\n"
                f"Connection: keep-alive\r\n"
                f"\r\n"
            )
            writer.write(request.encode())
            await writer.drain()

            buffer = b""
            while True:
                chunk = await asyncio.wait_for(
                    reader.read(8192), timeout=timeout,
                )
                if not chunk:
                    raise exceptions.LoginError(
                        "SSE соединение закрыто сервером"
                    )
                buffer += chunk

                # Обрабатываем только завершённые строки (до \n).
                # Незавершённый хвост остаётся в buffer на следующий цикл.
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace").strip()

                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if not data_str:
                        continue

                    try:
                        data = json.loads(data_str)
                    except (json.JSONDecodeError, ValueError):
                        # Неполный или невалидный JSON — пропускаем
                        continue

                    error = data.get("error", {})
                    code = (
                        error.get("code", "")
                        if isinstance(error, dict)
                        else ""
                    )
                    if code in (
                        "QR_AUTHORIZATION_SESSION_EXPIRED",
                        "QR_CODE_SESSION_NOT_FOUND",
                        "QR_CODE_SESSION_OUTDATED",
                    ):
                        raise exceptions.LoginError(
                            f"QR сессия истекла: {code}"
                        )
                    if code:
                        msg = (
                            error.get("message", "")
                            if isinstance(error, dict)
                            else ""
                        )
                        raise exceptions.LoginError(
                            f"Ошибка ESIA при QR-входе: {code} — {msg}"
                        )
                    return data

        except asyncio.TimeoutError:
            raise exceptions.LoginError(
                "Таймаут ожидания QR сканирования"
            )
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ── MFA-обработка ────────────────────────────────────────

    async def _handle_esia_mfa(
        self,
        esia_client: httpx.AsyncClient,
        login_data: dict,
    ) -> Optional[str]:
        """Обработка двухфакторной аутентификации ESIA.

        Поддерживает SMS, TOTP (приложение-аутентификатор) и PUSH (Госключ).
        """
        mfa_details = login_data.get("mfa_details", {})
        mfa_type = mfa_details.get("type", "UNKNOWN")
        otp_details = mfa_details.get("otp_details", {})

        esia_headers = {
            "content-type": "application/json",
            "origin": "https://esia.gosuslugi.ru",
            "referer": "https://esia.gosuslugi.ru/login/",
        }
        base = "https://esia.gosuslugi.ru/aas/oauth2/api/login"

        if mfa_type in ("SMS", "TOTP"):
            if mfa_type == "SMS":
                phone = otp_details.get("phone", "***")
                code_len = otp_details.get("code_length", 6)
                ttl = otp_details.get("verify_timeout_secs", 300)
                attempts = otp_details.get("verify_attempts_left", 3)
                print(f"\nSMS-код отправлен на {phone}")
                print(f"({code_len} цифр, действует {ttl}с, попыток: {attempts})")
                prompt = "Введите код из SMS: "
            else:
                prompt = "Введите код из приложения-аутентификатора: "

            code = input(prompt).strip()
            if not code:
                raise exceptions.LoginError("Код подтверждения не введён")

            resp = await esia_client.post(
                f"{base}/otp/verify?code={code}",
                headers=esia_headers,
            )
            if resp.status_code not in (200, 202):
                try:
                    err = resp.json()
                    raise exceptions.LoginError(
                        f"Ошибка подтверждения: "
                        f"{err.get('message', err.get('error', resp.text))}"
                    )
                except (ValueError, KeyError):
                    raise exceptions.LoginError(
                        f"Ошибка подтверждения (HTTP {resp.status_code})"
                    )
            try:
                data = resp.json()
            except ValueError:
                data = {}

        elif mfa_type == "PUSH":
            print("\nПодтвердите вход в приложении Госключ...")
            data = await self._poll_esia_push(esia_client, login_data)
            if isinstance(data, str):
                return data

        else:
            raise exceptions.LoginError(f"Неизвестный тип MFA: {mfa_type}")

        if data.get("redirect_url"):
            return data["redirect_url"]

        return await self._handle_esia_post_mfa(esia_client, data)

    async def _handle_esia_post_mfa(
        self,
        esia_client: httpx.AsyncClient,
        data: dict,
    ) -> str:
        """Обработка шагов после MFA (MAX_QUIZ, смена пароля и т.д.)."""
        esia_headers = {
            "content-type": "application/json",
            "origin": "https://esia.gosuslugi.ru",
            "referer": "https://esia.gosuslugi.ru/login/",
        }
        base = "https://esia.gosuslugi.ru/aas/oauth2/api/login"

        if not data or not data.get("action"):
            resp = await esia_client.get(f"{base}/next-step", headers=esia_headers)
            data = resp.json()

        action = data.get("action", "")

        for _ in range(10):
            if action == "DONE":
                redirect_url = data.get("redirect_url")
                if redirect_url:
                    return redirect_url
                raise exceptions.LoginError("ESIA вернула DONE без redirect_url")

            elif action == "MAX_QUIZ":
                max_details = data.get("max_details", {})
                if not max_details.get("skippable", False):
                    raise exceptions.LoginError(
                        "ESIA требует настройку Госключа (MAX_QUIZ), "
                        "но пропуск недоступен. Настройте Госключ в "
                        "личном кабинете Госуслуг."
                    )
                resp = await esia_client.post(
                    f"{base}/quiz-max/skip", json={}, headers=esia_headers,
                )
                if resp.status_code != 200:
                    raise exceptions.LoginError(
                        f"Не удалось пропустить MAX_QUIZ (HTTP {resp.status_code})"
                    )
                data = resp.json()
                action = data.get("action", "")
                continue

            elif action == "CHANGE_PASSWORD":
                resp = await esia_client.post(
                    f"{base}/change-password/skip", json={}, headers=esia_headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    action = data.get("action", "")
                    continue
                resp = await esia_client.get(f"{base}/next-step", headers=esia_headers)
                data = resp.json()
                action = data.get("action", "")
                continue

            else:
                resp = await esia_client.get(f"{base}/next-step", headers=esia_headers)
                new_data = resp.json()
                new_action = new_data.get("action", "")
                if new_action == action:
                    raise exceptions.LoginError(
                        f"Неизвестный шаг ESIA: {action}. "
                        f"Данные: {json.dumps(data, ensure_ascii=False)}"
                    )
                data = new_data
                action = new_action
                continue

        raise exceptions.LoginError(
            "Слишком много шагов ESIA, возможно зацикливание"
        )

    async def _poll_esia_push(
        self,
        esia_client: httpx.AsyncClient,
        login_data: dict,
        max_wait: int = 120,
    ) -> Optional[str]:
        """Поллинг статуса push-подтверждения."""
        challenge_id = login_data.get("challenge_id", "")
        state = login_data.get("state", "")
        poll_url = "https://esia.gosuslugi.ru/aas/oauth2/api/login/poll"

        for _ in range(max_wait // 3):
            await asyncio.sleep(3)
            try:
                resp = await esia_client.post(
                    poll_url,
                    json={"challenge_id": challenge_id, "state": state},
                    headers={
                        "content-type": "application/json",
                        "origin": "https://esia.gosuslugi.ru",
                        "referer": "https://esia.gosuslugi.ru/login/",
                    },
                )
                data = resp.json()
                if "redirect_url" in data:
                    return data["redirect_url"]
                if "failed" in data:
                    raise exceptions.LoginError(
                        f"Push-подтверждение отклонено: {data['failed']}"
                    )
            except exceptions.LoginError:
                raise
            except Exception:
                continue

        raise exceptions.LoginError("Время ожидания push-подтверждения истекло")

    # ═══════════════════════════════════════════════════════════
    #  Keep-alive
    # ═══════════════════════════════════════════════════════════

    def _start_keepalive(self) -> None:
        """Запускает фоновый keep-alive (если ещё не запущен)."""
        self._stop_keepalive()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._keepalive_task = loop.create_task(
            self._keepalive_loop(), name="netschoolpy-keepalive",
        )

    def _stop_keepalive(self) -> None:
        """Останавливает фоновый keep-alive."""
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            self._keepalive_task = None

    async def _keepalive_loop(self) -> None:
        """Пингует ``GET /context`` раз в ``_keepalive_interval`` секунд."""
        while True:
            await asyncio.sleep(self._keepalive_interval)
            try:
                await self._http.get("context")
            except Exception:
                pass

    def set_keepalive_interval(self, seconds: int) -> None:
        """Установить интервал keep-alive. ``0`` — отключить."""
        self._keepalive_interval = seconds
        if seconds <= 0:
            self._stop_keepalive()
        elif self._access_token:
            self._start_keepalive()

    # ═══════════════════════════════════════════════════════════
    #  Вспомогательные способы входа
    # ═══════════════════════════════════════════════════════════

    async def _finish_login(self, *, timeout: int | None = None) -> None:
        """Загрузка данных после успешной авторизации (год, типы заданий)."""
        resp = await self._http.get("years/current", timeout=timeout)
        self._year_id = resp.json()["id"]

        # Если school_id ещё не установлен (ESIA/QR/token-вход),
        # получаем его из /context
        if self._school_id <= 0:
            try:
                ctx_resp = await self._http.get("context", timeout=timeout)
                self._school_id = ctx_resp.json().get("schoolId", -1)
            except Exception:
                pass

        resp = await self._http.get(
            "grade/assignment/types", params={"all": False}, timeout=timeout,
        )
        self._assignment_types = {
            a["id"]: {"name": a["name"], "abbr": a.get("abbr", "")}
            for a in resp.json()
        }

    async def login_with_token(
        self,
        token: str,
        school: Optional[Union[int, str]] = None,
        *,
        timeout: int | None = None,
    ) -> None:
        """Логин с использованием токена доступа (accessToken из localStorage)."""
        self._access_token = token
        self._http.set_header("at", token)

        resp = await self._http.get("student/diary/init", timeout=timeout)
        info = resp.json()
        student = info["students"][info["currentStudentId"]]
        self._student_id = student["studentId"]

        await self._finish_login(timeout=timeout)

        if school is not None:
            if isinstance(school, str):
                self._school_id = await self._resolve_school(school, timeout=timeout)
            else:
                self._school_id = school

        self._credentials = ()
        self._start_keepalive()

    async def login_with_session_store(
        self,
        session_store: str,
        school: Optional[Union[int, str]] = None,
        *,
        timeout: int | None = None,
    ) -> None:
        """Вход с использованием строки session-store из localStorage браузера."""
        token = self._extract_access_token_from_session_store(session_store)
        if not token:
            raise exceptions.LoginError("accessToken не найден в session-store")
        await self.login_with_token(token, school, timeout=timeout)

    async def login_with_cookies(
        self,
        cookies: str,
        school: Optional[Union[int, str]] = None,
        *,
        timeout: int | None = None,
    ) -> None:
        """Вход с использованием строки куки из браузера.

        Формат: ``"NSSESSIONID=abc123"`` или полная Cookie-строка.
        """
        parsed = self._parse_cookies(cookies)
        if not parsed:
            raise exceptions.LoginError(
                "Не удалось извлечь куки. Передайте строку вида "
                "'NSSESSIONID=xxx' или полную Cookie-строку из DevTools."
            )

        for name, value in parsed.items():
            self._http.set_cookie(name, value)

        try:
            resp = await self._http.get("student/diary/init", timeout=timeout)
            info = resp.json()
            student = info["students"][info["currentStudentId"]]
            self._student_id = student["studentId"]
        except Exception as e:
            raise exceptions.LoginError(
                f"Куки невалидны или сессия истекла: {e}"
            )

        at = resp.headers.get("at", "")
        if at:
            self._access_token = at
            self._http.set_header("at", at)

        await self._finish_login(timeout=timeout)

        if school is not None:
            if isinstance(school, str):
                self._school_id = await self._resolve_school(school, timeout=timeout)
            else:
                self._school_id = school

        self._credentials = ()
        self._start_keepalive()

    @staticmethod
    def _parse_cookies(raw: str) -> Dict[str, str]:
        raw = raw.strip()
        if not raw:
            return {}
        if re.fullmatch(r"[0-9a-fA-F]{32}", raw):
            return {"NSSESSIONID": raw}
        result = {}
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                key, _, value = part.partition("=")
                result[key.strip()] = value.strip()
        return result if "NSSESSIONID" in result else {}

    @staticmethod
    def _extract_access_token_from_session_store(
        session_store: str,
    ) -> Optional[str]:
        try:
            data = json.loads(session_store)
        except Exception:
            return None

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                return None

        if isinstance(data, dict):
            return data.get("accessToken") or data.get("at")

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("active") and item.get("accessToken"):
                    return item["accessToken"]
            for item in data:
                if isinstance(item, dict) and item.get("accessToken"):
                    return item["accessToken"]
        return None

    # ═══════════════════════════════════════════════════════════
    #  API-методы
    # ═══════════════════════════════════════════════════════════

    async def _authed_get(
        self, path: str, *, timeout: int | None = None, **kw: Any,
    ) -> httpx.Response:
        """GET с автоматической переавторизацией при 401."""
        try:
            return await self._http.get(path, timeout=timeout, **kw)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.UNAUTHORIZED:
                if self._credentials:
                    await self.login(*self._credentials)
                    return await self._http.get(path, timeout=timeout, **kw)
                raise exceptions.LoginError(
                    "Сначала вызовите login()"
                ) from None
            raise

    async def _authed_post(
        self, path: str, *, timeout: int | None = None, **kw: Any,
    ) -> httpx.Response:
        """POST с автоматической переавторизацией при 401."""
        try:
            return await self._http.post(path, timeout=timeout, **kw)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.UNAUTHORIZED:
                if self._credentials:
                    await self.login(*self._credentials)
                    return await self._http.post(path, timeout=timeout, **kw)
                raise exceptions.LoginError(
                    "Сначала вызовите login()"
                ) from None
            raise

    async def diary(
        self,
        start: date | None = None,
        end: date | None = None,
        *,
        timeout: int | None = None,
    ) -> Diary:
        """Получить дневник за неделю (по-умолчанию — текущую)."""
        if not start:
            start = date.today() - timedelta(days=date.today().weekday())
        if not end:
            end = start + timedelta(days=5)

        resp = await self._authed_get(
            "student/diary",
            params={
                "studentId": self._student_id,
                "yearId": self._year_id,
                "weekStart": start.isoformat(),
                "weekEnd": end.isoformat(),
            },
            timeout=timeout,
        )
        return Diary.from_raw(resp.json(), self._assignment_types)

    async def overdue(
        self,
        start: date | None = None,
        end: date | None = None,
        *,
        timeout: int | None = None,
    ) -> List[Assignment]:
        """Получить просроченные задания."""
        if not start:
            start = date.today() - timedelta(days=date.today().weekday())
        if not end:
            end = start + timedelta(days=5)

        resp = await self._authed_get(
            "student/diary/pastMandatory",
            params={
                "studentId": self._student_id,
                "yearId": self._year_id,
                "weekStart": start.isoformat(),
                "weekEnd": end.isoformat(),
            },
            timeout=timeout,
        )
        return [
            Assignment.from_raw(a, self._assignment_types)
            for a in resp.json()
        ]

    async def announcements(
        self,
        take: int = -1,
        *,
        timeout: int | None = None,
    ) -> List[Announcement]:
        """Получить объявления."""
        resp = await self._authed_get(
            "announcements", params={"take": take}, timeout=timeout,
        )
        return [Announcement.from_raw(a) for a in resp.json()]

    async def attachments(
        self,
        assignment_id: int,
        *,
        timeout: int | None = None,
    ) -> List[Attachment]:
        """Получить вложения к заданию."""
        resp = await self._authed_post(
            "student/diary/get-attachments",
            params={"studentId": self._student_id},
            json={"assignId": [assignment_id]},
            timeout=timeout,
        )
        items = resp.json()
        if not items:
            return []
        return [
            Attachment.from_raw(a) for a in items[0].get("attachments", [])
        ]

    async def school_info(self, *, timeout: int | None = None) -> School:
        """Получить информацию о школе."""
        resp = await self._authed_get(
            f"schools/{self._school_id}/card", timeout=timeout,
        )
        return School.from_raw(resp.json())

    async def download_attachment(
        self,
        attachment_id: int,
        buffer: BytesIO,
        *,
        timeout: int | None = None,
    ) -> None:
        """Скачать вложение в буфер."""
        resp = await self._authed_get(
            f"attachments/{attachment_id}", timeout=timeout,
        )
        buffer.write(resp.content)

    async def download_profile_picture(
        self,
        user_id: int,
        buffer: BytesIO,
        *,
        timeout: int | None = None,
    ) -> None:
        """Скачать аватар пользователя."""
        resp = await self._authed_get(
            "users/photo",
            params={"at": self._access_token, "userId": user_id},
            timeout=timeout,
            follow_redirects=True,
        )
        buffer.write(resp.content)

    # ══ Школы ════════════════════════════════════════════════

    async def schools(self, *, timeout: int | None = None) -> List[ShortSchool]:
        """Список доступных школ."""
        resp = await self._http.get(
            "schools/search", params={"name": "У"}, timeout=timeout,
        )
        return [ShortSchool.from_raw(s) for s in resp.json()]

    async def _resolve_school(
        self,
        school_name: str,
        *,
        timeout: int | None = None,
    ) -> int:
        """Найти ID школы по короткому названию."""
        resp = await self._http.get(
            "schools/search", params={"name": school_name}, timeout=timeout,
        )
        for s in resp.json():
            if s["shortName"] == school_name:
                self._school_id = s["id"]
                return s["id"]
        raise exceptions.SchoolNotFound(school_name)

    # ═══════════════════════════════════════════════════════════
    #  Почта / сообщения
    # ═══════════════════════════════════════════════════════════

    async def mail_list(
        self,
        folder: str = "Inbox",
        page: int = 1,
        page_size: int = 20,
        *,
        timeout: int | None = None,
    ) -> MailPage:
        """Получить список писем из указанной папки.

        Args:
            folder: Папка — ``"Inbox"`` (входящие, по-умолчанию),
                ``"Sent"`` (отправленные), ``"Draft"`` (черновики),
                ``"Deleted"`` (удалённые).
            page: Номер страницы (начиная с 1).
            page_size: Количество писем на странице.

        Returns:
            Объект ``MailPage`` с полями ``entries`` (список ``MailEntry``),
            ``page`` и ``total_items``.
        """
        folder_labels = {
            "Inbox": "Входящие",
            "Sent": "Отправленные",
            "Draft": "Черновики",
            "Deleted": "Удалённые",
        }
        resp = await self._authed_post(
            "mail/registry",
            json={
                "filterContext": {
                    "selectedData": [
                        {
                            "filterId": "MailBox",
                            "filterValue": folder,
                            "filterText": folder_labels.get(folder, folder),
                        },
                        {
                            "filterId": "MessageType",
                            "filterValue": "All",
                            "filterText": "Все",
                        },
                    ],
                    "params": None,
                },
                "fields": ["author", "subject", "sent"],
                "page": page,
                "pageSize": page_size,
                "search": None,
                "order": {"fieldId": "sent", "ascending": False},
            },
            timeout=timeout,
        )
        return MailPage.from_raw(resp.json())

    async def mail_unread(
        self, *, timeout: int | None = None,
    ) -> List[int]:
        """Список ID непрочитанных писем.

        Returns:
            Список целочисленных ID непрочитанных сообщений.
        """
        resp = await self._authed_get(
            "mail/messages/unread",
            params={"userId": self._student_id},
            timeout=timeout,
        )
        return resp.json()

    async def mail_read(
        self, message_id: int, *, timeout: int | None = None,
    ) -> Message:
        """Прочитать письмо по ID.

        Args:
            message_id: ID сообщения (можно получить из ``mail_unread()``).

        Returns:
            Объект ``Message`` с полным содержимым письма.
        """
        resp = await self._authed_get(
            f"mail/messages/{message_id}/read",
            params={"userId": self._student_id},
            timeout=timeout,
        )
        return Message.from_raw(resp.json())

    async def mail_recipients(
        self, *, timeout: int | None = None,
    ) -> List[MailRecipient]:
        """Список доступных получателей писем (учителя, администрация)."""
        resp = await self._authed_get(
            "mail/recipients",
            params={
                "userId": self._student_id,
                "organizationId": self._school_id,
                "funcType": 2,
                "orgType": 1,
                "group": 1,
            },
            timeout=timeout,
        )
        return [MailRecipient.from_raw(r) for r in resp.json()]

    async def mail_send(
        self,
        subject: str,
        text: str,
        to: List[str],
        *,
        timeout: int | None = None,
    ) -> None:
        """Отправить письмо.

        Args:
            subject: Тема письма.
            text: Текст письма.
            to: Список ID получателей (из ``mail_recipients()``).
        """
        await self._authed_post(
            "mail/messages/send",
            json={
                "subject": subject,
                "text": text,
                "to": [{"id": r} for r in to],
                "cc": [],
                "bcc": [],
                "notify": False,
                "fileAttachments": [],
            },
            timeout=timeout,
        )

    # ── Выход ────────────────────────────────────────────────

    async def logout(self, *, timeout: int | None = None) -> None:
        """Завершить сессию."""
        self._stop_keepalive()
        try:
            await self._http.post("auth/logout", timeout=timeout)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.UNAUTHORIZED:
                raise

    async def close(self, *, timeout: int | None = None) -> None:
        """Завершить сессию и закрыть HTTP-клиент."""
        await self.logout(timeout=timeout)
        await self._http.close()

"""HTTP-обёртка поверх httpx с таймаутами и повтором при ReadTimeout."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from netschoolpy.exceptions import ServerUnavailable

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 5   # секунд (прямое соединение)
_TOR_TIMEOUT = 30      # секунд (Tor медленнее)

# SOCKS5-прокси Tor (локальный, поднятый системой)
_TOR_PROXY = "socks5://127.0.0.1:9050"

# Кэш хостов, для которых прямое соединение не работает → нужен Tor
_tor_hosts: set[str] = set()


class HttpSession:
    """Тонкая обёртка вокруг ``httpx.AsyncClient``.

    • При ``ReadTimeout`` автоматически повторяет запрос.
    • При ``ConnectError``/``ConnectTimeout`` — автоматически повторяет
      через Tor (socks5://127.0.0.1:9050), если он доступен.
      Полезно для региональных серверов СГО, блокирующих datacenter IP.
    • Если общий таймаут ``timeout`` исчерпан — бросает ``ServerUnavailable``.
    """

    def __init__(self, base_url: str, *, timeout: int | None = None):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=f"{self._base_url}/webapi",
            headers={
                "user-agent": "NetSchoolPy/1.0",
                "referer": self._base_url,
            },
            event_hooks={"response": [self._check_status]},
        )
        self._timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT

    # ── публичные свойства ───────────────────────────────────

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def client(self) -> httpx.AsyncClient:
        """Прямой доступ к ``httpx.AsyncClient`` (для куки и т.п.)."""
        return self._client

    # ── удобные мутаторы ─────────────────────────────────────

    def set_header(self, key: str, value: str) -> None:
        self._client.headers[key] = value

    def remove_header(self, key: str) -> None:
        self._client.headers.pop(key, None)

    def set_cookie(self, name: str, value: str) -> None:
        self._client.cookies.set(name, value)

    # ── HTTP-методы ──────────────────────────────────────────

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
        follow_redirects: bool = False,
    ) -> httpx.Response:
        return await self._send(
            "GET", path, params=params,
            timeout=timeout, follow_redirects=follow_redirects,
        )

    async def post(
        self,
        path: str,
        *,
        data: Any | None = None,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> httpx.Response:
        return await self._send(
            "POST", path, data=data, json=json,
            params=params, headers=headers, timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()
        if hasattr(self, "_tor_client"):
            await self._tor_client.aclose()

    # ── внутренняя механика ──────────────────────────────────

    def _get_active_client(self) -> httpx.AsyncClient:
        """Возвращает Tor-клиент если хост заблокирован, иначе обычный."""
        import httpx as _httpx
        host = self._base_url
        if host in _tor_hosts:
            if not hasattr(self, "_tor_client"):
                log.info("🧅 Tor fallback activated for %s", host)
                self._tor_client = _httpx.AsyncClient(
                    base_url=f"{host}/webapi",
                    headers={
                        "user-agent": "NetSchoolPy/1.0",
                        "referer": host,
                    },
                    proxy=_TOR_PROXY,
                    event_hooks={"response": [self._check_status]},
                )
            return self._tor_client
        return self._client

    async def _send(
        self,
        method: str,
        path: str,
        *,
        timeout: int | None = None,
        follow_redirects: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        direct_timeout = timeout if timeout is not None else self._timeout
        max_5xx_retries = 3

        async def _do_request(client: httpx.AsyncClient) -> httpx.Response:
            retry_5xx = 0
            while True:
                try:
                    req = client.build_request(
                        method, path,
                        **{k: v for k, v in kwargs.items() if v is not None},
                    )
                    return await client.send(req, follow_redirects=follow_redirects)
                except httpx.ReadTimeout:
                    await asyncio.sleep(0.1)
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if 500 <= status < 600 and retry_5xx < max_5xx_retries:
                        retry_5xx += 1
                        await asyncio.sleep(0.2 * retry_5xx)
                        continue
                    raise

        # Если хост уже помечен как требующий Tor — идём сразу через него
        if self._base_url in _tor_hosts:
            try:
                return await asyncio.wait_for(
                    _do_request(self._get_active_client()), _TOR_TIMEOUT
                )
            except asyncio.TimeoutError:
                raise ServerUnavailable("Сервер не ответил (Tor)") from None

        # Пробуем прямое соединение
        connect_failed = False
        try:
            return await asyncio.wait_for(
                _do_request(self._client), direct_timeout
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            connect_failed = True
        except asyncio.TimeoutError:
            connect_failed = True

        # Прямое не сработало — пробуем через Tor
        if connect_failed:
            if self._base_url not in _tor_hosts:
                log.warning(
                    "🧅 Direct connection failed for %s, retrying via Tor...",
                    self._base_url,
                )
                _tor_hosts.add(self._base_url)
            try:
                return await asyncio.wait_for(
                    _do_request(self._get_active_client()), _TOR_TIMEOUT
                )
            except asyncio.TimeoutError:
                raise ServerUnavailable("Сервер не ответил (Tor)") from None

    @staticmethod
    async def _check_status(response: httpx.Response) -> None:
        if not response.is_redirect:
            if 500 <= response.status_code < 600:
                log.warning(
                    "Server error %d for %s",
                    response.status_code, response.url,
                )
            response.raise_for_status()

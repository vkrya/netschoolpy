"""HTTP-обёртка поверх httpx с таймаутами и повтором при ReadTimeout."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from netschoolpy.exceptions import ServerUnavailable

_DEFAULT_TIMEOUT = 5  # секунд


class HttpSession:
    """Тонкая обёртка вокруг ``httpx.AsyncClient``.

    • При ``ReadTimeout`` автоматически повторяет запрос.
    • Если общий таймаут ``timeout`` исчерпан — бросает ``ServerUnavailable``.
    """

    def __init__(self, base_url: str, *, timeout: int | None = None):
        url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=f"{url}/webapi",
            headers={
                "user-agent": "NetSchoolPy/1.0",
                "referer": url,
            },
            event_hooks={"response": [self._check_status]},
        )
        self._timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT

    # ── публичные свойства ───────────────────────────────────

    @property
    def base_url(self) -> str:
        return str(self._client.base_url)

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

    # ── внутренняя механика ──────────────────────────────────

    async def _send(
        self,
        method: str,
        path: str,
        *,
        timeout: int | None = None,
        follow_redirects: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        effective = timeout if timeout is not None else self._timeout
        max_5xx_retries = 3
        retry_5xx = 0

        async def _retry() -> httpx.Response:
            nonlocal retry_5xx
            while True:
                try:
                    req = self._client.build_request(
                        method, path,
                        **{k: v for k, v in kwargs.items() if v is not None},
                    )
                    return await self._client.send(
                        req, follow_redirects=follow_redirects,
                    )
                except httpx.ReadTimeout:
                    await asyncio.sleep(0.1)
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if 500 <= status < 600 and retry_5xx < max_5xx_retries:
                        retry_5xx += 1
                        await asyncio.sleep(0.2 * retry_5xx)
                        continue
                    raise

        try:
            if effective and effective > 0:
                return await asyncio.wait_for(_retry(), effective)
            return await _retry()
        except asyncio.TimeoutError:
            raise ServerUnavailable("Сервер не ответил") from None

    @staticmethod
    async def _check_status(response: httpx.Response) -> None:
        if not response.is_redirect:
            response.raise_for_status()

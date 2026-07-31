import re

with open('./netschoolpy/client.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add auto_relogin logic to _authed_get & _authed_post
old_authed_get = '''    async def _authed_get(
        self, path: str, *, params: dict[str, Any] | None = None, timeout: int | None = None
    ) -> httpx.Response:
        self._ensure_authed()
        return await self._http.get(path, params=params, timeout=timeout)'''

new_authed_get = '''    async def _authed_get(
        self, path: str, *, params: dict[str, Any] | None = None, timeout: int | None = None
    ) -> httpx.Response:
        self._ensure_authed()
        try:
            return await self._http.get(path, params=params, timeout=timeout)
        except exceptions.SessionExpired:
            if self._auto_relogin and self._last_login_args:
                log.info("🔄 Session expired, performing automatic re-login...")
                await self.login(**self._last_login_args)
                return await self._http.get(path, params=params, timeout=timeout)
            raise'''

code = code.replace(old_authed_get, new_authed_get)

old_authed_post = '''    async def _authed_post(
        self, path: str, *, json: Any | None = None, timeout: int | None = None
    ) -> httpx.Response:
        self._ensure_authed()
        return await self._http.post(path, json=json, timeout=timeout)'''

new_authed_post = '''    async def _authed_post(
        self, path: str, *, json: Any | None = None, timeout: int | None = None
    ) -> httpx.Response:
        self._ensure_authed()
        try:
            return await self._http.post(path, json=json, timeout=timeout)
        except exceptions.SessionExpired:
            if self._auto_relogin and self._last_login_args:
                log.info("🔄 Session expired, performing automatic re-login...")
                await self.login(**self._last_login_args)
                return await self._http.post(path, json=json, timeout=timeout)
            raise'''

code = code.replace(old_authed_post, new_authed_post)

# Save login args in self._last_login_args upon login
code = code.replace('await self._finish_login(timeout=timeout)', 'self._last_login_args = {"user_name": user_name, "password": password, "school": school}\n        await self._finish_login(timeout=timeout)')

# Add caching to subjects()
old_subjects = '''    async def subjects(
        self, timeout: int | None = None
    ) -> list[SubjectInfo]:
        """Возвращает список предметов ученика."""
        resp = await self._authed_get(
            f"students/{self._student_id}/subjects", timeout=timeout
        )
        return [SubjectInfo.from_filter_item(item) for item in resp.json()]'''

new_subjects = '''    async def subjects(
        self, timeout: int | None = None
    ) -> list[SubjectInfo]:
        """Возвращает список предметов ученика (с TTL-кэшированием)."""
        cache_key = f"subjects:{self._student_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        resp = await self._authed_get(
            f"students/{self._student_id}/subjects", timeout=timeout
        )
        res = [SubjectInfo.from_filter_item(item) for item in resp.json()]
        self._cache.set(cache_key, res)
        return res'''

code = code.replace(old_subjects, new_subjects)

# Add caching to school_years()
old_years = '''    async def school_years(
        self, timeout: int | None = None
    ) -> list[SchoolYear]:
        """Возвращает доступные учебные года."""
        resp = await self._authed_get("years", timeout=timeout)
        return [SchoolYear.from_raw(item) for item in resp.json()]'''

new_years = '''    async def school_years(
        self, timeout: int | None = None
    ) -> list[SchoolYear]:
        """Возвращает доступные учебные года (с TTL-кэшированием)."""
        cache_key = "school_years"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        resp = await self._authed_get("years", timeout=timeout)
        res = [SchoolYear.from_raw(item) for item in resp.json()]
        self._cache.set(cache_key, res)
        return res'''

code = code.replace(old_years, new_years)

with open('./netschoolpy/client.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('Updated client.py successfully!')

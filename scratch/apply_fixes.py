"""Скрипт точного исправления models.py и client.py."""

with open('netschoolpy/models.py', 'r', encoding='utf-8') as f:
    m_code = f.read()

# Fix LoginMethods
old_lm = '''class LoginMethods(BaseModel):
    password: bool
    esia: bool
    esia_main: bool
    esia_button: bool'''

new_lm = '''class LoginMethods(BaseModel):
    password: bool = True
    esia: bool = False
    esia_main: bool = False
    esia_button: bool = False
    windows_auth: bool = False'''

m_code = m_code.replace(old_lm, new_lm)

# Fix Lesson types
old_lesson = '''class Lesson(BaseModel):
    number: int
    subject: str
    start: time
    end: time
    room: Optional[str]
    assignments: List[Assignment] = Field(default_factory=list)'''

new_lesson = '''class Lesson(BaseModel):
    number: int = 1
    subject: str = ""
    start: Any = None
    end: Any = None
    room: Optional[str] = None
    day: Optional[date] = None
    assignments: List[Assignment] = Field(default_factory=list)'''

m_code = m_code.replace(old_lesson, new_lesson)

with open('netschoolpy/models.py', 'w', encoding='utf-8') as f:
    f.write(m_code)

# Fix client.py __init__
with open('netschoolpy/client.py', 'r', encoding='utf-8') as f:
    c_code = f.read()

old_c_init = '''    def __init__(self, url: str, *, timeout: int | None = None,
                 proxy: str | None = None):'''

new_c_init = '''    def __init__(
        self,
        url: str,
        *,
        timeout: int | None = None,
        proxy: str | None = None,
        auto_relogin: bool = False,
        cache_ttl: float = 3600.0,
    ) -> None:
        from netschoolpy.cache import TTLCache
        self._http = HttpSession(url, timeout=timeout, proxy=proxy)
        self._proxy = proxy
        self._auto_relogin = auto_relogin
        self._cache = TTLCache(default_ttl=cache_ttl)
        self._last_login_args: dict | None = None'''

c_code = c_code.replace(old_c_init, new_c_init)

with open('netschoolpy/client.py', 'w', encoding='utf-8') as f:
    f.write(c_code)

print('Applied exact fixes!')

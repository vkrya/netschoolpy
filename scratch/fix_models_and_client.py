import re

# 1. Fix models.py defaults
with open('netschoolpy/models.py', 'r', encoding='utf-8') as f:
    m_code = f.read()

# Fix LoginMethods defaults
m_code = re.sub(r'class LoginMethods\(BaseModel\):\n\s+esia: bool\n\s+esia_main: bool\n\s+esia_button: bool\n\s+password: bool = True',
                'class LoginMethods(BaseModel):\n    esia: bool = False\n    esia_main: bool = False\n    esia_button: bool = False\n    password: bool = True',
                m_code)

# Fix Assignment defaults
m_code = m_code.replace('class Assignment(BaseModel):', '''class Assignment(BaseModel):
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
    attachments: List[Attachment] = Field(default_factory=list)''')

with open('netschoolpy/models.py', 'w', encoding='utf-8') as f:
    f.write(m_code)

# 2. Fix NetSchool __init__ signature in client.py
with open('netschoolpy/client.py', 'r', encoding='utf-8') as f:
    c_code = f.read()

# Find NetSchool __init__
pattern = r'class NetSchool:[^Class]*?def __init__\(\s*self,\s*url:\s*str,\s*\*,[^\)]*?\)\s*->\s*None:'
new_init = '''class NetSchool:
    def __init__(
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

c_code = re.sub(pattern, new_init, c_code, count=1, flags=re.DOTALL)

with open('netschoolpy/client.py', 'w', encoding='utf-8') as f:
    f.write(c_code)

print('Fixed models.py defaults and client.py __init__ signature!')

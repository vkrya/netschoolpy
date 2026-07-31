with open('netschoolpy/models.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace LoginMethods fields
old_lm_block = """class LoginMethods(BaseModel):
    \"\"\"Доступные способы авторизации на сервере SGO.

    Поля:
        password: Вход по логину и паролю SGO.
        esia: Вход через Госуслуги (ЕСИА) доступен.
        esia_main: Госуслуги — основной/обязательный способ входа.
        esia_button: Кнопка «Войти через Госуслуги» отображается.
    \"\"\"

    password: bool
    esia: bool
    esia_main: bool
    esia_button: bool"""

new_lm_block = """class LoginMethods(BaseModel):
    \"\"\"Доступные способы авторизации на сервере SGO.\"\"\"

    password: bool = True
    esia: bool = False
    esia_main: bool = False
    esia_button: bool = False
    windows_auth: bool = False"""

text = text.replace(old_lm_block, new_lm_block)

# Replace Lesson fields
old_lesson_block = """class Lesson(BaseModel):

    def to_ical_event(self) -> str:"""

new_lesson_block = """class Lesson(BaseModel):
    number: int = 1
    subject: str = ""
    start: Any = None
    end: Any = None
    room: Optional[str] = None
    day: Optional[date] = None
    assignments: List[Assignment] = Field(default_factory=list)

    def to_ical_event(self) -> str:"""

text = text.replace(old_lesson_block, new_lesson_block)

with open('netschoolpy/models.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Cleanly updated models.py!')

# netschoolpy

[![CI](https://github.com/Vladcom4iiik/netschoolpy/actions/workflows/ci.yml/badge.svg)](https://github.com/Vladcom4iiik/netschoolpy/actions)
[![PyPI](https://img.shields.io/pypi/v/netschoolpy)](https://pypi.org/project/netschoolpy/)
[![Python](https://img.shields.io/pypi/pyversions/netschoolpy)](https://pypi.org/project/netschoolpy/)

Асинхронный клиент для «Сетевого города». Дневник, оценки, домашние задания, объявления — всё программно, без браузера.

Репозиторий: https://github.com/Vladcom4iiik/netschoolpy

[Поддержать проект (ЮMoney)](https://yoomoney.ru/to/4100118867747459)

Ключевые слова: Сетевой город, SGO, дневник, оценки, домашние задания, Госуслуги, ESIA, QR, API.

## Документация (Docs)

Документация к проекту находится в папке [docs/](docs/). Для локального просмотра:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

## Установка

```bash
pip install netschoolpy

# Для отображения QR-кода в терминале (опционально):
pip install netschoolpy[qr]
```

## Способы входа

### По логину/паролю SGO

```python
import asyncio
from netschoolpy import NetSchool

async def main():
    async with NetSchool("https://sgo.example.ru") as ns:
        await ns.login("ИвановИ", "password", "Школа №1")
        diary = await ns.diary()

asyncio.run(main())
```

### Через Госуслуги (логин + пароль ЕСИА)

Программный вход через Госуслуги — без браузера.
Поддерживает SMS, TOTP (приложение-аутентификатор) и MAX (Госключ) в качестве второго фактора.

```python
async with NetSchool("https://sgo.example.ru") as ns:
    await ns.login_via_gosuslugi(
        esia_login="+79001234567",     # телефон, email или СНИЛС
        esia_password="your_password",
        school="Школа №1",             # если к аккаунту привязано несколько организаций
    )
    diary = await ns.diary()
```

При MFA код из SMS/TOTP/MAX будет запрошен через `input()`.
Если `esia_login` / `esia_password` не указаны, они тоже запрашиваются через `input()`.
Если к аккаунту привязано несколько организаций и `school` не указан — будет предложен интерактивный выбор.

### Через Госуслуги (QR-код)

Вход без ввода логина и пароля — нужно отсканировать QR-код
в мобильном приложении «Госуслуги».

```python
async def show_qr(qr_data: str):
    """qr_data — deep-link gosuslugi://auth/signed_token=..."""
    import qrcode
    qrcode.make(qr_data).save("qr.png")
    print("Отсканируйте QR в приложении Госуслуги!")

async with NetSchool("https://sgo.example.ru") as ns:
    await ns.login_via_gosuslugi_qr(
        qr_callback=show_qr,   # вызовется после генерации QR
        qr_timeout=120,         # секунд ожидания сканирования
        school="Школа №1",     # если привязано несколько организаций
    )
    diary = await ns.diary()
```

- `qr_callback` — async/sync функция, получает deep-link
  `gosuslugi://auth/signed_token=...` для кодирования в QR.
  Если не указан — QR печатается в stdout (`pip install qrcode`).
- `qr_timeout` — таймаут ожидания сканирования (по-умолчанию 120 сек).
- `school` — название организации (подстрока). Если привязано несколько — выбирает автоматически. Без параметра — интерактивный выбор.

### По токену / куки (продвинутое)

```python
# По accessToken из localStorage SGO:
await ns.login_with_token("eyJ...")

# По session-store из localStorage:
await ns.login_with_session_store('{"accessToken":"eyJ..."}')

# По Cookie-строке из DevTools:
await ns.login_with_cookies("NSSESSIONID=abc123")
```

## Удержание сессии (keep-alive)

После любого входа автоматически запускается фоновая задача,
которая каждые **5 минут** пингует сервер, не давая сессии истечь.

```python
# Изменить интервал (в секундах):
ns.set_keepalive_interval(120)   # каждые 2 минуты

# Отключить keep-alive:
ns.set_keepalive_interval(0)
```

При вызове `logout()` keep-alive останавливается автоматически.

## Справочник регионов

Библиотека включает справочник из **26 регионов** с готовыми URL.

```python
from netschoolpy import REGIONS, get_url, list_regions

# Все доступные регионы
for name in list_regions():
    print(name, "→", REGIONS[name])

# Быстрый поиск (регистронезависимый, поддерживает подстроки)
url = get_url("Челябинская область")   # "https://sgo.edu-74.ru"
url = get_url("челябинская")           # тоже найдёт

# Использование с клиентом
async with NetSchool(get_url("Краснодарский край")) as ns:
    ...
```

> **Примечание:** Иркутская, Ростовская и Свердловская области имеют
> несколько независимых серверов — для них URL нужно указывать вручную.

## Экспорт/импорт сессии

Чтобы не авторизоваться каждый раз, можно сохранить и восстановить сессию:

```python
from pathlib import Path

# Сохранить после логина:
session_data = ns.export_session()
Path("session.json").write_text(session_data)

# Восстановить при следующем запуске:
async with NetSchool("https://sgo.example.ru") as ns:
    try:
        await ns.import_session(Path("session.json").read_text())
    except netschoolpy.SessionExpired:
        await ns.login(...)  # сессия истекла — логинимся заново
```

## API

```python
async with NetSchool("https://sgo.example.ru") as ns:
    await ns.login(...)

    diary = await ns.diary()                    # дневник (текущая неделя)
    diary = await ns.diary(start, end)          # дневник за период

    overdue = await ns.overdue()                # просроченные задания
    announcements = await ns.announcements()    # объявления
    attachments = await ns.attachments(...)     # вложения к заданию
    info = await ns.school_info()               # информация о школе

    await ns.download_attachment(id, buffer)    # скачать вложение
    await ns.download_profile_picture(id, buf)  # аватар пользователя
```

## Исключения

```python
import netschoolpy

netschoolpy.NetSchoolError      # базовое
netschoolpy.LoginError          # ошибка авторизации
netschoolpy.MFAError            # ошибка двухфакторной (SMS/TOTP/PUSH)
netschoolpy.ESIAError           # ошибка на стороне Госуслуг
netschoolpy.SchoolNotFound      # школа не найдена
netschoolpy.SessionExpired      # сессия истекла (401)
netschoolpy.ServerUnavailable   # сервер не ответил
```

## Логирование

Библиотека использует стандартный `logging`. Для отладки:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Лицензия

© 2026 Vladcom4iiik.
GNU GPLv3. Подробнее — [LICENSE](LICENSE).

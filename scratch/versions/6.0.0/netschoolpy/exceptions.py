"""Исключения netschoolpy."""


class NetSchoolError(Exception):
    """Базовое исключение библиотеки."""


class LoginError(NetSchoolError):
    """Ошибка авторизации (неверные данные, школа не найдена и т.д.)."""


class MFAError(LoginError):
    """Ошибка двухфакторной аутентификации (неверный код, таймаут и т.д.)."""


class ESIAError(LoginError):
    """Ошибка на стороне Госуслуг (ESIA недоступна, неожиданный ответ)."""


class SchoolNotFound(LoginError):
    """Школа с указанным названием не найдена."""


class SessionExpired(NetSchoolError):
    """Сессия истекла (HTTP 401). Необходимо повторно авторизоваться."""


class ServerUnavailable(NetSchoolError):
    """Сервер не ответил в отведённое время."""

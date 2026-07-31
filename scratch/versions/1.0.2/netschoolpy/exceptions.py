"""Исключения netschoolpy."""


class NetSchoolError(Exception):
    """Базовое исключение библиотеки."""


class LoginError(NetSchoolError):
    """Ошибка авторизации (неверные данные, MFA и т.д.)."""


class SchoolNotFound(NetSchoolError):
    """Школа с указанным названием не найдена."""


class ServerUnavailable(NetSchoolError):
    """Сервер не ответил в отведённое время."""

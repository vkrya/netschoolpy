"""netschoolpy — асинхронный клиент для «Сетевого города»."""

from .client import NetSchool, get_login_methods, search_schools
from .exceptions import (
    ESIAError,
    LoginError,
    MFAError,
    NetSchoolError,
    SchoolNotFound,
    ServerUnavailable,
    SessionExpired,
)
from .models import LoginMethods
from .regions import REGIONS, get_url, list_regions

__version__ = "3.2.1"

__all__ = [
    "NetSchool",
    "search_schools",
    "get_login_methods",
    "LoginMethods",
    "NetSchoolError",
    "LoginError",
    "MFAError",
    "ESIAError",
    "SchoolNotFound",
    "SessionExpired",
    "ServerUnavailable",
    "REGIONS",
    "get_url",
    "list_regions",
]

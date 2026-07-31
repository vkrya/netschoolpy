"""netschoolpy — асинхронный клиент для «Сетевого города»."""

from .client import NetSchool, get_login_methods, get_total_marks, search_schools
from .exceptions import (
    ESIAError,
    LoginError,
    MFAError,
    NetSchoolError,
    SchoolNotFound,
    ServerUnavailable,
    SessionExpired,
)
from .models import (
    AssignedMark,
    LoginMethods,
    SPECIAL_MARK_DESCRIPTIONS,
    ReportingPeriod,
    SchoolYear,
    Student,
    SubjectGrades,
    SubjectInfo,
    SubjectTotalMark,
    TotalMarksReportLine,
)
from .regions import REGIONS, get_url, list_regions

__version__ = "8.0.1"

__all__ = [
    "NetSchool",
    "search_schools",
    "get_login_methods",
    "get_total_marks",
    "AssignedMark",
    "LoginMethods",
    "SPECIAL_MARK_DESCRIPTIONS",
    "ReportingPeriod",
    "SchoolYear",
    "Student",
    "SubjectGrades",
    "SubjectInfo",
    "SubjectTotalMark",
    "TotalMarksReportLine",
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

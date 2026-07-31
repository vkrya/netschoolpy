"""Скрипт преобразования всех моделей 7.1.3 на Pydantic v2 с сохранением всех методов и дополнением to_ical."""

import re

with open('./scratch/versions/7.1.3/netschoolpy/models.py', 'r', encoding='utf-8') as f:
    orig = f.read()

# Replace dataclass imports with Pydantic v2
header = '''"""Pydantic v2 модели данных для библиотеки netschoolpy."""

from __future__ import annotations

from dataclasses import field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

'''

# Remove @dataclass(frozen=True) / @dataclass and convert dataclasses to Pydantic BaseModel
content = orig
content = re.sub(r'from dataclasses import [^\n]+\n', '', content)
content = re.sub(r'@dataclass\([^\)]*\)\n', '', content)
content = re.sub(r'@dataclass\n', '', content)

# Change dataclass definitions to Pydantic BaseModel inheritance
classes = [
    'Student', 'Attachment', 'Author', 'Announcement', 'Assignment', 'Lesson',
    'Day', 'Diary', 'SubjectTotalMark', 'AssignedMark', 'ShortSchool', 'School',
    'LoginMethods', 'MailEntry', 'MailPage', 'MailRecipient', 'Message',
    'ReportingPeriod', 'SubjectInfo', 'SubjectGrades', 'SchoolYear', 'TotalMarksReportLine'
]

for c in classes:
    content = re.sub(rf'class {c}:', f'class {c}(BaseModel):', content)

# Add model_config for arbitrary types if needed
content = content.replace('class Student(BaseModel):', 'class Student(BaseModel):\n    model_config = ConfigDict(arbitrary_types_allowed=True)\n')

# Replace field(default_factory=...) with Field(default_factory=...)
content = content.replace('field(default_factory=', 'Field(default_factory=')
content = content.replace('field(default=', 'Field(default=')

# Add to_ical_event and to_ical methods
ical_methods = '''
    def to_ical_event(self) -> str:
        """Генерирует строку события VEVENT в формате iCalendar (RFC 5545)."""
        dt_format = "%Y%m%dT%H%M%SZ"
        start_str = self.start.strftime(dt_format)
        end_str = self.end.strftime(dt_format)
        summary = f"{self.number}. {self.subject}"
        desc = []
        if self.room:
            desc.append(f"Кабинет: {self.room}")
        for a in self.assignments:
            assign_str = f"• {a.title} [{a.type_name}]"
            if a.mark:
                assign_str += f" — Оценка: {a.mark}"
            desc.append(assign_str)
        description_str = "\\n".join(desc)

        lines = [
            "BEGIN:VEVENT",
            f"UID:netschool-lesson-{int(self.start.timestamp())}-{self.number}@netschoolpy",
            f"DTSTAMP:{datetime.utcnow().strftime(dt_format)}",
            f"DTSTART:{start_str}",
            f"DTEND:{end_str}",
            f"SUMMARY:{summary}",
        ]
        if self.room:
            lines.append(f"LOCATION:{self.room}")
        if description_str:
            lines.append(f"DESCRIPTION:{description_str}")
        lines.append("END:VEVENT")
        return "\\n".join(lines)
'''

content = content.replace('class Lesson(BaseModel):', 'class Lesson(BaseModel):\n' + ical_methods)

diary_ical = '''
    def to_ical(self) -> str:
        """Экспортирует весь дневник в формат iCalendar (.ics)."""
        events = []
        for day in self.days:
            for lesson in day.lessons:
                events.append(lesson.to_ical_event())

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//netschoolpy//NetSchool Diary//RU",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Сетевой Город - Дневник",
        ]
        lines.extend(events)
        lines.append("END:VCALENDAR")
        return "\\n".join(lines)
'''

content = content.replace('class Diary(BaseModel):', 'class Diary(BaseModel):\n' + diary_ical)

full_file = header + content

with open('./netschoolpy/models.py', 'w', encoding='utf-8') as f:
    f.write(full_file)

print('Successfully created complete Pydantic v2 models.py!')

with open('netschoolpy/models.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('from datetime import date, datetime, time', 'from datetime import date as DateType, datetime as DateTimeType, time as TimeType\nfrom datetime import date, datetime, time')
text = text.replace('date: date = Field(default_factory=date.today)', 'date: DateType = Field(default_factory=DateType.today)')

with open('netschoolpy/models.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Fixed date field collision in AssignedMark')

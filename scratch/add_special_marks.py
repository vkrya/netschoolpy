with open('netschoolpy/models.py', 'r', encoding='utf-8') as f:
    text = f.read()

special_marks_code = '''
SPECIAL_MARK_DESCRIPTIONS: Dict[str, str] = {
    "УП": "Пропуск по уважительной причине",
    "Б": "Пропустил по болезни",
    "НП": "Пропуск по неуважительной причине",
    "ОТ": "Отсутствовал",
    "ОП": "Опоздал",
    "ОСВ": "Освобожден от посещения",
}
'''

text += special_marks_code

with open('netschoolpy/models.py', 'w', encoding='utf-8') as f:
    f.write(text)

with open('netschoolpy/__init__.py', 'r', encoding='utf-8') as f:
    init_text = f.read()

init_text = init_text.replace('    LoginMethods,\n', '    LoginMethods,\n    SPECIAL_MARK_DESCRIPTIONS,\n')
init_text = init_text.replace('    "LoginMethods",\n', '    "LoginMethods",\n    "SPECIAL_MARK_DESCRIPTIONS",\n')

with open('netschoolpy/__init__.py', 'w', encoding='utf-8') as f:
    f.write(init_text)

print('Added SPECIAL_MARK_DESCRIPTIONS to models.py and __init__.py')

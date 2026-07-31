"""Консольная утилита (CLI) для библиотеки netschoolpy."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Sequence

from netschoolpy.regions import REGIONS, get_url, list_regions


def print_banner() -> None:
    print("=" * 60)
    print(" 🏫 NetSchoolPy CLI — «Сетевой город. Образование»")
    print("=" * 60)


def cmd_regions(args: argparse.Namespace) -> None:
    print_banner()
    if args.query:
        url = get_url(args.query)
        if url:
            print(f"\n✅ Найден регион по запросу '{args.query}':")
            print(f"   URL: {url}")
        else:
            print(f"\n❌ Регион по запросу '{args.query}' не найден или неоднозначен.")
            matches = [r for r in list_regions() if args.query.lower() in r.lower()]
            if matches:
                print("   Возможные варианты:", ", ".join(matches))
    else:
        print(f"\n📍 Доступно {len(REGIONS)} регионов в справочнике:\n")
        for name in list_regions():
            print(f"  • {name:<35} → {REGIONS[name]}")


async def async_cmd_diary(args: argparse.Namespace) -> None:
    from netschoolpy.client import NetSchool

    print_banner()
    url = args.url
    if not url and args.region:
        url = get_url(args.region)

    if not url:
        print("❌ Ошибка: Укажите --url или --region!")
        sys.exit(1)

    print(f"🌐 Подключение к {url}...")
    async with NetSchool(url, proxy=args.proxy, auto_relogin=True) as ns:
        try:
            print(f"🔑 Авторизация для пользователя '{args.user}'...")
            await ns.login(args.user, args.password, school=args.school)
            print("📅 Загрузка дневника...")
            diary = await ns.diary()
            print(f"\n📖 Дневник на неделю ({diary.start} — {diary.end}):")
            for day in diary.days:
                print(f"\n📆 {day.date.strftime('%d.%m.%Y (%A)')}:")
                if not day.lessons:
                    print("   (нет уроков)")
                    continue
                for lesson in day.lessons:
                    room_str = f" [Каб. {lesson.room}]" if lesson.room else ""
                    print(f"   {lesson.number}. {lesson.subject}{room_str} ({lesson.start.strftime('%H:%M')}-{lesson.end.strftime('%H:%M')})")
                    for a in lesson.assignments:
                        mark_str = f" -> Оценка: {a.mark}" if a.mark else ""
                        print(f"      • {a.title} [{a.type_name}]{mark_str}")

            if args.export_ical:
                with open(args.export_ical, "w", encoding="utf-8") as f:
                    f.write(diary.to_ical())
                print(f"\n💾 Календарь успешно экспортирован в файл '{args.export_ical}'!")

        except Exception as exc:
            print(f"❌ Ошибка: {exc}")
            sys.exit(1)


def cmd_diary(args: argparse.Namespace) -> None:
    asyncio.run(async_cmd_diary(args))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="netschoolpy",
        description="Консольная утилита для работы с Сетевым Городом.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Команды")

    parser_regions = subparsers.add_parser("regions", help="Просмотр и поиск в справочнике регионов")
    parser_regions.add_argument("query", nargs="?", help="Название региона для поиска")
    parser_regions.set_defaults(func=cmd_regions)

    parser_diary = subparsers.add_parser("diary", help="Просмотр дневника и экспорта в .ics")
    parser_diary.add_argument("-u", "--user", required=True, help="Логин SGO")
    parser_diary.add_argument("-p", "--password", required=True, help="Пароль SGO")
    parser_diary.add_argument("--url", help="URL сервера Сетевого города")
    parser_diary.add_argument("--region", help="Название региона (вместо --url)")
    parser_diary.add_argument("--school", help="Название школы (подстрока)")
    parser_diary.add_argument("--proxy", help="Прокси (например, http://127.0.0.1:8080)")
    parser_diary.add_argument("--export-ical", help="Путь для сохранения .ics файла календаря")
    parser_diary.set_defaults(func=cmd_diary)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

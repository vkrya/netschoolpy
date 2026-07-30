"""Тесты для модуля regions."""

from __future__ import annotations

from netschoolpy.regions import REGIONS, get_url, list_regions


class TestREGIONS:
    def test_count(self) -> None:
        assert len(REGIONS) == 26

    def test_all_urls_have_scheme(self) -> None:
        for name, url in REGIONS.items():
            assert url.startswith(("http://", "https://")), (
                f"{name}: некорректный URL {url}"
            )

    def test_sorted(self) -> None:
        keys = list(REGIONS.keys())
        assert keys == sorted(keys), "REGIONS должен быть отсортирован"

    def test_known_regions_present(self) -> None:
        expected = [
            "Алтайский край",
            "Амурская область",
            "Забайкальский край",
            "Калужская область",
            "Камчатский край",
            "Костромская область",
            "Краснодарский край",
            "Ленинградская область",
            "Приморский край",
            "Республика Алтай",
            "Республика Бурятия",
            "Республика Ингушетия",
            "Республика Коми",
            "Республика Марий Эл",
            "Республика Мордовия",
            "Республика Саха (Якутия)",
            "Рязанская область",
            "Самарская область",
            "Сахалинская область",
            "Тверская область",
            "Томская область",
            "Ульяновская область",
            "Челябинская область",
            "Черноголовка",
            "Чувашская Республика",
            "Ямало-Ненецкий автономный округ",
        ]
        for name in expected:
            assert name in REGIONS, f"{name} отсутствует в REGIONS"

    def test_specific_urls(self) -> None:
        assert REGIONS["Черноголовка"] == "https://journal.nschg.ru"
        assert REGIONS["Самарская область"] == "https://asurso.ru"
        assert REGIONS["Республика Саха (Якутия)"] == "https://sgo.e-yakutia.ru"
        assert REGIONS["Сахалинская область"] == "https://netcity.admsakhalin.ru:11111"


class TestListRegions:
    def test_returns_sorted_list(self) -> None:
        names = list_regions()
        assert names == sorted(names)
        assert len(names) == len(REGIONS)

    def test_contains_known(self) -> None:
        names = list_regions()
        assert "Челябинская область" in names
        assert "Краснодарский край" in names
        assert "Черноголовка" in names


class TestGetUrl:
    def test_exact_match(self) -> None:
        assert get_url("Челябинская область") == "https://sgo.edu-74.ru"

    def test_case_insensitive(self) -> None:
        assert get_url("челябинская область") == "https://sgo.edu-74.ru"

    def test_partial_unique(self) -> None:
        assert get_url("Челябинская") == "https://sgo.edu-74.ru"

    def test_partial_case_insensitive(self) -> None:
        assert get_url("челябинская") == "https://sgo.edu-74.ru"

    def test_ambiguous_returns_none(self) -> None:
        # "Республика" matches multiple entries
        assert get_url("Республика") is None

    def test_not_found_returns_none(self) -> None:
        assert get_url("Несуществующий регион") is None

    def test_empty_string(self) -> None:
        # Empty string is a substring of everything → ambiguous
        assert get_url("") is None

    def test_chernogolovka(self) -> None:
        assert get_url("Черноголовка") == "https://journal.nschg.ru"
        assert get_url("черноголовка") == "https://journal.nschg.ru"

    def test_all_regions_findable(self) -> None:
        for name in REGIONS:
            assert get_url(name) == REGIONS[name], f"get_url({name!r}) не нашёл"

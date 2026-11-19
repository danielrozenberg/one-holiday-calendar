import datetime

from one_holiday_calendar import config_pb2
from one_holiday_calendar import sources


def _occurrences(**kwargs) -> list[sources.Occurrence]:
    return list(sources.occurrences(config_pb2.Source(**kwargs), [2026]))


def _find(occurrences, name) -> list[sources.Occurrence]:
    return [o for o in occurrences if o.name == name]


def test_national_only_by_default():
    found = _occurrences(country="CA")

    assert _find(found, "Canada Day") == [
        sources.Occurrence(
            datetime.date(2026, 7, 1), "Canada Day", "CA", "", "public"
        )
    ]
    assert not _find(found, "Family Day")


def test_subdivision_adds_only_regional_holidays():
    found = _occurrences(country="CA", subdivisions=["ON"])

    assert [o.subdivision for o in _find(found, "Family Day")] == ["ON"]
    assert [o.subdivision for o in _find(found, "Canada Day")] == [""]


def test_all_subdivisions():
    found = _occurrences(country="CA", all_subdivisions=True)

    assert {o.subdivision for o in _find(found, "Family Day")} >= {"ON", "AB"}


def test_categories():
    found = _occurrences(country="US", categories=["government"])

    assert found
    assert {o.category for o in found} == {"government"}


def test_names_are_english_when_supported():
    found = _occurrences(country="DE")

    assert _find(found, "Christmas Day")


def test_flag():
    assert sources.flag("CA") == "\U0001f1e8\U0001f1e6"
    assert sources.flag("Jewish") == "✡️"


def test_english_prefers_the_countrys_own_variant():
    assert sources.english("CA") == "en_CA"
    assert sources.english("DE") == "en_US"
    assert sources.english("JM") is None


def test_country_names_keep_small_words_lowercase():
    names = sources.country_names()

    assert names["BA"] == "Bosnia and Herzegovina"
    assert names["IM"] == "Isle of Man"
    assert names["VC"] == "Saint Vincent and the Grenadines"
    assert names["HM"] == "Heard Island and McDonald Islands"
    assert names["AG"] == "Antigua and Barbuda"

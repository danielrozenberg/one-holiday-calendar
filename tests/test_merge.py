import datetime

import pytest

from holidaycal import config_pb2
from holidaycal import merge


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("New Year's Day", "new years day"),
        ("Christmas Day (observed)", "christmas day"),
        ("Eid al-Fitr (estimated)", "eid al fitr"),
        ("Eid-ul-Fitr", "eid al fitr"),
        ("Labour Day", "labor day"),
        ("International Workers' Day", "labor day"),
    ],
)
def test_normalize(name, key):
    assert merge.normalize(name) == key


def test_aliases_are_sorted():
    keys = list(merge._aliases())

    assert keys == sorted(keys)


def _build(*sources: config_pb2.Source) -> list[merge.Event]:
    return merge.build(config_pb2.Config(sources=sources), [2026])


def _on(events, month, day) -> list[merge.Event]:
    return [e for e in events if e.date == datetime.date(2026, month, day)]


def test_christmas_merges_across_countries():
    events = _build(
        config_pb2.Source(country="CA"),
        config_pb2.Source(country="US"),
        config_pb2.Source(country="DE"),
    )

    [christmas] = _on(events, 12, 25)
    assert christmas.name == "Christmas Day"
    assert {o.source for o in christmas.occurrences} == {"CA", "US", "DE"}


def test_labour_day_merges_with_labor_day():
    events = _build(
        config_pb2.Source(country="US"),
        config_pb2.Source(country="CA"),
    )

    [labor_day] = _on(events, 9, 7)
    assert {o.source for o in labor_day.occurrences} == {"US", "CA"}


def test_excluded_holidays_are_dropped_per_source():
    events = _build(
        config_pb2.Source(country="CA", excluded=["christmas day"]),
        config_pb2.Source(country="US"),
    )

    [christmas] = _on(events, 12, 25)
    assert {o.source for o in christmas.occurrences} == {"US"}


def test_uid_is_stable_and_depends_on_key():
    first = _build(config_pb2.Source(country="US"))
    second = _build(config_pb2.Source(country="CA"))

    [us_christmas] = _on(first, 12, 25)
    [ca_christmas] = _on(second, 12, 25)
    assert us_christmas.uid == ca_christmas.uid
    assert len({e.uid for e in first}) == len(first)


def _passover(combine: bool) -> list[merge.Event]:
    config = config_pb2.Config(
        sources=[config_pb2.Source(religion="jewish")],
        combine_multiday=combine,
    )
    return [e for e in merge.build(config, [2026]) if e.key == "passover"]


def test_multiday_holidays_stay_separate_by_default():
    assert [e.days for e in _passover(combine=False)] == [1] * 8


def test_combine_multiday():
    [passover] = _passover(combine=True)

    assert passover.date == datetime.date(2026, 4, 2)
    assert passover.days == 8
    assert passover.end == datetime.date(2026, 4, 10)
    assert len(passover.occurrences) == 8


def test_combine_multiday_keeps_observed_days_apart():
    config = config_pb2.Config(
        sources=[config_pb2.Source(country="US")], combine_multiday=True
    )
    events = merge.build(config, [2027])

    christmas = [e for e in events if e.key == "christmas day"]
    assert [(e.date.day, e.days) for e in christmas] == [(24, 1), (25, 1)]


def test_aliases_are_normalized_and_never_chain():
    aliases = merge._aliases()

    for key, value in aliases.items():
        assert merge.unaliased(key) == key
        assert merge.unaliased(value) == value
        assert value not in aliases


@pytest.mark.parametrize(
    ("order", "name"),
    [(["US", "CA"], "Labor Day"), (["CA", "US"], "Labour Day")],
)
def test_name_comes_from_the_first_source(order, name):
    events = _build(*(config_pb2.Source(country=c) for c in order))

    [labor_day] = _on(events, 9, 7)
    assert labor_day.name == name


def test_regional_variants_merge_into_the_national_holiday():
    events = _build(config_pb2.Source(country="US", all_subdivisions=True))

    [mlk_day] = [
        e
        for e in events
        if e.date == datetime.date(2026, 1, 19)
        and e.key == "martin luther king jr day"
    ]
    assert mlk_day.name == "Martin Luther King Jr. Day"
    assert len({o.name for o in mlk_day.occurrences}) > 1


def test_religion_names_merge_with_country_names():
    events = _build(
        config_pb2.Source(country="AR", categories=["hebrew"]),
        config_pb2.Source(religion="jewish"),
    )

    [passover] = [e for e in _on(events, 4, 2) if e.key == "passover"]
    assert passover.name == "Pesach"
    assert {o.source for o in passover.occurrences} == {"AR", "Jewish"}


def test_hidden_unaliased_name_stays_hidden():
    events = _build(
        config_pb2.Source(country="CA", excluded=["labour day"]),
    )

    assert not _on(events, 9, 7)

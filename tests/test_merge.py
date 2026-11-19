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

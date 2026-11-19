import datetime
import re

import pytest

from holidaycal import config_pb2
from holidaycal import merge
from holidaycal import sources


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("New Year's Day", "new years day"),
        ("Christmas Day (observed)", "christmas_day"),
        ("Eid al-Fitr (estimated)", "eid_al_fitr"),
        ("Eid-ul-Fitr", "eid_al_fitr"),
        ("Labour Day", "labor_day"),
        ("International Workers' Day", "labor_day"),
    ],
)
def test_normalize(name, key):
    assert merge.normalize(name) == key


def test_alias_ids_are_sorted_snake_case():
    ids = list(merge.alias_groups())

    assert ids == sorted(ids)
    assert all(re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", i) for i in ids)


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


def test_hidden_holidays_are_dropped_for_every_source():
    parsed = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA"),
            config_pb2.Source(country="US"),
        ],
        hidden=["CA:christmas_day", "US:christmas_day", "US:labor_day"],
    )

    assert not _on(merge.build(parsed, [2026]), 12, 25)
    [labor_day] = _on(merge.build(parsed, [2026]), 9, 7)
    assert {o.source for o in labor_day.occurrences} == {"CA"}
    assert _on(merge.build(parsed, [2026], include_hidden=True), 12, 25)


def test_hiding_is_per_source():
    parsed = config_pb2.Config(
        sources=[
            config_pb2.Source(country="US"),
            config_pb2.Source(country="PH"),
            config_pb2.Source(religion="christian"),
        ],
        hidden=["US:independence day", "@christian:christmas_day"],
    )
    events = merge.build(parsed, [2026])

    assert not _on(events, 7, 4)
    assert [e.name for e in _on(events, 6, 12)] == ["Independence Day"]
    [christmas] = _on(events, 12, 25)
    assert {o.source for o in christmas.occurrences} == {"US", "PH"}


def test_event_is_hidden_when_every_source_is():
    parsed = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA"),
            config_pb2.Source(country="US"),
        ]
    )
    [christmas] = _on(merge.build(parsed, [2026]), 12, 25)

    assert merge.hide_tokens(christmas) == [
        "CA:christmas_day",
        "US:christmas_day",
    ]
    assert not merge.is_hidden(christmas, {"CA:christmas_day"})
    assert merge.is_hidden(christmas, set(merge.hide_tokens(christmas)))


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

    christmas = [e for e in events if e.key == "christmas_day"]
    assert [(e.date.day, e.days) for e in christmas] == [(24, 1), (25, 1)]


def test_alias_names_are_normalized_and_unique():
    names = [
        name
        for tiers in merge.alias_groups().values()
        for tier in tiers
        for name in tier
    ]

    assert all(merge.unaliased(name) == name for name in names)
    assert len(names) == len(set(names))


def _occurrence(name: str, source: str) -> sources.Occurrence:
    return sources.Occurrence(
        datetime.date(2026, 12, 24), name, source, "", "public"
    )


def test_earlier_tier_name_wins_over_source_order():
    [event] = merge.merge(
        [
            _occurrence("Christmas Eve (from 12pm)", "US"),
            _occurrence("Christmas Eve", "DE"),
        ]
    )

    assert event.key == "christmas_eve"
    assert event.name == "Christmas Eve"


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
        and e.key == "martin_luther_king_jr_day"
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

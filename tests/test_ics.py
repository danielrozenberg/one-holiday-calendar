import datetime

import icalendar
import pytest

from one_holiday_calendar import config_pb2
from one_holiday_calendar import ics
from one_holiday_calendar import merge

NOW = datetime.datetime(2026, 11, 19, tzinfo=datetime.UTC)


def _render() -> icalendar.Calendar:
    config = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA"),
            config_pb2.Source(country="US"),
        ]
    )
    events = merge.build(config, ics.years(NOW.date()))
    return icalendar.Calendar.from_ical(ics.render(events, config, NOW))


def test_years():
    assert list(ics.years(datetime.date(2026, 11, 19))) == [
        2025,
        2026,
        2027,
        2028,
    ]


def test_render_all_day_events():
    calendar = _render()

    christmas = [
        e
        for e in calendar.walk("VEVENT")
        if e.decoded("dtstart") == datetime.date(2026, 12, 25)
    ]
    assert len(christmas) == 1
    assert christmas[0]["summary"] == "Christmas Day"
    assert christmas[0].decoded("dtend") == datetime.date(2026, 12, 26)


def test_render_is_stable():
    first = [e["uid"] for e in _render().walk("VEVENT")]
    second = [e["uid"] for e in _render().walk("VEVENT")]

    assert first == second
    assert len(set(first)) == len(first)


def _christmas(**kwargs) -> tuple[merge.Event, config_pb2.Config]:
    config = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA", subdivisions=["ON"]),
            config_pb2.Source(country="US"),
            config_pb2.Source(religion="christian"),
        ],
        **kwargs,
    )
    [event] = [
        e
        for e in merge.build(config, [2026])
        if e.date == datetime.date(2026, 12, 25)
    ]
    return event, config


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (config_pb2.TITLE_STYLE_PLAIN, "Christmas Day"),
        (
            config_pb2.TITLE_STYLE_PREFIX_CODES,
            "[CA, US, Christian] Christmas Day",
        ),
        (
            config_pb2.TITLE_STYLE_PREFIX_NAMES,
            "[Canada, United States, Christian] Christmas Day",
        ),
        (
            config_pb2.TITLE_STYLE_SUFFIX_CODES,
            "Christmas Day [CA, US, Christian]",
        ),
        (
            config_pb2.TITLE_STYLE_SUFFIX_NAMES,
            "Christmas Day [Canada, United States, Christian]",
        ),
        (config_pb2.TITLE_STYLE_PREFIX_FLAGS, "🇨🇦🇺🇸✝️ Christmas Day"),
        (config_pb2.TITLE_STYLE_SUFFIX_FLAGS, "Christmas Day 🇨🇦🇺🇸✝️"),
    ],
)
def test_title(style, expected):
    event, _ = _christmas()

    assert ics.title(event, style) == expected


def test_description():
    event, config = _christmas(describe_sources=True, describe_categories=True)

    assert ics.description(event, config) == (
        "Observed in: Canada, United States, Christian\n"
        "Types: public, religious"
    )


def test_description_lists_regions_of_regional_holidays():
    config = config_pb2.Config(
        sources=[config_pb2.Source(country="CA", subdivisions=["ON", "AB"])],
        describe_sources=True,
    )
    [family_day] = [
        e for e in merge.build(config, [2026]) if e.key == "family day"
    ]

    assert ics.description(family_day, config) == (
        "Observed in: Canada (AB, ON)"
    )


def test_description_is_empty_by_default():
    event, config = _christmas()

    assert ics.description(event, config) == ""


def test_multiday_event_spans_its_days():
    config = config_pb2.Config(
        sources=[config_pb2.Source(religion="jewish")], combine_multiday=True
    )
    events = merge.build(config, [2026])
    calendar = icalendar.Calendar.from_ical(ics.render(events, config, NOW))

    [passover] = [
        e for e in calendar.walk("VEVENT") if e["summary"] == "Passover"
    ]
    assert passover.decoded("dtstart") == datetime.date(2026, 4, 2)
    assert passover.decoded("dtend") == datetime.date(2026, 4, 10)

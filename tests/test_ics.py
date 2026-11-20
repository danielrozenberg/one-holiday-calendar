import datetime

import icalendar
import pytest

from one_holiday_calendar import config_pb2
from one_holiday_calendar import ics
from one_holiday_calendar import merge

NOW = datetime.datetime(2026, 11, 19, tzinfo=datetime.UTC)
PAGE_URL = "https://example.com/c/blob"


def _render() -> icalendar.Calendar:
    config = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA"),
            config_pb2.Source(country="US"),
        ]
    )
    events = merge.build(config, ics.years(NOW.date()))
    return icalendar.Calendar.from_ical(
        ics.render(events, config, NOW, PAGE_URL)
    )


def test_years():
    years = ics.years(datetime.date(2026, 11, 19))
    assert (years.start, years.stop) == (2016, 2057)


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
    calendar = icalendar.Calendar.from_ical(
        ics.render(events, config, NOW, PAGE_URL)
    )

    [passover] = [
        e for e in calendar.walk("VEVENT") if e["summary"] == "Passover"
    ]
    assert passover.decoded("dtstart") == datetime.date(2026, 4, 2)
    assert passover.decoded("dtend") == datetime.date(2026, 4, 10)


def _global_christmas() -> merge.Event:
    config = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA"),
            config_pb2.Source(country="US"),
            config_pb2.Source(country="DE"),
            config_pb2.Source(religion="christian"),
        ]
    )
    [event] = [
        e
        for e in merge.build(config, [2026])
        if e.date == datetime.date(2026, 12, 25)
    ]
    return event


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (config_pb2.TITLE_STYLE_PREFIX_CODES, "[Global] Christmas Day"),
        (config_pb2.TITLE_STYLE_SUFFIX_NAMES, "Christmas Day [Global]"),
        (config_pb2.TITLE_STYLE_PREFIX_FLAGS, "\U0001f30d Christmas Day"),
    ],
)
def test_title_says_global_from_four_sources(style, expected):
    assert ics.title(_global_christmas(), style) == expected


def test_description_says_global_from_four_sources():
    lines = ics.description_lines(_global_christmas())

    assert lines["sources"] == "Observed in: Global"


def test_calendar_links_to_its_config_page():
    calendar = _render()

    assert calendar["url"] == PAGE_URL
    assert PAGE_URL in str(calendar["description"])
    assert PAGE_URL in str(calendar["x-wr-caldesc"])


def test_refresh_hints_are_durations():
    text = ics.render([], config_pb2.Config(), NOW, PAGE_URL).decode()

    assert "REFRESH-INTERVAL;VALUE=DURATION:P1D\r\n" in text
    assert "X-PUBLISHED-TTL:P1D\r\n" in text

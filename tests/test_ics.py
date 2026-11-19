import datetime

import icalendar

from holidaycal import config_pb2
from holidaycal import ics
from holidaycal import merge

NOW = datetime.datetime(2026, 11, 19, tzinfo=datetime.UTC)


def _render() -> icalendar.Calendar:
    config = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA"),
            config_pb2.Source(country="US"),
        ]
    )
    events = merge.build(config, ics.years(NOW.date()))
    return icalendar.Calendar.from_ical(ics.render(events, NOW))


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

"""Rendering of merged events as an iCalendar feed."""

import datetime
from collections.abc import Iterable

import icalendar

from holidaycal import merge

CALENDAR_NAME = "Holidays"
REFRESH = datetime.timedelta(days=1)


def years(today: datetime.date) -> range:
    """Returns the years a feed covers: last year to the year after next."""
    return range(today.year - 1, today.year + 3)


def render(events: Iterable[merge.Event], now: datetime.datetime) -> bytes:
    """Renders events as all-day VEVENTs in a VCALENDAR."""
    calendar = icalendar.Calendar()
    calendar.add("prodid", "-//holidaycal//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", CALENDAR_NAME)
    calendar.add("refresh-interval", REFRESH, parameters={"VALUE": "DURATION"})
    calendar.add("x-published-ttl", REFRESH)
    for event in events:
        vevent = icalendar.Event()
        vevent.add("uid", event.uid)
        vevent.add("dtstamp", now)
        vevent.add("dtstart", event.date)
        vevent.add("dtend", event.date + datetime.timedelta(days=1))
        vevent.add("summary", event.name)
        vevent.add("transp", "TRANSPARENT")
        calendar.add_component(vevent)
    return calendar.to_ical()

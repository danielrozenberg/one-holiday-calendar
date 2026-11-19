"""Rendering of merged events as an iCalendar feed."""

import datetime
from collections.abc import Iterable

import icalendar

from one_holiday_calendar import config_pb2
from one_holiday_calendar import merge
from one_holiday_calendar import settings
from one_holiday_calendar import sources


def years(today: datetime.date) -> range:
    """Returns the years a feed covers around the current one."""
    feed = settings.CURRENT.feed
    return range(
        today.year - feed.years_before, today.year + feed.years_after + 1
    )


def title(event: merge.Event, style: config_pb2.TitleStyle.ValueType) -> str:
    """Formats an event's title in the configured style."""
    codes = list(dict.fromkeys(o.source for o in event.occurrences))
    names = ", ".join(map(sources.source_name, codes))
    flags = "".join(map(sources.flag, codes))
    match style:
        case config_pb2.TITLE_STYLE_PREFIX_CODES:
            return f"[{', '.join(codes)}] {event.name}"
        case config_pb2.TITLE_STYLE_SUFFIX_CODES:
            return f"{event.name} [{', '.join(codes)}]"
        case config_pb2.TITLE_STYLE_PREFIX_NAMES:
            return f"[{names}] {event.name}"
        case config_pb2.TITLE_STYLE_SUFFIX_NAMES:
            return f"{event.name} [{names}]"
        case config_pb2.TITLE_STYLE_PREFIX_FLAGS:
            return f"{flags} {event.name}"
        case config_pb2.TITLE_STYLE_SUFFIX_FLAGS:
            return f"{event.name} {flags}"
        case _:
            return event.name


def description_lines(event: merge.Event) -> dict[str, str]:
    """Returns every description line an event can have, by option."""
    regions: dict[str, list[str]] = {}
    for o in event.occurrences:
        regions.setdefault(o.source, []).append(o.subdivision)
    categories = dict.fromkeys(o.category for o in event.occurrences)
    return {
        "sources": "Observed in: "
        + ", ".join(
            _with_regions(code, subdivisions)
            for code, subdivisions in regions.items()
        ),
        "categories": "Types: " + ", ".join(categories).replace("_", " "),
    }


def description(event: merge.Event, parsed: config_pb2.Config) -> str:
    """Lists the event's sources and categories, as configured."""
    enabled = {
        "sources": parsed.describe_sources,
        "categories": parsed.describe_categories,
    }
    lines = description_lines(event)
    return "\n".join(line for key, line in lines.items() if enabled[key])


def _with_regions(code: str, subdivisions: list[str]) -> str:
    name = sources.source_name(code)
    if "" in subdivisions:
        return name
    return f"{name} ({', '.join(sorted(set(subdivisions)))})"


def render(
    events: Iterable[merge.Event],
    parsed: config_pb2.Config,
    now: datetime.datetime,
) -> bytes:
    """Renders events as all-day VEVENTs in a VCALENDAR."""
    calendar = icalendar.Calendar()
    calendar.add("prodid", "-//one-holiday-calendar//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    feed = settings.CURRENT.feed
    refresh = datetime.timedelta(hours=feed.refresh_hours)
    calendar.add("x-wr-calname", feed.calendar_name)
    calendar.add("refresh-interval", refresh, parameters={"VALUE": "DURATION"})
    calendar.add("x-published-ttl", refresh)
    for event in events:
        vevent = icalendar.Event()
        vevent.add("uid", event.uid)
        vevent.add("dtstamp", now)
        vevent.add("dtstart", event.date)
        vevent.add("dtend", event.end)
        vevent.add("summary", title(event, parsed.title_style))
        if text := description(event, parsed):
            vevent.add("description", text)
        vevent.add("transp", "TRANSPARENT")
        calendar.add_component(vevent)
    return calendar.to_ical()

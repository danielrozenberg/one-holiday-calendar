"""Holiday occurrences produced by each configured source."""

import dataclasses
import datetime
from collections.abc import Iterable, Iterator

import holidays

from holidaycal import config_pb2
from holidaycal import religions

LANGUAGE = "en_US"
DEFAULT_CATEGORY = "public"
RELIGIOUS_CATEGORY = "religious"


@dataclasses.dataclass(frozen=True)
class Occurrence:
    """A single holiday on a single date, as reported by one source."""

    date: datetime.date
    name: str
    source: str
    subdivision: str
    category: str


def occurrences(
    source: config_pb2.Source, years: Iterable[int]
) -> Iterator[Occurrence]:
    """Yields every holiday a source contributes in the given years."""
    years = list(years)
    match source.WhichOneof("kind"):
        case "country":
            yield from _country_occurrences(source, years)
        case "religion":
            label, calendar = religions.RELIGIONS[source.religion]
            yield from _emit(
                calendar(years=years), label, "", RELIGIOUS_CATEGORY, None
            )
        case None:
            raise ValueError("Source has no kind")


def _country_occurrences(
    source: config_pb2.Source, years: list[int]
) -> Iterator[Occurrence]:
    code = source.country
    subdivisions = (
        holidays.country_holidays(code).subdivisions
        if source.all_subdivisions
        else source.subdivisions
    )
    for category in source.categories or [DEFAULT_CATEGORY]:
        national = _holidays(code, None, years, category)
        yield from _emit(national, code, "", category, exclude=None)
        for subdivision in subdivisions:
            regional = _holidays(code, subdivision, years, category)
            yield from _emit(regional, code, subdivision, category, national)


def _holidays(
    code: str, subdivision: str | None, years: list[int], category: str
) -> holidays.HolidayBase:
    supported = holidays.country_holidays(code).supported_languages
    return holidays.country_holidays(
        code,
        subdiv=subdivision,
        years=years,
        categories=category,
        language=LANGUAGE if LANGUAGE in supported else None,
    )


def _emit(
    calendar: holidays.HolidayBase,
    source: str,
    subdivision: str,
    category: str,
    exclude: holidays.HolidayBase | None,
) -> Iterator[Occurrence]:
    for date in sorted(calendar):
        already = exclude.get_list(date) if exclude is not None else []
        for name in calendar.get_list(date):
            if name not in already:
                yield Occurrence(date, name, source, subdivision, category)

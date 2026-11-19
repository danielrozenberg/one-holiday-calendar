"""Holiday occurrences produced by each configured source."""

import dataclasses
import datetime
import functools
import re
from collections.abc import Iterable, Iterator

import holidays
from holidays import registry

from one_holiday_calendar import config_pb2
from one_holiday_calendar import religions

FALLBACK_LANGUAGE = "en_US"
DEFAULT_CATEGORY = "public"
RELIGION_PREFIX = "@"
RELIGIOUS_CATEGORY = "religious"
_SMALL_WORDS = re.compile(r"(?<= )(?:And|Of|The|Da)\b")
_MC = re.compile(r"\bMc(\w)")


@functools.cache
def country_names() -> dict[str, str]:
    """Returns English country names by code, sorted by name."""
    names = {
        code: _title(key.replace("_", " "))
        for key, (_, code, *_) in registry.COUNTRIES.items()
    }
    return dict(sorted(names.items(), key=lambda item: item[1]))


def _title(name: str) -> str:
    name = _SMALL_WORDS.sub(lambda m: m[0].lower(), name.title())
    return _MC.sub(lambda m: "Mc" + m[1].upper(), name)


def source_name(source: str) -> str:
    """Returns the display name of an occurrence's source."""
    return country_names().get(source, source)


def source_id(source: str) -> str:
    """Returns an occurrence's source as configured: "CA" or "@christian"."""
    for key, religion in religions.RELIGIONS.items():
        if religion.label == source:
            return RELIGION_PREFIX + key
    return source


def flag(source: str) -> str:
    """Returns a flag emoji for a country, or a religion's symbol."""
    for religion in religions.RELIGIONS.values():
        if religion.label == source:
            return religion.symbol
    if len(source) == 2 and source.isascii() and source.isalpha():
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in source.upper())
    return source


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
            religion = religions.RELIGIONS[source.religion]
            yield from _emit(
                religion.calendar(years=years),
                religion.label,
                "",
                RELIGIOUS_CATEGORY,
                None,
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
    return holidays.country_holidays(
        code,
        subdiv=subdivision,
        years=years,
        categories=category,
        language=english(code),
    )


@functools.cache
def english(code: str) -> str | None:
    """Picks the country's own English if available, else US English.

    Returns None for countries without translations, whose names are already
    in English.
    """
    supported = holidays.country_holidays(code).supported_languages
    for language in (f"en_{code}", FALLBACK_LANGUAGE):
        if language in supported:
            return language
    return None


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

"""Merging of holiday occurrences from many sources into single events."""

import collections
import dataclasses
import datetime
import functools
import hashlib
import importlib.resources
import re
import tomllib
from collections.abc import Collection, Iterable

from one_holiday_calendar import config_pb2
from one_holiday_calendar import sources

_MARKERS = re.compile(r"\([^)]*\b(?:observed|estimated)\b[^)]*\)")
_APOSTROPHES = re.compile(r"['\u2019]")
_NON_WORD = re.compile(r"[^\w]+")


@dataclasses.dataclass(frozen=True)
class Event:
    """One calendar event, merged from every occurrence sharing its key."""

    date: datetime.date
    key: str
    name: str
    occurrences: tuple[sources.Occurrence, ...]
    days: int = 1

    @property
    def end(self) -> datetime.date:
        """The day after the event's last day."""
        return self.date + datetime.timedelta(days=self.days)

    @property
    def uid(self) -> str:
        """A stable identifier derived from the merge key."""
        digest = hashlib.sha1(f"{self.date}|{self.key}".encode()).hexdigest()
        return f"{digest}@one-holiday-calendar"


def normalize(name: str) -> str:
    """Returns the merge key of a holiday name: its holiday id if aliased."""
    key = unaliased(name)
    return _aliases().get(key, (key, 0))[0]


def _tier(name: str) -> int:
    """Returns how preferred a name is among its holiday's names; 0 is best."""
    return _aliases().get(unaliased(name), ("", 0))[1]


def hide_token(occurrence: sources.Occurrence) -> str:
    """Identifies a holiday from one source and region.

    E.g. "US:independence day" nationally, "US/PR:emancipation_day" in Puerto
    Rico. Hiding is per source and region because the same merge key can be a
    different holiday elsewhere: every country's "Independence Day", or
    Emancipation Day in Puerto Rico, DC and the Virgin Islands.
    """
    source = sources.source_id(occurrence.source)
    if occurrence.subdivision:
        source = f"{source}/{occurrence.subdivision}"
    return f"{source}:{normalize(occurrence.name)}"


def hidden_source(token: str) -> str:
    """Returns the configured source a hide token belongs to, e.g. "US"."""
    return token.partition(":")[0].partition("/")[0]


def hide_tokens(event: "Event") -> list[str]:
    """Returns the hide tokens of every source contributing to an event."""
    return sorted({hide_token(o) for o in event.occurrences})


def is_hidden(event: "Event", hidden: Collection[str]) -> bool:
    """Whether every source's contribution to an event is hidden."""
    return all(token in hidden for token in hide_tokens(event))


def unaliased(name: str) -> str:
    """Returns a holiday name's merge key before aliases are applied."""
    name = _MARKERS.sub(" ", name.lower())
    name = _APOSTROPHES.sub("", name)
    return _NON_WORD.sub(" ", name).strip()


@functools.cache
def alias_groups() -> dict[str, list[list[str]]]:
    """Returns each aliased holiday's names, by holiday id, as ranked tiers."""
    text = importlib.resources.files(__package__).joinpath("aliases.toml")
    return tomllib.loads(text.read_text(encoding="utf-8"))["aliases"]


@functools.cache
def _aliases() -> dict[str, tuple[str, int]]:
    return {
        name: (holiday, tier)
        for holiday, tiers in alias_groups().items()
        for tier, names in enumerate(tiers)
        for name in names
    }


def build(
    config: config_pb2.Config,
    years: Iterable[int],
    *,
    include_hidden: bool = False,
) -> list[Event]:
    """Collects every configured source's holidays and merges them.

    Occurrences whose `hide_token` is in `config.hidden` are left out unless
    `include_hidden` is set.
    """
    years = list(years)
    hidden = set() if include_hidden else set(config.hidden)
    events = merge(
        o
        for source in config.sources
        for o in sources.occurrences(source, years)
        if hide_token(o) not in hidden
    )
    return combine_multiday(events) if config.combine_multiday else events


def merge(occurrences: Iterable[sources.Occurrence]) -> list[Event]:
    """Groups occurrences by date and normalized name, sorted by date.

    Each event takes the most preferred name among its occurrences (see
    `aliases.toml`); ties go to the earliest, which follows the order of the
    configured sources.
    """
    groups: dict[tuple[datetime.date, str], list[sources.Occurrence]] = (
        collections.defaultdict(list)
    )
    for occurrence in occurrences:
        groups[occurrence.date, normalize(occurrence.name)].append(occurrence)
    return [
        Event(
            date,
            key,
            min(group, key=lambda o: _tier(o.name)).name,
            tuple(group),
        )
        for (date, key), group in sorted(groups.items())
    ]


def combine_multiday(events: Iterable[Event]) -> list[Event]:
    """Joins same-named events on consecutive days into one, sorted by date."""
    positions: dict[tuple[str, str], int] = {}
    combined: list[Event] = []
    for event in sorted(events, key=lambda e: e.date):
        position = positions.get((event.key, event.name))
        if position is not None and combined[position].end == event.date:
            run = combined[position]
            combined[position] = dataclasses.replace(
                run,
                occurrences=run.occurrences + event.occurrences,
                days=run.days + 1,
            )
        else:
            positions[event.key, event.name] = len(combined)
            combined.append(event)
    return combined

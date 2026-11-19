"""Merging of holiday occurrences from many sources into single events."""

import collections
import dataclasses
import datetime
import functools
import hashlib
import importlib.resources
import re
import tomllib
from collections.abc import Iterable

from holidaycal import config_pb2
from holidaycal import sources

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
        return f"{digest}@holidaycal"


def normalize(name: str) -> str:
    """Returns the merge key of a holiday name."""
    name = _MARKERS.sub(" ", name.lower())
    name = _APOSTROPHES.sub("", name)
    name = _NON_WORD.sub(" ", name).strip()
    return _aliases().get(name, name)


@functools.cache
def _aliases() -> dict[str, str]:
    text = importlib.resources.files(__package__).joinpath("aliases.toml")
    return tomllib.loads(text.read_text(encoding="utf-8"))["aliases"]


def build(config: config_pb2.Config, years: Iterable[int]) -> list[Event]:
    """Collects every configured source's holidays and merges them."""
    years = list(years)
    found: list[sources.Occurrence] = []
    for source in config.sources:
        excluded = set(source.excluded)
        found.extend(
            o
            for o in sources.occurrences(source, years)
            if normalize(o.name) not in excluded
        )
    events = merge(found)
    return combine_multiday(events) if config.combine_multiday else events


def merge(occurrences: Iterable[sources.Occurrence]) -> list[Event]:
    """Groups occurrences by date and normalized name, sorted by date."""
    groups: dict[tuple[datetime.date, str], list[sources.Occurrence]] = (
        collections.defaultdict(list)
    )
    for occurrence in occurrences:
        groups[occurrence.date, normalize(occurrence.name)].append(occurrence)
    return [
        Event(date, key, _display_name(group), tuple(group))
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


def _display_name(group: list[sources.Occurrence]) -> str:
    counts = collections.Counter(o.name for o in group)
    return min(counts, key=lambda name: (-counts[name], len(name), name))

"""Translation between the config page's form and `Config`."""

import dataclasses
import datetime
import functools
import re
import typing
from collections.abc import Collection

import holidays
from werkzeug import datastructures

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import ics
from holidaycal import merge
from holidaycal import religions
from holidaycal import sources

_KIND_FIELD = re.compile(r"s(\d+)\.kind")


@dataclasses.dataclass(frozen=True)
class Option:
    """A checkbox or select option."""

    value: str
    label: str
    checked: bool = False


@dataclasses.dataclass(frozen=True)
class HiddenNotice:
    """A notice that all of a source's holidays, or a part of them, are hidden.

    Its button submits `action=value` to drop that part from the config.
    """

    message: str
    action: str
    value: str
    button: str


@dataclasses.dataclass(frozen=True)
class SourceView:
    """Everything the page needs to render one configured source."""

    index: int
    kind: str
    label: str
    all_subdivisions: bool
    subdivisions: list[Option]
    categories: list[Option]
    notices: list[HiddenNotice]


_TYPE_LETTERS = {
    "armed_forces": "A",
    "bank": "B",
    "de_facto": "D",
    "government": "G",
    "half_day": "\u00bd",
    "optional": "O",
    "public": "P",
    sources.RELIGIOUS_CATEGORY: "R",
    "school": "S",
    "unofficial": "U",
    "workday": "W",
}


@dataclasses.dataclass(frozen=True)
class SourceBadge:
    """A source's flag or symbol and the regions an event applies to."""

    flag: str
    name: str
    regions: list[str]
    region_names: list[str]

    @property
    def label(self) -> str:
        """The full description, for tooltips and screen readers."""
        if not self.region_names:
            return self.name
        return f"{self.name}: {', '.join(self.region_names)}"


@dataclasses.dataclass(frozen=True)
class TypeBadge:
    """A holiday category as a single letter, with its name for tooltips."""

    letter: str
    name: str


class Card(typing.TypedDict):
    """The event format card's content, sent to the page as JSON."""

    uid: str
    titles: dict[str, str]
    date: str
    sources: str
    categories: str


@dataclasses.dataclass(frozen=True)
class EventView:
    """Everything the preview needs to render one event."""

    event: merge.Event
    sources: list[SourceBadge]
    types: list[TypeBadge]
    hidden: bool = False
    toggle: str = ""

    @property
    def short_date(self) -> str:
        """The event's date, or date range, in as few characters as possible."""
        first = self.event.date
        if self.event.days == 1:
            return f"{first:%a, %b %-d}"
        last = self.event.end - datetime.timedelta(days=1)
        if last.month == first.month:
            return f"{first:%b %-d}\u2013{last:%-d}"
        return f"{first:%b %-d}\u2013{last:%b %-d}"

    @property
    def card(self) -> Card:
        """The event card's content for this event, in every title style."""
        event = self.event
        lines = ics.description_lines(event)
        return Card(
            uid=event.uid,
            titles={
                name: ics.title(event, value)
                for name, value in config_pb2.TitleStyle.items()
            },
            date=_long_date(event),
            sources=lines["sources"],
            categories=lines["categories"],
        )


def event_view(event: merge.Event, hidden: Collection[str] = ()) -> EventView:
    """Describes an event's sources, regions and categories for display."""
    regions: dict[str, set[str]] = {}
    for o in event.occurrences:
        regions.setdefault(o.source, set()).add(o.subdivision)
    badges = []
    for code, subdivisions in regions.items():
        regional = [] if "" in subdivisions else sorted(subdivisions)
        names = subdivision_names(code) if regional else {}
        badges.append(
            SourceBadge(
                flag=sources.flag(code),
                name=sources.source_name(code),
                regions=regional,
                region_names=[names.get(r, r) for r in regional],
            )
        )
    categories = dict.fromkeys(o.category for o in event.occurrences)
    return EventView(
        event=event,
        hidden=merge.is_hidden(event, hidden),
        toggle="|".join(merge.hide_tokens(event)),
        sources=badges,
        types=[
            TypeBadge(
                _TYPE_LETTERS.get(category, category[:1].upper()),
                category.replace("_", " "),
            )
            for category in categories
        ],
    )


def representative(views: list[EventView]) -> EventView | None:
    """Picks the event that shows off the most formatting options."""
    return max(
        views,
        key=lambda v: (
            len(v.sources),
            sum(len(s.regions) for s in v.sources),
            len(v.types),
        ),
        default=None,
    )


def sample_event(year: int) -> merge.Event:
    """An example event for the card when no holidays are selected."""
    date = datetime.date(year, 12, 24)
    occurrences = (
        sources.Occurrence(date, "Christmas Eve", "CA", "", "optional"),
        sources.Occurrence(date, "Christmas Eve", "US", "", "optional"),
        sources.Occurrence(
            date, "Christmas Eve", "Christian", "", sources.RELIGIOUS_CATEGORY
        ),
    )
    return merge.Event(date, "christmas eve", "Christmas Eve", occurrences)


def _long_date(event: merge.Event) -> str:
    first = event.date
    if event.days == 1:
        return first.strftime("%A, %B %-d, %Y")
    last = event.end - datetime.timedelta(days=1)
    return f"{first:%a, %b %-d} \u2013 {last:%a, %b %-d, %Y}"


@functools.cache
def subdivision_names(country: str) -> dict[str, str]:
    """Returns subdivision names by code, falling back to the code."""
    calendar = holidays.country_holidays(country)
    names: dict[str, str] = {}
    for name, code in calendar.subdivisions_aliases.items():
        names.setdefault(code, name)
    return {code: names.get(code, code) for code in calendar.subdivisions}


def parse(form: datastructures.MultiDict[str, str]) -> config_pb2.Config:
    """Builds a validated config from submitted form fields.

    Raises:
        config.InvalidConfigError: The form describes an unsupported config.
    """
    removed = form.get("remove")
    try:
        title_style = config_pb2.TitleStyle.Value(
            form.get("title_style", "TITLE_STYLE_PLAIN")
        )
    except ValueError as e:
        raise config.InvalidConfigError("Unknown title style") from e
    parsed = config_pb2.Config(
        title_style=title_style,
        describe_sources=bool(form.get("describe_sources")),
        describe_categories=bool(form.get("describe_categories")),
        combine_multiday=bool(form.get("combine_multiday")),
        hidden=sorted(_hidden(form)),
    )
    indices = [
        match[1]
        for key in form
        if (match := _KIND_FIELD.fullmatch(key)) and match[1] != removed
    ]
    if move := form.get("move"):
        _move(indices, move)
    by_index = {
        index: _parse_source(form, f"s{index}.", form[f"s{index}.kind"])
        for index in indices
    }
    if drop := form.get("drop_region"):
        _drop_region(by_index, drop)
    if drop := form.get("drop_type"):
        _drop_type(by_index, drop)
    parsed.sources.extend(by_index.values())
    if added := form.get("add"):
        parsed.sources.append(_new_source(added))
    config.validate(parsed)
    return parsed


def _hidden(form: datastructures.MultiDict[str, str]) -> set[str]:
    if form.get("unhide_all"):
        return set()
    hidden = set(form.getlist("hidden"))
    if toggle := form.get("toggle_hidden"):
        tokens = set(toggle.split("|"))
        hidden = hidden - tokens if tokens <= hidden else hidden | tokens
    return hidden


def _target(
    by_index: dict[str, config_pb2.Source], value: str
) -> tuple[config_pb2.Source, str]:
    index, _, part = value.partition(":")
    if index not in by_index or not part:
        raise config.InvalidConfigError(f"Unknown source part {value}")
    return by_index[index], part


def _drop_region(by_index: dict[str, config_pb2.Source], value: str) -> None:
    source, region = _target(by_index, value)
    if source.all_subdivisions:
        source.all_subdivisions = False
        source.subdivisions.extend(subdivision_names(source.country))
    remaining = [code for code in source.subdivisions if code != region]
    source.ClearField("subdivisions")
    source.subdivisions.extend(remaining)


def _drop_type(by_index: dict[str, config_pb2.Source], value: str) -> None:
    source, category = _target(by_index, value)
    current = list(source.categories) or [sources.DEFAULT_CATEGORY]
    source.ClearField("categories")
    source.categories.extend(c for c in current if c != category)
    _default_categories(source)


def _move(indices: list[str], move: str) -> None:
    index, _, direction = move.partition(":")
    match direction:
        case "up":
            delta = -1
        case "down":
            delta = 1
        case _:
            raise config.InvalidConfigError(f"Unknown move {move}")
    if index not in indices:
        raise config.InvalidConfigError(f"Unknown source {index}")
    position = indices.index(index)
    target = position + delta
    if 0 <= target < len(indices):
        indices[position], indices[target] = indices[target], indices[position]


def _parse_source(
    form: datastructures.MultiDict[str, str], prefix: str, kind: str
) -> config_pb2.Source:
    source = _new_source(kind)
    source.subdivisions.extend(form.getlist(prefix + "subdivision"))
    source.all_subdivisions = bool(form.get(prefix + "all_subdivisions"))
    source.categories.extend(form.getlist(prefix + "category"))
    if source.all_subdivisions:
        source.ClearField("subdivisions")
    _default_categories(source)
    return source


def _default_categories(source: config_pb2.Source) -> None:
    if list(source.categories) == [sources.DEFAULT_CATEGORY]:
        source.ClearField("categories")


def religion_names() -> dict[str, str]:
    """Returns religion names by form value."""
    return {
        sources.RELIGION_PREFIX + key: label
        for key, (label, _, _) in religions.RELIGIONS.items()
    }


def _new_source(kind: str) -> config_pb2.Source:
    if kind.startswith(sources.RELIGION_PREFIX):
        return config_pb2.Source(
            religion=kind.removeprefix(sources.RELIGION_PREFIX)
        )
    return config_pb2.Source(country=kind)


def views(
    parsed: config_pb2.Config, events: list[merge.Event]
) -> list[SourceView]:
    """Builds the page's view of each source, given all its merged events."""
    hidden = set(parsed.hidden)
    return [
        _view(index, source, events, hidden)
        for index, source in enumerate(parsed.sources)
    ]


def _view(
    index: int,
    source: config_pb2.Source,
    events: list[merge.Event],
    hidden: set[str],
) -> SourceView:
    if source.HasField("religion"):
        kind = sources.RELIGION_PREFIX + source.religion
        label = religion_names()[kind]
        return SourceView(
            index=index,
            kind=kind,
            label=label,
            all_subdivisions=False,
            subdivisions=[],
            categories=[],
            notices=_notices(index, label, label, events, hidden),
        )
    country = source.country
    label = sources.country_names()[country]
    categories = set(source.categories) or {sources.DEFAULT_CATEGORY}
    return SourceView(
        index=index,
        kind=country,
        label=label,
        all_subdivisions=source.all_subdivisions,
        subdivisions=[
            Option(code, name, code in source.subdivisions)
            for code, name in subdivision_names(country).items()
        ],
        categories=[
            Option(category, category.replace("_", " "), category in categories)
            for category in config.supported_categories(country)
        ],
        notices=_notices(index, country, label, events, hidden),
    )


def _notices(
    index: int,
    code: str,
    label: str,
    events: list[merge.Event],
    hidden: set[str],
) -> list[HiddenNotice]:
    """Flags a source, region or type whose holidays are all hidden."""
    found = [
        (o, merge.hide_token(o) in hidden)
        for event in events
        for o in event.occurrences
        if o.source == code
    ]
    if found and all(is_hidden for _, is_hidden in found):
        return [
            HiddenNotice(
                f"Every holiday from {label} is hidden.",
                "remove",
                str(index),
                f"Remove {label}",
            )
        ]
    notices = []
    by_region = _group(found, lambda o: o.subdivision)
    region_names = subdivision_names(code) if by_region.keys() - {""} else {}
    for region, all_hidden in by_region.items():
        if region and all_hidden:
            name = region_names.get(region, region)
            notices.append(
                HiddenNotice(
                    f"Every holiday specific to {name} is hidden.",
                    "drop_region",
                    f"{index}:{region}",
                    f"Remove {name}",
                )
            )
    by_type = _group(found, lambda o: o.category)
    if len(by_type) > 1:
        for category, all_hidden in by_type.items():
            if all_hidden:
                name = category.replace("_", " ")
                notices.append(
                    HiddenNotice(
                        f"Every {name} holiday from {label} is hidden.",
                        "drop_type",
                        f"{index}:{category}",
                        f"Remove {name} holidays",
                    )
                )
    return notices


def _group(
    found: list[tuple[sources.Occurrence, bool]],
    part: typing.Callable[[sources.Occurrence], str],
) -> dict[str, bool]:
    """Maps each part (region, type) to whether all its holidays are hidden."""
    groups: dict[str, bool] = {}
    for occurrence, is_hidden in found:
        key = part(occurrence)
        groups[key] = groups.get(key, True) and is_hidden
    return groups

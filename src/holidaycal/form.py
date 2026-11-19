"""Translation between the config page's form and `Config`."""

import dataclasses
import functools
import re
from collections.abc import Iterable

import holidays
from werkzeug import datastructures

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import merge
from holidaycal import religions
from holidaycal import sources

RELIGION_PREFIX = "@"
_KIND_FIELD = re.compile(r"s(\d+)\.kind")


@dataclasses.dataclass(frozen=True)
class Option:
    """A checkbox or select option."""

    value: str
    label: str
    checked: bool = False


@dataclasses.dataclass(frozen=True)
class SourceView:
    """Everything the page needs to render one configured source."""

    index: int
    kind: str
    label: str
    all_subdivisions: bool
    subdivisions: list[Option]
    categories: list[Option]
    holidays: list[Option]


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
    )
    indices = [
        match[1]
        for key in form
        if (match := _KIND_FIELD.fullmatch(key)) and match[1] != removed
    ]
    if move := form.get("move"):
        _move(indices, move)
    parsed.sources.extend(
        _parse_source(form, f"s{index}.", form[f"s{index}.kind"])
        for index in indices
    )
    if added := form.get("add"):
        parsed.sources.append(_new_source(added))
    config.validate(parsed)
    return parsed


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
    source.excluded.extend(form.getlist(prefix + "excluded"))
    if list(source.categories) == [sources.DEFAULT_CATEGORY]:
        source.ClearField("categories")
    return source


def religion_names() -> dict[str, str]:
    """Returns religion names by form value."""
    return {
        RELIGION_PREFIX + key: label
        for key, (label, _) in religions.RELIGIONS.items()
    }


def _new_source(kind: str) -> config_pb2.Source:
    if kind.startswith(RELIGION_PREFIX):
        return config_pb2.Source(religion=kind.removeprefix(RELIGION_PREFIX))
    return config_pb2.Source(country=kind)


def views(parsed: config_pb2.Config, years: Iterable[int]) -> list[SourceView]:
    """Builds the page's view of each configured source."""
    years = list(years)
    return [
        _view(index, source, years)
        for index, source in enumerate(parsed.sources)
    ]


def _view(
    index: int, source: config_pb2.Source, years: list[int]
) -> SourceView:
    unfiltered = config_pb2.Source()
    unfiltered.CopyFrom(source)
    unfiltered.ClearField("excluded")
    names: dict[str, str] = {}
    for occurrence in sources.occurrences(unfiltered, years):
        names.setdefault(merge.normalize(occurrence.name), occurrence.name)
    holiday_options = [
        Option(key, name, key in source.excluded)
        for key, name in sorted(names.items(), key=lambda item: item[1])
    ]
    if source.HasField("religion"):
        kind = RELIGION_PREFIX + source.religion
        return SourceView(
            index=index,
            kind=kind,
            label=religion_names()[kind],
            all_subdivisions=False,
            subdivisions=[],
            categories=[],
            holidays=holiday_options,
        )
    country = source.country
    categories = set(source.categories) or {sources.DEFAULT_CATEGORY}
    return SourceView(
        index=index,
        kind=country,
        label=sources.country_names()[country],
        all_subdivisions=source.all_subdivisions,
        subdivisions=[
            Option(code, name, code in source.subdivisions)
            for code, name in subdivision_names(country).items()
        ],
        categories=[
            Option(category, category.replace("_", " "), category in categories)
            for category in config.supported_categories(country)
        ],
        holidays=holiday_options,
    )

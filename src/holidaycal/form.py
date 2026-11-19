"""Translation between the config page's form and `Config`."""

import dataclasses
import functools
from collections.abc import Iterable

import holidays
from holidays import registry
from werkzeug import datastructures

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import merge
from holidaycal import religions
from holidaycal import sources

RELIGION_PREFIX = "@"


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
def country_names() -> dict[str, str]:
    """Returns English country names by code, sorted by name."""
    names = {
        code: key.replace("_", " ").title()
        for key, (_, code, *_) in registry.COUNTRIES.items()
    }
    return dict(sorted(names.items(), key=lambda item: item[1]))


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
    parsed = config_pb2.Config()
    index = 0
    while (kind := form.get(f"s{index}.kind")) is not None:
        if str(index) != removed:
            parsed.sources.append(_parse_source(form, f"s{index}.", kind))
        index += 1
    if added := form.get("add"):
        parsed.sources.append(_new_source(added))
    config.validate(parsed)
    return parsed


def _parse_source(
    form: datastructures.MultiDict[str, str], prefix: str, kind: str
) -> config_pb2.Source:
    source = _new_source(kind)
    source.subdivisions.extend(form.getlist(prefix + "subdivision"))
    source.all_subdivisions = bool(form.get(prefix + "all_subdivisions"))
    source.categories.extend(form.getlist(prefix + "category"))
    source.excluded.extend(form.getlist(prefix + "excluded"))
    if source.all_subdivisions:
        source.ClearField("subdivisions")
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
        label=country_names()[country],
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

import pytest
from werkzeug import datastructures

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import form


def _parse(*pairs: tuple[str, str]) -> config_pb2.Config:
    return form.parse(datastructures.MultiDict(list(pairs)))


def test_add_country():
    assert _parse(("add", "CA")) == config_pb2.Config(
        sources=[config_pb2.Source(country="CA")]
    )


def test_add_religion():
    assert _parse(("add", "@jewish")) == config_pb2.Config(
        sources=[config_pb2.Source(religion="jewish")]
    )


def test_religion_view():
    [view] = form.views(_parse(("s0.kind", "@hindu")), [2026])

    assert (view.kind, view.label) == ("@hindu", "Hindu")
    assert not view.subdivisions
    assert form.Option("diwali", "Diwali") in view.holidays


def test_source_fields():
    parsed = _parse(
        ("s0.kind", "CA"),
        ("s0.subdivision", "ON"),
        ("s0.category", "public"),
        ("s0.category", "optional"),
        ("s0.excluded", "christmas day"),
    )

    assert parsed.sources[0] == config_pb2.Source(
        country="CA",
        subdivisions=["ON"],
        categories=["public", "optional"],
        excluded=["christmas day"],
    )


def test_all_subdivisions_keeps_picked_regions():
    parsed = _parse(
        ("s0.kind", "CA"),
        ("s0.all_subdivisions", "1"),
        ("s0.subdivision", "ON"),
        ("s0.category", "public"),
    )

    assert parsed.sources[0] == config_pb2.Source(
        country="CA", all_subdivisions=True, subdivisions=["ON"]
    )


def test_remove():
    parsed = _parse(("s0.kind", "CA"), ("s1.kind", "US"), ("remove", "0"))

    assert [s.country for s in parsed.sources] == ["US"]


def test_invalid():
    with pytest.raises(config.InvalidConfigError):
        _parse(("add", "XX"))


def test_views_list_holidays_and_exclusions():
    parsed = _parse(("s0.kind", "CA"), ("s0.excluded", "christmas day"))

    [view] = form.views(parsed, [2026])

    assert view.label == "Canada"
    assert form.Option("christmas day", "Christmas Day", True) in view.holidays
    assert form.Option("ON", "Ontario") in view.subdivisions
    assert form.Option("public", "public", True) in view.categories


def test_format_options():
    parsed = _parse(
        ("add", "CA"),
        ("title_style", "TITLE_STYLE_PREFIX_NAMES"),
        ("describe_sources", "1"),
    )

    assert parsed.title_style == config_pb2.TITLE_STYLE_PREFIX_NAMES
    assert parsed.describe_sources
    assert not parsed.describe_categories


def test_invalid_title_style():
    with pytest.raises(config.InvalidConfigError):
        _parse(("add", "CA"), ("title_style", "BOLD"))


def _countries(parsed: config_pb2.Config) -> list[str]:
    return [s.country for s in parsed.sources]


def test_sources_follow_form_order():
    parsed = _parse(("s1.kind", "US"), ("s0.kind", "CA"), ("s2.kind", "DE"))

    assert _countries(parsed) == ["US", "CA", "DE"]


@pytest.mark.parametrize(
    ("move", "expected"),
    [
        ("1:up", ["US", "CA", "DE"]),
        ("1:down", ["CA", "DE", "US"]),
        ("0:up", ["CA", "US", "DE"]),
        ("2:down", ["CA", "US", "DE"]),
    ],
)
def test_move(move, expected):
    parsed = _parse(
        ("s0.kind", "CA"), ("s1.kind", "US"), ("s2.kind", "DE"), ("move", move)
    )

    assert _countries(parsed) == expected


@pytest.mark.parametrize("move", ["1:left", "7:up", "up"])
def test_invalid_move(move):
    with pytest.raises(config.InvalidConfigError):
        _parse(("s0.kind", "CA"), ("s1.kind", "US"), ("move", move))


def test_combine_multiday_option():
    assert _parse(("add", "CA"), ("combine_multiday", "1")).combine_multiday
    assert not _parse(("add", "CA"), ("combine_multiday", "")).combine_multiday

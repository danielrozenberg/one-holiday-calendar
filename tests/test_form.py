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


def test_defaults_are_left_empty():
    parsed = _parse(
        ("s0.kind", "CA"),
        ("s0.all_subdivisions", "1"),
        ("s0.subdivision", "ON"),
        ("s0.category", "public"),
    )

    assert parsed.sources[0] == config_pb2.Source(
        country="CA", all_subdivisions=True
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

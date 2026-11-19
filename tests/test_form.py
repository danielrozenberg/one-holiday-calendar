import pytest
from werkzeug import datastructures

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import form
from holidaycal import merge


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


def test_event_view():
    parsed = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA", subdivisions=["ON", "AB"]),
            config_pb2.Source(religion="christian"),
        ]
    )
    [family_day] = [
        e for e in merge.build(parsed, [2026]) if e.key == "family day"
    ]

    view = form.event_view(family_day)

    [badge] = view.sources
    assert badge.flag == "\U0001f1e8\U0001f1e6"
    assert badge.regions == ["AB", "ON"]
    assert badge.label == "Canada: Alberta, Ontario"
    assert view.types == [form.TypeBadge("P", "public")]


def test_short_date():
    parsed = config_pb2.Config(
        sources=[config_pb2.Source(religion="jewish")], combine_multiday=True
    )
    events = {e.key: e for e in merge.build(parsed, [2026])}

    assert form.event_view(events["passover"]).short_date == "Apr 2\u20139"
    assert form.event_view(events["hanukkah"]).short_date == "Dec 5\u201312"
    assert form.event_view(events["purim"]).short_date == "Tue, Mar 3"


def test_national_sources_have_no_regions():
    parsed = config_pb2.Config(sources=[config_pb2.Source(country="CA")])
    [canada_day] = [
        e for e in merge.build(parsed, [2026]) if e.key == "canada day"
    ]

    [badge] = form.event_view(canada_day).sources
    assert badge.regions == []
    assert badge.label == "Canada"


def test_card_has_every_title_style_and_description_line():
    card = form.event_view(form.sample_event(2026)).card

    assert set(card["titles"]) == set(config_pb2.TitleStyle.keys())
    assert card["titles"]["TITLE_STYLE_SUFFIX_CODES"] == (
        "Christmas Eve [CA, US, Christian]"
    )
    assert card["date"] == "Thursday, December 24, 2026"
    assert card["sources"] == "Observed in: Canada, United States, Christian"
    assert card["categories"] == "Types: optional, religious"


def test_representative_prefers_most_sources():
    parsed = config_pb2.Config(
        sources=[
            config_pb2.Source(country="CA"),
            config_pb2.Source(country="US"),
            config_pb2.Source(religion="christian"),
        ]
    )
    views = [form.event_view(e) for e in merge.build(parsed, [2026])]

    featured = form.representative(views)

    assert featured is not None
    assert featured.event.name == "Christmas Day"
    assert form.representative([]) is None


def test_multiday_card_date_is_a_range():
    parsed = config_pb2.Config(
        sources=[config_pb2.Source(religion="jewish")], combine_multiday=True
    )
    [passover] = [e for e in merge.build(parsed, [2026]) if e.key == "passover"]

    assert form.event_view(passover).card["date"] == (
        "Thu, Apr 2 \u2013 Thu, Apr 9, 2026"
    )

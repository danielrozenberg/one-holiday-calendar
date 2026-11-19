import datetime

import pytest

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import merge
from holidaycal import religions
from holidaycal import sources


@pytest.mark.parametrize("religion", religions.RELIGIONS)
def test_every_religion_has_holidays(religion):
    source = config_pb2.Source(religion=religion)

    found = list(sources.occurrences(source, [2026]))

    assert len(found) >= 8
    assert {o.category for o in found} == {sources.RELIGIOUS_CATEGORY}


def test_config_accepts_religion():
    blob = config.encode(
        config_pb2.Config(sources=[config_pb2.Source(religion="jewish")])
    )

    assert config.decode(blob).sources[0].religion == "jewish"


def test_christmas_merges_with_countries():
    events = merge.build(
        config_pb2.Config(
            sources=[
                config_pb2.Source(country="US"),
                config_pb2.Source(religion="christian"),
            ]
        ),
        [2026],
    )

    [christmas] = [e for e in events if e.date == datetime.date(2026, 12, 25)]
    assert {o.source for o in christmas.occurrences} == {"US", "Christian"}


def test_estimated_islamic_dates_merge_with_countries():
    events = merge.build(
        config_pb2.Config(
            sources=[
                config_pb2.Source(country="EG"),
                config_pb2.Source(religion="islamic"),
            ]
        ),
        [2026],
    )

    eid = [e for e in events if e.key == "eid al fitr"]
    assert any(len({o.source for o in e.occurrences}) == 2 for e in eid)

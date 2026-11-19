import pytest

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import settings


def _config(**kwargs) -> config_pb2.Config:
    return config_pb2.Config(
        sources=[
            config_pb2.Source(
                country="CA",
                subdivisions=["ON", "BC"],
                categories=["public", "optional"],
                excluded=["groundhog day"],
            ),
            config_pb2.Source(country="US"),
        ],
        **kwargs,
    )


def test_round_trip():
    original = _config(title_style=config_pb2.TITLE_STYLE_PREFIX_CODES)

    blob = config.encode(original)

    assert config.decode(blob) == original
    assert "=" not in blob
    assert len(blob) < 80


@pytest.mark.parametrize(
    "blob",
    [
        "!!!",
        "a",
        "ä",
        "_" * 7,
        "x" * (settings.CURRENT.url.max_blob_length + 1),
    ],
)
def test_decode_rejects_malformed(blob):
    with pytest.raises(config.InvalidConfigError):
        config.decode(blob)


@pytest.mark.parametrize(
    "source",
    [
        config_pb2.Source(country="XX"),
        config_pb2.Source(country="CA", subdivisions=["TX"]),
        config_pb2.Source(country="CA", categories=["bank"]),
        config_pb2.Source(religion="pastafarian"),
        config_pb2.Source(),
    ],
)
def test_decode_rejects_unsupported(source):
    blob = config.encode(config_pb2.Config(sources=[source]))

    with pytest.raises(config.InvalidConfigError):
        config.decode(blob)


def test_decode_rejects_future_version():
    blob = config.encode(_config(v=1))

    with pytest.raises(config.InvalidConfigError, match="version"):
        config.decode(blob)


def test_decode_rejects_unknown_title_style():
    blob = config.encode(_config(title_style=7))

    with pytest.raises(config.InvalidConfigError, match="title style"):
        config.decode(blob)


def test_decode_rejects_too_many_sources():
    countries = "CA US DE FR IT ES GB MX BR AR JP KR CN IN AU NZ ZA EG IL TR SE"
    sources = [config_pb2.Source(country=c) for c in countries.split()]
    blob = config.encode(config_pb2.Config(sources=sources))

    with pytest.raises(config.InvalidConfigError, match="sources"):
        config.decode(blob)


def test_decode_rejects_duplicate_sources():
    sources = [
        config_pb2.Source(country="US", excluded=["christmas day"]),
        config_pb2.Source(country="US", excluded=["new years day"]),
    ]
    blob = config.encode(config_pb2.Config(sources=sources))

    with pytest.raises(config.InvalidConfigError, match="Duplicate"):
        config.decode(blob)

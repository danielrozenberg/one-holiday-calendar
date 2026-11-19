import base64
import hashlib
import zlib

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
            ),
            config_pb2.Source(country="US"),
        ],
        hidden=["groundhog day"],
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
        config_pb2.Source(religion="jewish", all_subdivisions=True),
        config_pb2.Source(religion="jewish", categories=["public"]),
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
        config_pb2.Source(country="US"),
        config_pb2.Source(country="US", all_subdivisions=True),
    ]
    blob = config.encode(config_pb2.Config(sources=sources))

    with pytest.raises(config.InvalidConfigError, match="Duplicate"):
        config.decode(blob)


def _hidden_heavy() -> config_pb2.Config:
    tokens = [
        "US:independence day",
        "US:labor_day",
        "US:thanksgiving day",
        "US/CA:cesar chavez day",
        "US/TX:emancipation day in texas",
    ]
    return config_pb2.Config(
        sources=[config_pb2.Source(country="US", all_subdivisions=True)],
        hidden=sorted(tokens),
    )


def test_tiny_configs_stay_uncompressed():
    blob = config.encode(
        config_pb2.Config(sources=[config_pb2.Source(country="CA")])
    )

    assert blob.startswith("A")


def test_long_configs_are_compressed():
    original = _hidden_heavy()
    raw = original.SerializeToString(deterministic=True)

    blob = config.encode(original)

    assert blob.startswith("B")
    assert len(blob) < len(raw)
    assert config.decode(blob) == original


def test_empty_blob_is_the_empty_config():
    assert config.decode("") == config_pb2.Config()


def _deflate_blob(data: bytes) -> str:
    compressor = zlib.compressobj(
        level=9, wbits=-15, zdict=config._dictionary("B")
    )
    compressed = compressor.compress(data) + compressor.flush()
    encoded = base64.urlsafe_b64encode(compressed).rstrip(b"=").decode()
    return "B" + encoded


@pytest.mark.parametrize(
    "blob",
    [
        "Z" + config.encode(config_pb2.Config())[1:],
        _deflate_blob(b"\0" * 1_000_000),
        _deflate_blob(_hidden_heavy().SerializeToString())[:-4],
    ],
    ids=["unknown format", "decompression bomb", "truncated"],
)
def test_decode_rejects_bad_formats(blob):
    with pytest.raises(config.InvalidConfigError):
        config.decode(blob)


def test_dictionary_is_frozen():
    # Changing a deployed dictionary breaks existing URLs; add a new format.
    digest = hashlib.sha256(config._dictionary("B")).hexdigest()

    assert (
        digest
        == "31768c73f5fe98cc2e455b82159c1b7b40698c19178895d24bc817f16c5326c9"
    )

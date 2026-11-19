"""Encoding, decoding and validation of the URL-borne `Config`."""

import base64
import functools
import importlib.resources
import zlib

import holidays
from google.protobuf import message

from one_holiday_calendar import config_pb2
from one_holiday_calendar import religions
from one_holiday_calendar import settings


class InvalidConfigError(ValueError):
    """Raised when a config blob cannot be decoded or fails validation."""


# Each blob starts with a format marker, followed by base64url without padding.
_RAW = "A"
_DEFLATE_V1 = "B"
# Decompressed configs are small; this bounds work on crafted blobs.
_MAX_RAW_BYTES = 64 * 1024


def encode(config: config_pb2.Config) -> str:
    """Serializes a config into its shortest URL-safe form.

    That is the protobuf either as is, or compressed with DEFLATE and a preset
    dictionary of common strings, which shrinks long configs severalfold.
    """
    raw = config.SerializeToString(deterministic=True)
    compressor = zlib.compressobj(
        level=9, wbits=-15, zdict=_dictionary(_DEFLATE_V1)
    )
    compressed = compressor.compress(raw) + compressor.flush()
    return min(_RAW + _base64(raw), _DEFLATE_V1 + _base64(compressed), key=len)


def decode(blob: str) -> config_pb2.Config:
    """Parses and validates a blob produced by `encode`.

    An empty blob is the empty config.

    Raises:
        InvalidConfigError: The blob is malformed or describes an unsupported
            config.
    """
    if not blob:
        return config_pb2.Config()
    if len(blob) > settings.CURRENT.url.max_blob_length:
        raise InvalidConfigError("Config is too long")
    marker, body = blob[0], blob[1:]
    try:
        data = base64.b64decode(
            body + "=" * (-len(body) % 4), altchars=b"-_", validate=True
        )
        match marker:
            case "A":
                raw = data
            case "B":
                raw = _inflate(data, _dictionary(marker))
            case _:
                raise InvalidConfigError(f"Unknown config format {marker!r}")
        config = config_pb2.Config.FromString(raw)
    except InvalidConfigError:
        raise
    except (ValueError, zlib.error, message.DecodeError) as e:
        raise InvalidConfigError("Config is not a valid blob") from e
    validate(config)
    return config


def _base64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _inflate(data: bytes, dictionary: bytes) -> bytes:
    decompressor = zlib.decompressobj(wbits=-15, zdict=dictionary)
    raw = decompressor.decompress(data, _MAX_RAW_BYTES)
    if decompressor.unconsumed_tail or not decompressor.eof:
        raise InvalidConfigError("Config is too long or truncated")
    return raw


@functools.cache
def _dictionary(marker: str) -> bytes:
    """Returns the frozen preset dictionary of a compressed format."""
    name = {_DEFLATE_V1: "config_dictionary_v1.txt"}[marker]
    return importlib.resources.files(__package__).joinpath(name).read_bytes()


def validate(config: config_pb2.Config) -> None:
    """Checks that a config only references supported data.

    Raises:
        InvalidConfigError: The config is not supported.
    """
    if config.v != 0:
        raise InvalidConfigError(f"Unsupported config version {config.v}")
    if config.title_style not in config_pb2.TitleStyle.values():
        raise InvalidConfigError(f"Unknown title style {config.title_style}")
    max_sources = settings.CURRENT.url.max_sources
    if len(config.sources) > max_sources:
        raise InvalidConfigError(f"More than {max_sources} sources")
    if len({(s.country, s.religion) for s in config.sources}) != len(
        config.sources
    ):
        raise InvalidConfigError("Duplicate sources")
    for source in config.sources:
        match source.WhichOneof("kind"):
            case "country":
                _validate_country(source)
            case "religion":
                if source.religion not in religions.RELIGIONS:
                    raise InvalidConfigError(
                        f"Unknown religion {source.religion}"
                    )
                if (
                    source.subdivisions
                    or source.all_subdivisions
                    or source.categories
                ):
                    raise InvalidConfigError(
                        "Religions have no regions or holiday types"
                    )
            case None:
                raise InvalidConfigError("Source has no country or religion")


def _validate_country(source: config_pb2.Source) -> None:
    subdivisions = _supported_countries().get(source.country)
    if subdivisions is None:
        raise InvalidConfigError(f"Unknown country {source.country}")
    if unknown := set(source.subdivisions) - set(subdivisions):
        raise InvalidConfigError(f"Unknown subdivisions {sorted(unknown)}")
    categories = supported_categories(source.country)
    if unknown := set(source.categories) - set(categories):
        raise InvalidConfigError(f"Unknown categories {sorted(unknown)}")


@functools.cache
def _supported_countries() -> dict[str, list[str]]:
    return holidays.list_supported_countries(include_aliases=False)


@functools.cache
def supported_categories(country: str) -> tuple[str, ...]:
    """Returns the holiday categories python-holidays supports for a country."""
    return tuple(holidays.country_holidays(country).supported_categories)

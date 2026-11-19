"""Encoding, decoding and validation of the URL-borne `Config`."""

import base64
import functools

import holidays
from google.protobuf import message

from holidaycal import config_pb2
from holidaycal import religions

MAX_BLOB_LENGTH = 2048
MAX_SOURCES = 20


class InvalidConfigError(ValueError):
    """Raised when a config blob cannot be decoded or fails validation."""


def encode(config: config_pb2.Config) -> str:
    """Serializes a config into an unpadded base64url string."""
    raw = config.SerializeToString(deterministic=True)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode(blob: str) -> config_pb2.Config:
    """Parses and validates a blob produced by `encode`.

    Raises:
        InvalidConfigError: The blob is malformed or describes an unsupported
            config.
    """
    if len(blob) > MAX_BLOB_LENGTH:
        raise InvalidConfigError("Config is too long")
    try:
        raw = base64.b64decode(
            blob + "=" * (-len(blob) % 4), altchars=b"-_", validate=True
        )
        config = config_pb2.Config.FromString(raw)
    except (ValueError, message.DecodeError) as e:
        raise InvalidConfigError("Config is not a valid blob") from e
    validate(config)
    return config


def validate(config: config_pb2.Config) -> None:
    """Checks that a config only references supported data.

    Raises:
        InvalidConfigError: The config is not supported.
    """
    if config.v != 0:
        raise InvalidConfigError(f"Unsupported config version {config.v}")
    if config.title_style not in config_pb2.TitleStyle.values():
        raise InvalidConfigError(f"Unknown title style {config.title_style}")
    if len(config.sources) > MAX_SOURCES:
        raise InvalidConfigError(f"More than {MAX_SOURCES} sources")
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

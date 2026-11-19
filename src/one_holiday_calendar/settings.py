"""Load and validate the static app settings (`settings.toml`)."""

import pathlib
import tomllib

import pydantic

DEFAULT_PATH = pathlib.Path(__file__).with_name("settings.toml")


class SettingsError(Exception):
    """Raised when the settings file is missing or invalid."""


class _Section(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class UrlSettings(_Section):
    """Limits on the config carried in calendar URLs."""

    max_blob_length: pydantic.PositiveInt
    max_sources: pydantic.PositiveInt


class FeedSettings(_Section):
    """The iCalendar feed served to calendar apps."""

    calendar_name: str
    refresh_hours: pydantic.PositiveInt
    years_before: pydantic.NonNegativeInt
    years_after: pydantic.NonNegativeInt
    global_sources: pydantic.PositiveInt


class PageSettings(_Section):
    """The config and preview page."""

    preview_days: pydantic.PositiveInt
    offline_pages: pydantic.NonNegativeInt


class CacheSettings(_Section):
    """The in-memory response cache."""

    budget_mb: pydantic.NonNegativeInt


class Settings(_Section):
    """All app settings."""

    url: UrlSettings
    feed: FeedSettings
    page: PageSettings
    cache: CacheSettings


def load(path: pathlib.Path = DEFAULT_PATH) -> Settings:
    """Reads and validates a settings file.

    Raises:
        SettingsError: The file is missing, malformed, or fails validation.
            The message names what to fix.
    """
    if not path.exists():
        raise SettingsError(f"Settings file not found at {path}.")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise SettingsError(f"Could not parse {path}: {error}") from error
    try:
        return Settings.model_validate(raw)
    except pydantic.ValidationError as error:
        raise SettingsError(_format_validation_error(path, error)) from error


def _format_validation_error(
    path: pathlib.Path, error: pydantic.ValidationError
) -> str:
    lines = [f"Invalid settings in {path}:"]
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "(root)"
        lines.append(f"  - {location}: {item['msg']}")
    return "\n".join(lines)


CURRENT = load()

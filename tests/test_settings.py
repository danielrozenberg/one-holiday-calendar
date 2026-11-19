import pytest

from holidaycal import settings

_VALID = settings.DEFAULT_PATH.read_text(encoding="utf-8")


def _write(tmp_path, text):
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_packaged_settings_load():
    assert settings.load() == settings.CURRENT
    assert settings.CURRENT.url.max_sources > 0


def test_missing_file(tmp_path):
    with pytest.raises(settings.SettingsError, match="not found"):
        settings.load(tmp_path / "settings.toml")


def test_malformed_toml(tmp_path):
    with pytest.raises(settings.SettingsError, match="parse"):
        settings.load(_write(tmp_path, "this is = = not toml"))


def test_invalid_value_names_the_field(tmp_path):
    text = _VALID.replace("max_sources = 20", "max_sources = 0")

    with pytest.raises(settings.SettingsError, match=r"url\.max_sources"):
        settings.load(_write(tmp_path, text))


def test_unknown_key_is_rejected(tmp_path):
    with pytest.raises(settings.SettingsError, match="typo"):
        settings.load(_write(tmp_path, _VALID + "\n[typo]\nx = 1\n"))

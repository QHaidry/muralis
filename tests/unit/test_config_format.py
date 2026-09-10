#!/usr/bin/env python3
"""Tests for choosing and converting the configuration format.

TOML and YAML need optional dependencies, so these tests key off whatever
:func:`available_config_formats` actually reports rather than assuming a set.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from muralis.__main__ import main
from muralis.config import ConfigManager, ConfigValidationError, available_config_formats


@pytest.fixture
def temp_dir():
    directory = tempfile.TemporaryDirectory()
    ConfigManager.clear_cache()
    yield Path(directory.name)
    ConfigManager.clear_cache()
    directory.cleanup()


def _other_format():
    """A format other than the default, or skip if none is installed."""
    for fmt in available_config_formats():
        if fmt != "json":
            return fmt
    pytest.skip("no format other than json is available in this environment")


# ----------------------------------------------------------------------
# Reporting available formats
# ----------------------------------------------------------------------


def test_json_is_always_available():
    assert "json" in available_config_formats()


def test_available_formats_only_lists_usable_ones():
    # Every format offered must round-trip; offering one that cannot be
    # written would turn a clear "install this extra" into a confusing error.
    from gesso.config import builtin_codecs

    for name in available_config_formats():
        codec = next(c for c in builtin_codecs() if c.name == name)
        assert codec.available() is True


# ----------------------------------------------------------------------
# Choosing a format
# ----------------------------------------------------------------------


def test_default_format_is_json(temp_dir):
    config = ConfigManager(str(temp_dir / "config.json"))
    assert config.format == "json"
    assert (temp_dir / "config.json").exists()


def test_format_can_be_forced(temp_dir):
    fmt = _other_format()
    config = ConfigManager(str(temp_dir / "config"), format=fmt)
    assert config.format == fmt
    assert config.config_path.suffix == f".{fmt}"


def test_ini_path_is_reinterpreted_as_the_default_format(temp_dir):
    # INI is no longer a format. An older caller passing config.ini gets a
    # working JSON config rather than an error.
    config = ConfigManager(str(temp_dir / "config.ini"))
    assert config.config_path.name == "config.json"
    assert config.format == "json"


# ----------------------------------------------------------------------
# Converting
# ----------------------------------------------------------------------


def test_convert_rewrites_the_file_and_keeps_a_backup(temp_dir):
    fmt = _other_format()
    config = ConfigManager(str(temp_dir / "config.json"))
    config.set("general", "provider", "nasa")

    new_path = config.convert(fmt)

    assert new_path.suffix == f".{fmt}"
    assert config.config_path == new_path
    assert config.format == fmt
    assert (temp_dir / "config.json.bak").exists()


def test_convert_preserves_values_and_their_types(temp_dir):
    fmt = _other_format()
    config = ConfigManager(str(temp_dir / "config.json"))
    config.set("general", "provider", "nasa")
    config.set("image", "jpeg_quality", 75)

    new_path = config.convert(fmt)
    ConfigManager.clear_cache()
    reopened = ConfigManager(str(new_path))

    assert reopened.get_str("general", "provider") == "nasa"
    assert reopened.get_int("image", "jpeg_quality") == 75
    assert reopened.format == fmt


def test_convert_refuses_to_clobber_an_existing_file(temp_dir):
    fmt = _other_format()
    config = ConfigManager(str(temp_dir / "config.json"))
    # Something is already sitting at the target path.
    target = config.config_path.with_suffix(f".{fmt}")
    target.write_text("", encoding="utf-8")

    with pytest.raises(ConfigValidationError):
        config.convert(fmt)
    # The existing file is untouched and we still point at the original.
    assert config.format == "json"


def test_convert_to_the_same_format_is_a_no_op(temp_dir):
    config = ConfigManager(str(temp_dir / "config.json"))
    assert config.convert("json") == config.config_path
    assert config.format == "json"


def test_config_is_readable_as_plain_text_after_conversion(temp_dir):
    fmt = _other_format()
    config = ConfigManager(str(temp_dir / "config.json"))
    config.set("general", "provider", "nasa")

    new_path = config.convert(fmt)
    text = new_path.read_text(encoding="utf-8")

    assert "provider" in text and "nasa" in text
    if fmt == "yaml":
        # And the value is a string, not a quoted blob of JSON.
        assert json.dumps({"provider": "nasa"}) not in text


# ----------------------------------------------------------------------
# The CLI surface
# ----------------------------------------------------------------------


def _run(argv):
    with patch("sys.argv", ["muralis"] + argv):
        with patch("muralis.__main__.MuralisApp") as app_cls:
            app = MagicMock()
            app.run_once.return_value = True
            app_cls.return_value = app
            rc = main()
    return rc, app, app_cls


def test_convert_config_is_actionable():
    """--convert-config must not fall through to show_help."""
    fmt = available_config_formats()[0]
    rc, app, _ = _run(["--convert-config", fmt])
    app.config.convert.assert_called_once_with(fmt)
    assert rc == 0


def test_config_format_is_forwarded_to_the_app():
    fmt = available_config_formats()[0]
    _, _, app_cls = _run(["--once", "--config-format", fmt])
    assert app_cls.call_args.kwargs.get("config_format") == fmt


def test_config_format_rejects_an_unavailable_format():
    # argparse should refuse a format this installation cannot write.
    unavailable = [f for f in ("toml", "yaml", "json") if f not in available_config_formats()]
    if not unavailable:
        pytest.skip("every format is available here")
    with patch("sys.argv", ["muralis", "--config-format", unavailable[0]]):
        with pytest.raises(SystemExit):
            main()

#!/usr/bin/env python3
"""Tests for the helpers the GUI pages share.

``wallpaper_dir`` is the interesting one: the pages used to hard-code the
default directory while the updater wrote to the configured one, so a user who
moved their library saw an empty preview and an empty history.
"""

import os
from pathlib import Path

import pytest
from gesso.core.paths import AppPaths

from muralis import context
from muralis.config import ConfigManager
from muralis.gui import support


@pytest.fixture
def profile(tmp_path):
    context.use_paths(AppPaths.resolve("muralis", config_home=tmp_path / "config"))
    ConfigManager.clear_cache()
    yield tmp_path
    context.reset()
    ConfigManager.clear_cache()


@pytest.fixture
def config(profile):
    """The same configuration the helpers read, i.e. the app's own path."""
    return ConfigManager(str(context.config_path()))


def _wallpaper(directory: Path, name: str, age: float = 0.0) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"x")
    if age:
        stamp = path.stat().st_mtime - age
        os.utime(path, (stamp, stamp))
    return path


# ----------------------------------------------------------------------
# The wallpaper directory
# ----------------------------------------------------------------------


def test_the_wallpaper_directory_follows_the_configuration(config, profile):
    custom = profile / "elsewhere"
    config.set("storage", "download_dir", str(custom))

    assert support.wallpaper_dir() == custom


def test_the_wallpaper_directory_falls_back_to_the_default(config):
    assert support.wallpaper_dir() == Path.home() / "Pictures" / "Muralis"


def test_a_missing_directory_lists_nothing(config, profile):
    config.set("storage", "download_dir", str(profile / "nope"))
    assert support.list_wallpapers() == []


# ----------------------------------------------------------------------
# Listing
# ----------------------------------------------------------------------


def test_only_muralis_wallpapers_are_listed(config, profile):
    folder = profile / "wallpapers"
    config.set("storage", "download_dir", str(folder))
    _wallpaper(folder, "muralis_1_bing_a.jpg")
    _wallpaper(folder, "muralis_2_nasa_b.jpg")
    _wallpaper(folder, "holiday.jpg")
    _wallpaper(folder, "notes.txt")

    names = [path.name for path in support.list_wallpapers()]
    assert names == ["muralis_1_bing_a.jpg", "muralis_2_nasa_b.jpg"] or set(names) == {
        "muralis_1_bing_a.jpg",
        "muralis_2_nasa_b.jpg",
    }


def test_the_newest_wallpaper_comes_first(config, profile):
    folder = profile / "wallpapers"
    config.set("storage", "download_dir", str(folder))
    _wallpaper(folder, "muralis_old.jpg", age=10_000)
    _wallpaper(folder, "muralis_new.jpg")

    assert [path.name for path in support.list_wallpapers()][0] == "muralis_new.jpg"


def test_an_explicit_directory_is_honoured(config, profile):
    folder = profile / "explicit"
    _wallpaper(folder, "muralis_x.jpg")

    assert [path.name for path in support.list_wallpapers(folder)] == ["muralis_x.jpg"]


# ----------------------------------------------------------------------
# Formatting
# ----------------------------------------------------------------------


def test_a_vanished_file_does_not_raise(config, profile):
    folder = profile / "wallpapers"
    path = _wallpaper(folder, "muralis_gone.jpg")
    path.unlink()

    assert support.safe_mtime(path) == 0.0
    assert support.formatted_mtime(path) == "—"


def test_the_mtime_is_formatted_for_a_tooltip(config, profile):
    folder = profile / "wallpapers"
    path = _wallpaper(folder, "muralis_stamp.jpg")

    assert support.formatted_mtime(path) != "—"


# ----------------------------------------------------------------------
# Provider labels
# ----------------------------------------------------------------------


def test_a_known_provider_is_translated():
    from muralis.i18n import t

    assert support.provider_name("bing") == t("gui.provider.bing")


def test_an_unknown_provider_is_shown_as_its_key():
    assert support.provider_name("not-a-provider") == "not-a-provider"


def test_the_configured_provider_is_read(config):
    config.set("general", "provider", "nasa")
    assert support.configured_provider() == "nasa"

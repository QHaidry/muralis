#!/usr/bin/env python3
"""Tests for the settings tab.

These drive the widgets a user actually touches. The tab writes through the
same typed store the rest of the application uses, so the assertions here are
about the file on disk, not just the widget state.
"""

import json

import pytest

from muralis.config import ConfigManager, available_config_formats
from muralis.gui.settings_tab import SettingsTab
from muralis.gui.theme import DEFAULT_THEME, ThemeManager


@pytest.fixture
def config_file(tmp_path):
    """A configuration path inside the test's temporary directory."""
    ConfigManager.clear_cache()
    yield tmp_path / "config.json"
    ConfigManager.clear_cache()


@pytest.fixture
def make_tab(qapp, tmp_path, config_file, monkeypatch):
    """Build a SettingsTab wired to a temp config and silent dialogs.

    The dialogs are stubbed because a real QMessageBox would block the suite
    waiting for a click that never comes.
    """
    monkeypatch.setattr("muralis.gui.settings_tab.app_config_path", lambda: config_file)
    monkeypatch.setattr("muralis.gui.dialogs.info", lambda *args, **kwargs: None)
    monkeypatch.setattr("muralis.gui.dialogs.warning", lambda *args, **kwargs: None)

    def build(**kwargs):
        themes = ThemeManager(app=qapp, themes_dir=tmp_path / "themes")
        kwargs.setdefault("theme_manager", themes)
        tab = SettingsTab(**kwargs)
        tab._test_config_file = config_file
        return tab

    return build


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------


def test_builds_every_category(make_tab):
    tab = make_tab()
    assert set(tab.panes) == {"general", "image", "storage", "appearance"}
    assert set(tab.nav_items) == set(tab.panes)


def test_starts_on_the_general_category(make_tab):
    tab = make_tab()
    assert tab.stack.currentWidget() is tab.panes["general"]


def test_exposes_apply_and_reset_in_the_header(make_tab):
    tab = make_tab()
    labels = [button.text() for button in tab.action_buttons()]
    assert len(labels) == 2
    assert all(label for label in labels)


# ----------------------------------------------------------------------
# Loading and saving
# ----------------------------------------------------------------------


def test_load_reflects_the_defaults(make_tab):
    tab = make_tab()
    checked = [button.property("value") for button in tab.provider_buttons if button.isChecked()]
    assert checked == ["bing"]


def test_load_does_not_fire_the_change_callbacks(make_tab):
    calls = []
    make_tab(on_theme_change=calls.append)
    assert calls == [], "loading stored settings must not look like a user change"


def test_save_persists_values_with_their_types(make_tab):
    tab = make_tab()
    tab.max_files_spin.setValue(250)
    tab.auto_update_toggle.setChecked(False)

    tab.save_settings()

    payload = json.loads(tab._test_config_file.read_text(encoding="utf-8"))
    assert payload["storage"]["max_files"] == 250  # an int, not "250"
    assert payload["general"]["auto_update"] is False  # a bool, not "false"


def test_save_round_trips_through_a_reload(make_tab):
    tab = make_tab()
    tab.max_days_spin.setValue(7)
    tab.save_settings()

    reopened = ConfigManager(str(tab._test_config_file))
    assert reopened.get_int("storage", "max_days") == 7


def test_reset_restores_the_defaults_on_screen(make_tab, monkeypatch):
    monkeypatch.setattr("muralis.gui.dialogs.confirm", lambda *args, **kwargs: True)
    tab = make_tab()
    tab.max_files_spin.setValue(999)
    tab.save_settings()

    tab.reset_settings()

    assert tab.max_files_spin.value() == 100


# ----------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------


def test_selecting_a_theme_notifies_the_caller(make_tab):
    calls = []
    tab = make_tab(on_theme_change=calls.append)

    tab._on_theme_clicked(True, DEFAULT_THEME)

    assert calls == [DEFAULT_THEME]


def test_deselecting_a_theme_is_ignored(make_tab):
    calls = []
    tab = make_tab(on_theme_change=calls.append)

    tab._on_theme_clicked(False, DEFAULT_THEME)

    assert calls == []


# ----------------------------------------------------------------------
# The configuration-format row
# ----------------------------------------------------------------------


def test_format_row_appears_only_when_there_is_a_choice(make_tab):
    tab = make_tab()
    if len(available_config_formats()) > 1:
        assert tab.format_buttons
        checked = [b.property("value") for b in tab.format_buttons if b.isChecked()]
        assert checked == ["json"]
    else:
        # A single-option control would be a pointless row.
        assert not hasattr(tab, "format_buttons")


def test_choosing_a_format_converts_the_file(make_tab):
    formats = available_config_formats()
    if len(formats) <= 1:
        pytest.skip("only one configuration format is available here")

    tab = make_tab()
    tab.save_settings()  # make sure there is a file to convert
    target = next(fmt for fmt in formats if fmt != "json")

    tab._on_format_clicked(True, target)

    assert tab.config_path.suffix == f".{target}"
    assert tab.config_path.exists()
    # The previous file is kept, so changing your mind is a rename.
    assert (tab._test_config_file.parent / "config.json.bak").exists()

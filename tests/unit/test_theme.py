#!/usr/bin/env python3
"""Tests for the theme manager.

The GUI layer had no test coverage at all until now, which is how a real
regression slipped through earlier: the CLI tests mock the application, so
nothing exercised the code those mocks replace.
"""

import json

import pytest

from muralis.gui.theme import BUILTIN_THEMES_DIR, DEFAULT_THEME, ThemeManager


@pytest.fixture
def themes_dir(tmp_path):
    """An empty user themes directory, so tests never touch ~/.config."""
    return tmp_path / "themes"


def test_the_default_theme_ships_with_the_package():
    assert (BUILTIN_THEMES_DIR / f"{DEFAULT_THEME}.json").exists()


def test_seeding_copies_the_builtin_themes(themes_dir):
    ThemeManager(themes_dir=themes_dir)
    seeded = {path.name for path in themes_dir.glob("*.json")}
    builtin = {path.name for path in BUILTIN_THEMES_DIR.glob("*.json")}
    assert seeded == builtin


def test_seeding_does_not_overwrite_an_edited_theme(themes_dir):
    themes_dir.mkdir(parents=True, exist_ok=True)
    target = themes_dir / f"{DEFAULT_THEME}.json"
    target.write_text(json.dumps({"colors": {"accent": "#000000"}}), encoding="utf-8")

    ThemeManager(themes_dir=themes_dir)

    # The user's edit survives: seeding only fills in what is missing.
    assert json.loads(target.read_text(encoding="utf-8"))["colors"]["accent"] == "#000000"


def test_listing_includes_the_builtin_themes(themes_dir):
    manager = ThemeManager(themes_dir=themes_dir)
    assert DEFAULT_THEME in manager.list_themes()


def test_a_user_theme_is_listed(themes_dir):
    manager = ThemeManager(themes_dir=themes_dir)
    (themes_dir / "custom.json").write_text(
        json.dumps({"colors": {"accent": "#123456"}}), encoding="utf-8"
    )
    assert "custom" in manager.list_themes()


def test_colors_come_from_the_builtin_theme(themes_dir):
    colors = ThemeManager(themes_dir=themes_dir).load_colors(DEFAULT_THEME)
    assert colors.get("accent")
    assert colors.get("window")


def test_a_user_file_overrides_individual_tokens(themes_dir):
    manager = ThemeManager(themes_dir=themes_dir)
    (themes_dir / f"{DEFAULT_THEME}.json").write_text(
        json.dumps({"colors": {"accent": "#abcdef"}}), encoding="utf-8"
    )

    colors = manager.load_colors(DEFAULT_THEME)

    assert colors["accent"] == "#abcdef"
    # Everything the user did not mention still falls back to the built-in
    # value, so the stylesheet always substitutes and the UI cannot collapse
    # to the platform default.
    assert colors.get("window")


def test_an_unknown_theme_yields_no_colors(themes_dir):
    assert ThemeManager(themes_dir=themes_dir).load_colors("does-not-exist") == {}


def test_a_malformed_theme_file_is_ignored(themes_dir):
    manager = ThemeManager(themes_dir=themes_dir)
    (themes_dir / f"{DEFAULT_THEME}.json").write_text("{ not json", encoding="utf-8")
    # Falls back to the built-in palette rather than raising.
    assert manager.load_colors(DEFAULT_THEME).get("accent")


def test_an_unwritable_theme_directory_is_tolerated(tmp_path):
    # A read-only config directory must not stop the application starting.
    manager = ThemeManager(themes_dir=tmp_path / "nope" / "themes")
    assert DEFAULT_THEME in manager.list_themes()


def test_apply_without_an_application_is_a_no_op(themes_dir):
    assert ThemeManager(themes_dir=themes_dir).apply(DEFAULT_THEME) is False


def test_apply_sets_a_stylesheet_with_every_token_substituted(qapp, themes_dir):
    manager = ThemeManager(app=qapp, themes_dir=themes_dir)

    assert manager.apply(DEFAULT_THEME) is True

    sheet = qapp.styleSheet()
    assert "QPushButton" in sheet
    # An unsubstituted placeholder would mean a token is missing from the
    # theme, which is exactly the failure that silently flattens the UI.
    assert "${" not in sheet
    qapp.setStyleSheet("")


def test_apply_resolves_the_icon_directory(qapp, themes_dir):
    manager = ThemeManager(app=qapp, themes_dir=themes_dir)
    manager.apply(DEFAULT_THEME)

    # The spin-box arrows are url() references, which only resolve if the
    # stylesheet carries an absolute path.
    assert "chevron-up.svg" in qapp.styleSheet()
    qapp.setStyleSheet("")

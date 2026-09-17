#!/usr/bin/env python3
"""Tests for Muralis's theming, and for its adoption of Gesso's design system.

The interesting test here is :func:`test_every_object_name_muralis_sets_is_styled`.
Moving onto Gesso's stylesheet meant renaming Muralis's object names to Gesso's
vocabulary, and a name that does not match loses that widget's styling
*silently* — there is no error, the control just stops looking like anything.
That assertion turns the invisible into a failure.

``qapp`` comes from pytest-qt; ``tests/conftest.py`` puts Qt on the offscreen
platform so these run without a display.
"""

import json
import re
from pathlib import Path

import pytest

from muralis.gui import theme as theme_module
from muralis.gui.theme import BUILTIN_THEMES_DIR, DEFAULT_THEME, ThemeManager

THEME_NAMES = ("reasonix", "docker-dark", "light")


@pytest.fixture
def themes_dir(tmp_path):
    """An empty user themes directory, so tests never touch ~/.config."""
    return tmp_path / "themes"


# ----------------------------------------------------------------------
# The palettes
# ----------------------------------------------------------------------


def test_the_default_theme_ships_with_the_package():
    assert (BUILTIN_THEMES_DIR / f"{DEFAULT_THEME}.json").exists()


@pytest.mark.parametrize("name", THEME_NAMES)
def test_every_palette_satisfies_the_gesso_token_contract(name):
    """Muralis's palettes must speak Gesso's vocabulary exactly.

    A token Gesso does not know is almost always a typo, and would be ignored —
    the colour silently staying at its default with nothing to explain why.
    """
    from gesso.ui.theme import BASE_CONTRACT

    data = json.loads((BUILTIN_THEMES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    unknown = BASE_CONTRACT.unknown(data["colors"])
    assert unknown == [], f"{name} sets tokens Gesso does not know: {unknown}"


@pytest.mark.parametrize("name", THEME_NAMES)
def test_every_palette_renders(name, qapp, themes_dir):
    manager = ThemeManager(qapp, themes_dir=themes_dir)
    sheet = manager.stylesheet(name)
    assert "${" not in sheet
    assert "QPushButton" in sheet


# ----------------------------------------------------------------------
# Seeding and listing
# ----------------------------------------------------------------------


def test_the_builtin_palettes_are_copied_for_editing(themes_dir):
    ThemeManager(themes_dir=themes_dir)
    seeded = {path.name for path in themes_dir.glob("*.json")}
    builtin = {path.name for path in BUILTIN_THEMES_DIR.glob("*.json")}
    assert seeded == builtin


def test_seeding_never_overwrites_an_edited_theme(themes_dir):
    themes_dir.mkdir(parents=True, exist_ok=True)
    target = themes_dir / f"{DEFAULT_THEME}.json"
    target.write_text(json.dumps({"colors": {"accent": "#000000"}}), encoding="utf-8")

    ThemeManager(themes_dir=themes_dir)

    # An edit survives, and so survives a later release of Muralis.
    assert json.loads(target.read_text(encoding="utf-8"))["colors"]["accent"] == "#000000"


def test_listing_includes_the_builtin_themes(themes_dir):
    manager = ThemeManager(themes_dir=themes_dir)
    assert set(THEME_NAMES) <= set(manager.list_themes())


def test_a_user_theme_is_listed(themes_dir):
    manager = ThemeManager(themes_dir=themes_dir)
    (themes_dir / "custom.json").write_text(
        json.dumps({"colors": {"accent": "#123456"}}), encoding="utf-8"
    )
    assert "custom" in manager.list_themes()


def test_an_unwritable_theme_directory_is_tolerated(tmp_path):
    # A read-only config directory must not stop the application starting.
    manager = ThemeManager(themes_dir=tmp_path / "nope" / "themes")
    assert DEFAULT_THEME in manager.list_themes()


# ----------------------------------------------------------------------
# Loading and applying
# ----------------------------------------------------------------------


def test_colors_come_from_the_builtin_theme(themes_dir):
    colors = ThemeManager(themes_dir=themes_dir).load_colors(DEFAULT_THEME)
    assert colors.get("accent") and colors.get("window")


def test_a_user_file_overrides_individual_tokens(themes_dir):
    manager = ThemeManager(themes_dir=themes_dir)
    (themes_dir / f"{DEFAULT_THEME}.json").write_text(
        json.dumps({"colors": {"accent": "#abcdef"}}), encoding="utf-8"
    )

    colors = manager.load_colors(DEFAULT_THEME)

    assert colors["accent"] == "#abcdef"
    # Everything the user did not mention still falls back to the built-in
    # value, so the stylesheet always substitutes and the UI cannot collapse to
    # the platform default.
    assert colors.get("window")


def test_a_malformed_theme_file_is_ignored(themes_dir):
    manager = ThemeManager(themes_dir=themes_dir)
    (themes_dir / f"{DEFAULT_THEME}.json").write_text("{ not json", encoding="utf-8")
    # Falls back to the built-in palette rather than raising.
    assert manager.load_colors(DEFAULT_THEME).get("accent")


def test_apply_without_an_application_is_a_no_op(themes_dir):
    assert ThemeManager(themes_dir=themes_dir).apply(DEFAULT_THEME) is False


def test_apply_sets_a_stylesheet_with_every_token_substituted(qapp, themes_dir):
    manager = ThemeManager(qapp, themes_dir=themes_dir)

    assert manager.apply(DEFAULT_THEME) is True

    sheet = qapp.styleSheet()
    assert "QPushButton" in sheet
    # An unsubstituted placeholder would mean a token is missing from the
    # theme, which is exactly the failure that silently flattens the UI.
    assert "${" not in sheet
    qapp.setStyleSheet("")


def test_apply_sets_a_palette_too(qapp, themes_dir):
    # Qt draws tooltips and other native furniture from the palette, not the
    # stylesheet, so applying only a stylesheet leaves those at the platform
    # default (the ugly 80s yellow).
    manager = ThemeManager(qapp, themes_dir=themes_dir)
    manager.apply(DEFAULT_THEME)

    window = qapp.palette().color(qapp.palette().ColorRole.Window).name()
    assert window.lower() == manager.load_colors(DEFAULT_THEME)["window"].lower()
    qapp.setStyleSheet("")


def test_an_uninstalled_theme_falls_back_to_the_default(qapp, themes_dir):
    # A theme file that has been deleted should not leave the application
    # wearing a neutral palette nobody chose.
    manager = ThemeManager(qapp, themes_dir=themes_dir)
    assert manager.apply("does-not-exist") is True
    assert manager.current.name == DEFAULT_THEME
    qapp.setStyleSheet("")


def test_apply_resolves_the_icon_directory(qapp, themes_dir):
    manager = ThemeManager(qapp, themes_dir=themes_dir)
    manager.apply(DEFAULT_THEME)

    # The spin-box arrows are url() references, which only resolve if the
    # stylesheet carries an absolute path.
    assert "chevron-up.svg" in qapp.styleSheet()
    qapp.setStyleSheet("")


# ----------------------------------------------------------------------
# The object-name contract
# ----------------------------------------------------------------------


def _declared_object_names() -> set:
    """Every object name Muralis's GUI sets, read from its source.

    Read from the source rather than from live widgets on purpose: it catches
    names on code paths a test may not reach, which is where a rename is most
    likely to be missed.
    """
    gui_dir = Path(theme_module.__file__).parent
    names = set()
    for path in sorted(gui_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        names.update(re.findall(r"""setObjectName\(\s*["']([^"']+)["']""", source))
    return names


def test_every_object_name_muralis_sets_is_styled(qapp, themes_dir):
    """No widget is silently unstyled.

    Adopting Gesso's stylesheet meant adopting its object-name vocabulary. A
    name that does not exist in the stylesheet produces no error at all — the
    control simply stops being styled — which is exactly the kind of regression
    a visual check might miss and a test will not.
    """
    names = _declared_object_names()
    assert names, "the GUI should set some object names"

    sheet = ThemeManager(qapp, themes_dir=themes_dir).stylesheet(DEFAULT_THEME)
    missing = sorted(name for name in names if f"#{name}" not in sheet)
    assert missing == [], f"these object names are not styled: {missing}"

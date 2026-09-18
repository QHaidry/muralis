#!/usr/bin/env python3
"""Tests for Muralis's window and its entry point.

The window is the piece the migration changed most, and the piece no existing
test touched: everything above it passed while ``MainWindow`` could have been
constructing nothing at all.

``use_paths`` points Muralis at a temporary profile, so a test never writes into
the developer's real ``~/.config``.

The window fixture is **module-scoped**. Building one constructs every page,
and most of these tests only read from it — a fresh window per test turns a
two-second suite into an eighty-second one. The tests that do change state put
it back, so they stay order-independent.
"""

from __future__ import annotations

import pytest
from gesso.core.paths import AppPaths
from gesso.ui.app import AppShell

from muralis.gui.main_window import NAV_ITEMS, MainWindow


@pytest.fixture(scope="module")
def profile(tmp_path_factory):
    """Run Muralis against a throwaway profile for the whole module."""
    import muralis.context as context

    root = tmp_path_factory.mktemp("profile")
    context.use_paths(AppPaths.resolve("muralis", config_home=root))
    yield root
    context.reset()


@pytest.fixture(scope="module")
def window(qapp, profile):
    return MainWindow()


# ----------------------------------------------------------------------
# The shell
# ----------------------------------------------------------------------


def test_the_window_is_a_gesso_shell(window):
    assert isinstance(window, AppShell)


def test_the_window_title_comes_from_the_spec(window):
    from muralis.context import APP

    assert window.windowTitle() == APP.display_name


def test_every_navigation_entry_has_a_page(window):
    assert window.pages() == [key for key, *_ in NAV_ITEMS]


def test_the_window_starts_on_the_preview_page(window):
    assert window.current_page() == "preview"


def test_showing_a_page_checks_its_navigation_entry(window):
    from PySide6.QtWidgets import QPushButton

    assert window.show_page("settings") is True
    assert window.current_page() == "settings"

    # Only the navigation is exclusive; a settings pane has checkable controls
    # of its own.
    checked = [
        button
        for button in window.findChildren(QPushButton)
        if button.objectName() == "navButton" and button.isChecked()
    ]
    assert len(checked) == 1

    window.show_page("preview")


def test_the_pages_are_the_muralis_widgets(window):
    assert window.page("preview").widget is window.preview_widget
    assert window.page("history").widget is window.history_tab
    assert window.page("settings").widget is window.settings_tab
    assert window.page("about").widget is window.about_page


def test_the_preview_page_offers_its_actions(window):
    # The shell takes a page's buttons and puts them in the header row, without
    # the window having to know what they are.
    assert window.header("preview").actions


# ----------------------------------------------------------------------
# Branding, drawer and status
# ----------------------------------------------------------------------


def test_the_brand_comes_from_the_translations(window):
    from muralis.i18n import t

    assert window.brand_label.text() == t("gui.nav.brand")
    assert window.brand_subtitle.text() == t("gui.nav.brand_subtitle")


def test_the_drawer_button_uses_muralis_own_icon(window):
    assert not window.drawer_button.icon().isNull()


def test_collapsing_retitles_the_drawer_button(window):
    from muralis.i18n import t

    window.set_sidebar_collapsed(True)
    assert window.drawer_button.toolTip() == t("gui.nav.expand")

    window.set_sidebar_collapsed(False)
    assert window.drawer_button.toolTip() == t("gui.nav.collapse")


def test_the_status_line_is_populated(window):
    assert window.status_info.text()


def test_the_status_line_names_the_provider(window):
    from muralis.i18n import t

    # The default provider is bing, which has a translated display name.
    assert window._provider_name("bing") == t("gui.provider.bing")


def test_the_refresh_timer_is_running(window):
    assert window.refresh_timer.isActive()


# ----------------------------------------------------------------------
# Theming
# ----------------------------------------------------------------------


def test_the_stored_theme_is_applied(window):
    from muralis.gui.theme import DEFAULT_THEME

    assert window.theme_manager.current is not None
    assert window.theme_manager.current.name == DEFAULT_THEME


def test_gesso_strings_resolve_through_muralis_translator(window):
    """The shell's own strings go through the application's translator.

    This is the reserved ``gesso.`` domain doing its job: the framework owns
    those keys and the application owns the rest, so the shell can speak
    without the framework shipping a label nobody can change.
    """
    assert window._t("gesso.shell.toggle_navigation") != "gesso.shell.toggle_navigation"
    # An unknown key comes back as itself, so a typo is visible on screen
    # rather than silently blank.
    assert window._t("gesso.shell.nope") == "gesso.shell.nope"


def test_muralis_overrides_the_shells_wording(window):
    from muralis.i18n import t

    assert window.drawer_button.toolTip() == t("gui.nav.collapse")


def test_selecting_a_theme_persists_it(window):
    from muralis.gui.theme import DEFAULT_THEME

    window._set_theme("light")

    assert window.theme_manager.current.name == "light"

    reopened = window._read_config()
    assert reopened.get("gui", "theme", fallback=DEFAULT_THEME) == "light"

    # Put it back, so the other tests do not depend on the order they run in.
    window._set_theme(DEFAULT_THEME)


# ----------------------------------------------------------------------
# The entry point
# ----------------------------------------------------------------------


def test_run_gui_delegates_to_gesso(monkeypatch):
    """The bootstrap is Gesso's now, and this is what it is handed."""
    from muralis.gui import icons, run_gui
    from muralis.i18n import t

    captured = {}

    def fake_run_app(spec, *, shell_factory=None, **kwargs):
        captured["spec"] = spec
        captured["shell_factory"] = shell_factory
        captured["kwargs"] = kwargs
        return 0

    monkeypatch.setattr("gesso.ui.app.run_app", fake_run_app)

    assert run_gui() == 0

    assert captured["spec"].app_id == "muralis"
    # A subclass, so Gesso builds the window Muralis wants rather than one it
    # then throws away.
    assert captured["shell_factory"] is MainWindow
    # Gesso's own strings come through Muralis's translator.
    assert captured["kwargs"]["translate"] is t
    # Muralis's icons are appended to Gesso's, not substituted for them.
    assert icons.ICONS_DIR in captured["kwargs"]["icon_dirs"]
    assert captured["kwargs"]["user_theme_dir"] is not None
    assert captured["kwargs"]["window_icon"] is not None

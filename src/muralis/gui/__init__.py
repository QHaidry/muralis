"""Muralis's graphical entry point, and the pages it is built from."""

from .history_tab import HistoryTab
from .main_window import MainWindow
from .preview_widget import PreviewWidget
from .settings_tab import SettingsTab

__all__ = [
    "MainWindow",
    "SettingsTab",
    "HistoryTab",
    "PreviewWidget",
    "run_gui",
]


def run_gui() -> int:
    """Launch Muralis, returning the event loop's exit code.

    All of this used to be written out here: the ``QApplication`` and its
    metadata, the stored theme, the palette, the window. Gesso's ``run_app``
    does it instead, including two things that were missing — an exception hook,
    so an error inside a slot is not lost to a terminal nobody is reading, and
    the layout direction, so an RTL language mirrors the interface.
    """
    from gesso.ui.app import run_app

    from muralis.context import APP, user_themes_dir
    from muralis.i18n import t

    from . import icons
    from .theme import BUILTIN_THEMES_DIR

    return run_app(
        APP,
        # MainWindow subclasses AppShell, so Gesso builds the window the
        # application actually wants rather than one it then discards.
        shell_factory=MainWindow,
        builtin_theme_dirs=[BUILTIN_THEMES_DIR],
        user_theme_dir=user_themes_dir(),
        # Appended to Gesso's icon directory, not replacing it: the base
        # stylesheet's spin-box arrows come from there.
        icon_dirs=[icons.ICONS_DIR],
        window_icon=icons.app_icon(),
        # Gesso's own strings (the shell's tooltip) come through Muralis's
        # translator, under the reserved ``gesso.`` domain.
        translate=t,
    )


if __name__ == "__main__":
    raise SystemExit(run_gui())

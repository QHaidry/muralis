"""GUI module for Muralis - Smart Wallpaper Manager.

This module provides the graphical user interface for Muralis,
including the main window, settings, history viewer and preview widget.
"""

from .main_window import MainWindow
from .settings_tab import SettingsTab
from .history_tab import HistoryTab
from .preview_widget import PreviewWidget

__all__ = [
    "MainWindow",
    "SettingsTab",
    "HistoryTab",
    "PreviewWidget",
]


def run_gui():
    """Launch Muralis GUI application.

    This is the main entry point for the GUI. It creates the
    QApplication, main window, and starts the event loop.

    Example:
        from muralis.gui import run_gui
        run_gui()
    """
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    from muralis.context import APP

    from .theme import ThemeManager, DEFAULT_THEME
    from .icons import app_icon

    app = QApplication(sys.argv)
    # Identity comes from the application spec, so renaming Muralis is a
    # one-line change rather than a search for the old name.
    app.setApplicationName(APP.display_name)
    app.setOrganizationName(APP.org)
    app.setApplicationDisplayName(APP.display_name)
    app.setWindowIcon(app_icon())

    # Apply the stored theme (or the default) before showing the window
    theme_manager = ThemeManager(app)
    stored = DEFAULT_THEME
    try:
        from .configview import config_view

        stored = config_view().get("gui", "theme", fallback=DEFAULT_THEME)
    except Exception:
        pass
    if not theme_manager.apply(stored):
        theme_manager.apply(DEFAULT_THEME)

    # The palette arrives with the theme: Gesso derives it from the same tokens,
    # so tooltips and other natively-drawn furniture match the theme rather than
    # falling back to the platform default (the ugly 80s yellow).

    # Enable high DPI scaling for better display on high-resolution screens
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # Set application icon (once we have icons)
    # app.setWindowIcon(QIcon(":/icons/muralis.png"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


# Version of the GUI module
__version__ = "0.4.0"

# Module metadata
__author__ = "Qamber Haidry"
__copyright__ = "Copyright (c) 2026 Quoxiom"
__license__ = "MIT"


if __name__ == "__main__":
    """Run the GUI when this module is executed directly."""
    run_gui()

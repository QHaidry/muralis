"""Small shared helpers for Muralis's pages.

Each of these existed, identically, in ``main_window``, ``preview_widget`` and
``history_tab``. Three copies of a "read the mtime, tolerating a vanished file"
guard is three places for a fix to be forgotten, so they live here instead.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from muralis.config import ConfigManager
from muralis.context import DEFAULT_WALLPAPER_DIR, config_path
from muralis.i18n import t

#: Timestamp format used in tooltips.
MODIFIED_TIME_FORMAT = "%d %b %Y %H:%M:%S"

#: Every filename the updater writes, and therefore every file the pages list.
WALLPAPER_GLOB = "muralis_*.jpg"


def safe_mtime(path: Path) -> float:
    """Modified time, tolerating files that vanish between glob and stat."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def formatted_mtime(path: Path) -> str:
    """A wallpaper's modification time, ready for a tooltip."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime(MODIFIED_TIME_FORMAT)
    except OSError:
        return "—"


def config() -> ConfigManager:
    """The application's configuration, for the pages to read."""
    return ConfigManager(str(config_path()))


def wallpaper_dir() -> Path:
    """Where wallpapers actually live — the *configured* directory.

    The pages used to hard-code ``context.DEFAULT_WALLPAPER_DIR`` while the
    updater wrote to ``storage.download_dir``. Changing that setting therefore
    left the preview and history looking at an empty directory that the
    application never wrote to.
    """
    try:
        return config().get_download_dir()
    except Exception:
        return DEFAULT_WALLPAPER_DIR


def list_wallpapers(directory: Path | None = None) -> list[Path]:
    """Every saved wallpaper, newest first."""
    directory = directory if directory is not None else wallpaper_dir()
    if not directory.exists():
        return []
    return sorted(directory.glob(WALLPAPER_GLOB), key=safe_mtime, reverse=True)


def provider_name(key: str) -> str:
    """Localized display name for a provider key, or the key itself."""
    localized = t(f"gui.provider.{key}")
    return key if localized == f"gui.provider.{key}" else localized


def configured_provider() -> str:
    """The provider selected in the configuration."""
    try:
        return config().get_str("general", "provider", "bing")
    except Exception:
        return "bing"

"""Muralis's application identity, and every path derived from it.

Muralis used to scatter its own name across the codebase — ``Path.home() /
".config" / "muralis" / ...`` written out in a dozen places, and ``"Muralis"``
hard-coded as a window title. That made the application impossible to test
without touching the developer's real home directory, and meant a rename was a
grep-and-replace across the whole tree.

Now Muralis declares *who it is* exactly once, and Gesso works out *where*
everything goes. This module is the seam: it is the only place in Muralis that
knows the application id, and the only place that may construct an
:class:`~gesso.core.AppContext`.

The module-level :func:`context` caches a single instance. That is a
deliberate exception to Gesso's no-globals stance: the framework must not force
one application-wide identity on its consumers, but an *application* having one
identity is simply the truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from gesso.core import AppContext, AppSpec
from gesso.core.paths import AppPaths

from muralis._version import __version__

__all__ = [
    "APP",
    "DEFAULT_WALLPAPER_DIR",
    "PACKAGE_DIR",
    "LOCALES_DIR",
    "USER_AGENT",
    "context",
    "use_paths",
    "reset",
    "config_path",
    "user_themes_dir",
    "user_i18n_dir",
    "systemd_user_dir",
    "systemd_unit",
]

#: Muralis's identity. Everything else in this module derives from it.
#:
#: There is deliberately no ``org``: Muralis is a personal project rather than
#: a company product, and Gesso only calls ``setOrganizationName`` when this is
#: set. Leaving it empty means Qt does not advertise a company it does not have.
APP = AppSpec(
    name="Muralis",
    app_id="muralis",
    version=__version__,
    display_name="Muralis",
    description="Smart Wallpaper Manager for Linux",
    default_config_format="json",
)

#: Where downloaded wallpapers are kept, unless the user configures otherwise.
#: This is a *user-visible* location — somewhere people browse with their file
#: manager — not application data, so it deliberately does not live under the
#: XDG data directory.
DEFAULT_WALLPAPER_DIR = Path.home() / "Pictures" / "Muralis"

#: Assets shipped inside the package.
PACKAGE_DIR = Path(__file__).parent
LOCALES_DIR = PACKAGE_DIR / "i18n"

_context: Optional[AppContext] = None


def context() -> AppContext:
    """The process-wide application context."""
    global _context
    if _context is None:
        _context = AppContext(APP)
    return _context


def use_paths(paths: AppPaths) -> AppContext:
    """Point Muralis at an isolated set of directories.

    Used by tests, and by the ``--config`` flag, to keep application state away
    from the user's real profile.
    """
    global _context
    _context = AppContext(APP, paths)
    return _context


def reset() -> None:
    """Forget the cached context, so the next :func:`context` re-resolves it."""
    global _context
    _context = None


def config_path() -> Path:
    """Muralis's configuration file."""
    return context().config_file()


def user_themes_dir() -> Path:
    """Where the user's editable theme files live."""
    return context().paths.subdir("config", "themes")


def user_i18n_dir() -> Path:
    """Where the user's translation overrides live."""
    return context().paths.subdir("config", "i18n")


def systemd_user_dir() -> Path:
    """Where this user's systemd unit files live.

    ``~/.config/systemd/user`` is a systemd convention rather than an XDG
    application directory, so it is derived from the user's config home rather
    than from the application id.
    """
    base = context().paths.config_home
    return Path(base) / "systemd" / "user"


def systemd_unit(name: str) -> Path:
    """The path of Muralis's systemd unit called *name* (``muralis.timer``)."""
    return systemd_user_dir() / name


#: The HTTP User-Agent Muralis identifies itself with.
#:
#: Wikimedia Commons and the Art Institute both answer `python-requests/x.y`
#: with 403 and ask for a descriptive agent with a project URL, so the version
#: and the repository are part of the identity rather than an afterthought.
USER_AGENT = f"{APP.name}/{__version__} (+https://github.com/QHaidry/muralis)"

"""Muralis's icons, on Gesso's registry.

Gesso renders and tints SVG at runtime and searches a list of directories, so
Muralis no longer needs a painter of its own — it needs a registry with its own
icons *layered over* Gesso's.

Layered, not replaced: the base stylesheet draws the spin-box arrows from
Gesso's icon directory, and a private copy would leave them unresolved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtGui import QIcon, QPixmap

from gesso.ui.icons import DEFAULT_TINT
from gesso.ui.icons import ICONS_DIR as GESSO_ICONS_DIR
from gesso.ui.icons import IconRegistry, ThemedIcons

__all__ = [
    "ICONS_DIR",
    "ICON_IDLE",
    "app_icon",
    "make_icon",
    "registry",
    "render_color_pixmap",
    "render_pixmap",
    "themed",
]

#: Muralis's own icons.
ICONS_DIR = Path(__file__).parent / "icons"

#: The tint used for resting icons. Active variants come from the theme.
ICON_IDLE = DEFAULT_TINT

#: The sizes the application logo is rendered at (window and task switcher).
_LOGO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def registry() -> IconRegistry:
    """Gesso's icons, with Muralis's layered over them."""
    found = IconRegistry([GESSO_ICONS_DIR])
    found.add_directory(ICONS_DIR)
    return found


def themed(theme_manager: Any = None) -> ThemedIcons:
    """Icons tinted from a theme, and re-tinted when that theme changes."""
    return ThemedIcons(registry(), theme_manager)


def render_pixmap(name: str, size: int = 18, color: str = ICON_IDLE) -> QPixmap:
    """Render an icon at *size*, tinted with *color*."""
    return registry().render_pixmap(name, size, tint=color)


def render_color_pixmap(name: str, size: int = 18) -> QPixmap:
    """Render an icon preserving its own colours.

    For the logo, where a multicolour design should not be flattened.
    """
    return registry().render_pixmap(name, size, tint=None)


def make_icon(name: str, color: str = ICON_IDLE, size: int = 18) -> QIcon:
    """Build a :class:`QIcon` for the named icon at the given colour and size."""
    return registry().make_icon(name, tint=color, size=size)


def app_icon(tint: Optional[str] = None) -> QIcon:
    """The Muralis logo at every size a window or task switcher asks for.

    Rendered in its own colours by default; *tint* flattens it, which is kept
    for callers that want a monochrome mark.
    """
    return registry().make_icon("muralis", tint=tint, sizes=_LOGO_SIZES)

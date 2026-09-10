"""Greyscale SVG icons for the Muralis GUI.

Icons are rendered at runtime from the bundled SVG files and tinted to the
requested color, so the same artwork can be shown muted (idle), bright
(active), or in the theme accent.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICONS_DIR = Path(__file__).parent / "icons"

# Greyscale icon tint (idle). Active/accent variants come from the theme.
ICON_IDLE = "#9e9e9e"


def render_pixmap(name: str, size: int = 18, color: str = ICON_IDLE) -> QPixmap:
    """Render an SVG icon to a pixmap and tint every pixel with `color`."""
    return _render(name, size, tint=color)


def render_color_pixmap(name: str, size: int = 18) -> QPixmap:
    """Render an SVG icon to a pixmap preserving its original colors.

    Used for the application logo where a multicolor (e.g. sunset gradient)
    design should not be flattened to a single tint.
    """
    return _render(name, size, tint=None)


def _render(name: str, size: int = 18, tint: Optional[str] = None) -> QPixmap:
    renderer = QSvgRenderer(str(ICONS_DIR / f"{name}.svg"))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size, size))
    if tint is not None:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(tint))
    painter.end()
    return pixmap


def make_icon(name: str, color: str = ICON_IDLE, size: int = 18) -> QIcon:
    """Build a QIcon for the named icon at the given color/size."""
    icon = QIcon()
    icon.addPixmap(render_pixmap(name, size, color))
    return icon


def app_icon(tint: Optional[str] = None) -> QIcon:
    """The application icon at multiple sizes (window + taskbar).

    Renders the multicolor muralis logo by default. ``tint`` is accepted for
    backward compatibility: when provided it flattens the logo to that colour.
    """
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        if tint is None:
            icon.addPixmap(render_color_pixmap("muralis", size))
        else:
            icon.addPixmap(render_pixmap("muralis", size, tint))
    return icon

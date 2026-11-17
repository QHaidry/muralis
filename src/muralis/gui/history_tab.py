"""History tab for Muralis GUI."""

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
)

from muralis.i18n import t

from . import support


class _Thumb(QFrame):
    """A wallpaper thumbnail: click/double-click sets it as wallpaper."""

    def __init__(self, path: Path, applied_cb: Optional[Callable], parent=None):
        super().__init__(parent)
        self.setObjectName("thumbFrame")
        self._path = path
        self._applied_cb = applied_cb

        layout = QVBoxLayout(self)

        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                200,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image_label = QLabel()
            image_label.setPixmap(scaled)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setToolTip(self._build_tooltip())
            layout.addWidget(image_label)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_tooltip(self) -> str:
        try:
            size_kb = self._path.stat().st_size / 1024
        except OSError:
            size_kb = 0.0
        downloaded = support.formatted_mtime(self._path)
        provider = support.provider_name(support.configured_provider())
        return (
            f"{t('gui.preview.tooltip.name', name=self._path.name)}\n"
            f"{t('gui.preview.tooltip.downloaded', time=downloaded)}\n"
            f"{t('gui.preview.tooltip.size', kb=size_kb)}\n"
            f"{t('gui.preview.tooltip.provider', name=provider)}\n"
            f"{t('gui.history.tip')}"
        )

    def _set(self):
        from muralis.setter import get_wallpaper_setter

        setter = get_wallpaper_setter()
        if setter.set_wallpaper(str(self._path)):
            if self._applied_cb:
                self._applied_cb()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._set()
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self._set()
        super().mouseReleaseEvent(event)


class HistoryTab(QWidget):
    """History tab showing past wallpapers."""

    def __init__(
        self,
        refresh_callback: Optional[Callable] = None,
        wallpaper_applied_callback: Optional[Callable] = None,
        parent=None,
    ):
        """Initialize the history tab.

        Args:
            refresh_callback: Called to fetch a NEW wallpaper (Refresh).
            wallpaper_applied_callback: Called after setting a wallpaper so the
                preview updates WITHOUT re-downloading.
            parent: Parent widget
        """
        super().__init__(parent)

        self.refresh_callback = refresh_callback
        self.wallpaper_applied_callback = wallpaper_applied_callback

        # Refresh button (placed in the page header, top-right, by the caller).
        self.refresh_btn = QPushButton(t("gui.history.refresh"))
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.thumbnails_widget = QWidget()
        self.thumbnails_layout = QGridLayout(self.thumbnails_widget)
        self.thumbnails_layout.setContentsMargins(0, 0, 0, 0)
        # self.thumbnails_layout.setSpacing(0)
        scroll.setWidget(self.thumbnails_widget)

        layout.addWidget(scroll)

        self.refresh_history()

    def action_buttons(self) -> list:
        """Action buttons for the page header row (Refresh, top-right)."""
        return [self.refresh_btn]

    def _clear_thumbnails(self):
        if not self.thumbnails_layout:
            return
        while self.thumbnails_layout.count():
            item = self.thumbnails_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

    def _on_refresh_clicked(self):
        if self.refresh_callback:
            self.refresh_callback()
        else:
            self.refresh_history()

    def refresh_history(self):
        self._clear_thumbnails()

        folder = support.wallpaper_dir()
        wallpapers = support.list_wallpapers(folder)
        if not wallpapers:
            # "You have not downloaded anything yet" and "that folder is not
            # there" are different situations and deserve different wording.
            message = "gui.history.empty" if not folder.exists() else "gui.history.empty_short"
            no_wallpapers = QLabel(t(message))
            no_wallpapers.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.thumbnails_layout.addWidget(no_wallpapers, 0, 0)
            return

        cols = 4
        for i, wallpaper in enumerate(wallpapers[:50]):  # Limit to 50
            row = i // cols
            col = i % cols
            thumb = _Thumb(wallpaper, self.wallpaper_applied_callback)
            self.thumbnails_layout.addWidget(thumb, row, col)

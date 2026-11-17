"""Wallpaper preview widget for Muralis GUI."""

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QSizePolicy

from muralis.i18n import t

from . import support

PREVIEW_SIZE = (800, 450)  # fallback for freshly-downloaded images without a saved size


class PreviewWidget(QWidget):
    """Wallpaper preview: an expanding image with a rich tooltip."""

    def __init__(self, refresh_callback: Optional[Callable] = None, parent=None):
        super().__init__(parent)

        self.refresh_callback = refresh_callback
        self.local_image_callback: Optional[Callable] = None
        self._pixmap: Optional[QPixmap] = None
        self._tooltip = ""

        layout = QVBoxLayout(self)
        # Match the Settings content pane's left indentation so all pages align.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Expands in both directions — the sole body of the preview.
        self.preview_label = QLabel()
        self.preview_label.setObjectName("card")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setToolTip("")
        layout.addWidget(self.preview_label, 1)

        # Action buttons (text-only, styled like the rest of the UI). They are
        # placed right-aligned in the page header row by MainWindow._make_page.
        self.refresh_btn = self._make_action_button(t("gui.preview.refresh"))
        self.open_folder_btn = self._make_action_button(t("gui.preview.open_folder"))
        self.set_local_btn = self._make_action_button(t("gui.preview.set_local"))
        self.refresh_btn.clicked.connect(self.request_refresh)
        self.open_folder_btn.clicked.connect(self.open_wallpaper_folder)
        self.set_local_btn.clicked.connect(self.choose_local_image)

    def action_buttons(self) -> list:
        """Return the action buttons for the page header row."""
        return [self.set_local_btn, self.refresh_btn, self.open_folder_btn]

    def _make_action_button(self, label: str) -> QPushButton:
        button = QPushButton(label)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        return button

    def request_refresh(self):
        if self.refresh_callback:
            self.refresh_callback()
        else:
            print("No refresh callback set")

    def load_current_wallpaper(self):
        wallpapers = support.list_wallpapers()
        if wallpapers:
            self.display_wallpaper(wallpapers[0])
            return
        self._pixmap = None
        self.preview_label.setText(t("gui.preview.none_hint"))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setToolTip("")

    def display_wallpaper(self, image_path: Path):
        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            self._pixmap = pixmap
            self._update_preview()

            size_kb = image_path.stat().st_size / 1024
            downloaded = support.formatted_mtime(image_path)
            provider = support.provider_name(support.configured_provider())

            # Name + rich details on hover, not as cluttering on-screen text.
            self._tooltip = (
                f"{t('gui.preview.tooltip.name', name=image_path.name)}\n"
                f"{t('gui.preview.tooltip.downloaded', time=downloaded)}\n"
                f"{t('gui.preview.tooltip.size', kb=size_kb)}\n"
                f"{t('gui.preview.tooltip.provider', name=provider)}"
            )
            self.preview_label.setToolTip(self._tooltip)
        else:
            self._pixmap = None
            self.preview_label.setText(t("gui.preview.failed"))
            self.preview_label.setToolTip("")

    def _update_preview(self):
        if self._pixmap is None:
            return
        size = self.preview_label.size()
        if size.width() < 4 or size.height() < 4:
            return
        scaled = self._pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_preview()

    def refresh_preview(self):
        self.load_current_wallpaper()

    def open_wallpaper_folder(self):
        import subprocess

        folder = support.wallpaper_dir()
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["xdg-open", str(folder)])

    def choose_local_image(self):
        """Open a file dialog and pass the chosen image to the application."""
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            t("gui.dialog.pick_title"),
            str(Path.home()),
            t("gui.preview.pick_local") + " (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)",
        )
        if path and self.local_image_callback:
            self.local_image_callback(path)

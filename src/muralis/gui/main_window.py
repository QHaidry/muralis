"""Muralis's window.

Gesso's :class:`~gesso.ui.app.AppShell` provides the sidebar, the navigation,
the content stack and the status bar. This adds only what Muralis knows about:
the live status line, the daily update check, and the wallpaper actions.

That is the whole of the migration. The shell used to be built here — drawer,
brand, exclusive button group, page wrappers, collapse handling, icon
re-tinting — and all of it is the same in every desktop application.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gesso.ui.app import AppShell
from gesso.ui.widgets import Card

from muralis import __version__
from muralis.context import APP, DEFAULT_WALLPAPER_DIR, config_path
from muralis.i18n import t

from . import icons as muralis_icons
from .configview import config_view
from .history_tab import HistoryTab
from .preview_widget import PreviewWidget
from .settings_tab import SettingsTab
from .theme import DEFAULT_THEME, ThemeManager

#: Navigation entries: ``(key, icon name, label key, comment key)``.
NAV_ITEMS = [
    ("preview", "preview", "gui.nav.preview", "gui.page.preview_subtitle"),
    ("history", "history", "gui.nav.history", "gui.page.history_subtitle"),
    ("settings", "settings", "gui.nav.settings", "gui.page.settings_subtitle"),
    ("about", "about", "gui.nav.about", ""),
]

#: How often the preview refreshes and the daily update is checked.
_REFRESH_INTERVAL_MS = 60_000


def _safe_mtime(path: Path) -> float:
    """Modified time, tolerating files that vanish between glob and stat."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


class MainWindow(AppShell):
    """Muralis's window: Gesso's shell, wired to Muralis's pages."""

    def __init__(
        self,
        spec: Any = APP,
        *,
        theme_manager: Any = None,
        icons: Any = None,
        translate: Any = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        # Constructed directly — by a test, or by an embedder — there is no
        # bootstrap to supply icons or a translator, so default to Muralis's
        # own rather than rendering blank buttons and untranslated labels.
        super().__init__(
            spec,
            theme_manager=theme_manager,
            icons=icons if icons is not None else muralis_icons.themed(theme_manager),
            translate=translate if translate is not None else t,
            parent=parent,
        )

        # Likewise there may be no manager yet.
        if self.theme_manager is None:
            self.theme_manager = ThemeManager(self)

        self.setWindowIcon(muralis_icons.app_icon())
        self.setMinimumSize(1000, 700)
        self.resize(1150, 780)

        # Muralis has its own drawer glyph, and its own wording for what the
        # drawer does — the shell's default is generic.
        self.drawer_button.set_icon("drawer")
        self.drawer_button.setToolTip(t("gui.nav.collapse"))

        self.set_brand(t("gui.nav.brand"), t("gui.nav.brand_subtitle"))
        self._build_pages()
        self._build_refresh_timer()

        self._apply_stored_theme()
        self.set_message(t("gui.status.ready"))
        self.show_page("preview")
        self._load_current_wallpaper()
        self._update_status_bar()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_pages(self) -> None:
        """Gesso's shell builds the navigation entry alongside each page."""
        self.preview_widget = PreviewWidget(
            refresh_callback=self._refresh_wallpaper, parent=self
        )
        self.preview_widget.local_image_callback = self._set_local_image
        self.history_tab = HistoryTab(
            refresh_callback=self._refresh_wallpaper,
            wallpaper_applied_callback=self._load_current_wallpaper,
            parent=self,
        )
        self.settings_tab = SettingsTab(
            theme_manager=self.theme_manager,
            on_theme_change=self._set_theme,
            on_settings_changed=self._update_status_bar,
            on_auto_update_changed=self._setup_auto_update_scheduler,
            parent=self,
        )
        self.about_page = self._build_about_page()

        widgets = {
            "preview": self.preview_widget,
            "history": self.history_tab,
            "settings": self.settings_tab,
            "about": self.about_page,
        }

        for key, icon_name, label_key, comment_key in NAV_ITEMS:
            widget = widgets[key]
            actions = widget.action_buttons() if hasattr(widget, "action_buttons") else ()
            self.add_page(
                key,
                t(label_key),
                widget,
                comment=t(comment_key) if comment_key else "",
                icon=icon_name,
                actions=actions,
            )

    def _build_about_page(self) -> QWidget:
        """The About page: the logo, the version and two links."""
        page = QWidget()
        layout = QVBoxLayout(page)
        # Match the Settings content pane's indentation so all pages align.
        layout.setContentsMargins(0, 0, 0, 0)

        card = Card(margins=28, spacing=8)

        logo = QLabel()
        logo.setPixmap(muralis_icons.render_color_pixmap("muralis", 64))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.body.addWidget(logo)

        title = QLabel(t("gui.nav.brand"))
        title.setObjectName("displayTitle")
        card.body.addWidget(title)

        desc = QLabel(t("gui.about.desc"))
        desc.setWordWrap(True)
        card.body.addWidget(desc)

        version = QLabel(t("gui.about.version", version=__version__))
        version.setObjectName("pageSubtitle")
        card.body.addWidget(version)

        card.body.addSpacing(8)

        for url, label in (
            ("https://github.com/quoxiom/muralis", t("gui.about.github")),
            ("https://github.com/quoxiom/muralis/wiki", t("gui.about.docs")),
        ):
            link = QLabel(f'<a href="{url}">{label}</a>')
            link.setObjectName("link")
            link.setOpenExternalLinks(True)
            card.body.addWidget(link)

        card.body.addStretch()
        layout.addWidget(card)
        return page

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        """Collapse the drawer, and retitle its button for what it will do."""
        super().set_sidebar_collapsed(collapsed)
        self.drawer_button.setToolTip(t("gui.nav.expand" if collapsed else "gui.nav.collapse"))

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def _apply_stored_theme(self) -> None:
        """Apply the theme saved in the config (default: reasonix)."""
        theme_id = self._read_config().get("gui", "theme", fallback=DEFAULT_THEME)
        if not self.apply_theme(theme_id):
            self.apply_theme(DEFAULT_THEME)
        self.setWindowIcon(muralis_icons.app_icon())

    def _set_theme(self, theme_id: str) -> None:
        """Apply a theme and persist the choice."""
        if not self.apply_theme(theme_id):
            return
        self.setWindowIcon(muralis_icons.app_icon())
        try:
            config = self._read_config()
            config.set("gui", "theme", theme_id)
            config.save()
        except OSError:
            # A read-only config directory: the theme applies for this session.
            pass

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _read_config(self):
        """Read the config (ConfigParser-compatible facade over JSON)."""
        return config_view()

    def _provider_name(self, key: str) -> str:
        """Localized display name for a provider key."""
        localized = t(f"gui.provider.{key}")
        return key if localized == f"gui.provider.{key}" else localized

    def _update_status_bar(self) -> None:
        """Refresh the status bar info (image, provider, daily update)."""
        image_name = "—"
        if DEFAULT_WALLPAPER_DIR.exists():
            wallpapers = sorted(
                DEFAULT_WALLPAPER_DIR.glob("muralis_*.jpg"), key=_safe_mtime, reverse=True
            )
            if wallpapers:
                image_name = wallpapers[0].name

        config = self._read_config()
        provider = config.get("general", "provider", fallback="bing")

        sep = t("gui.statusbar.sep")
        timer_path = Path.home() / ".config/systemd/user/muralis.timer"
        if timer_path.exists():
            fetch_time = self._next_fetch_time(timer_path)
            provider_display = self._provider_name(provider)
            schedule = t("gui.statusbar.update_on", provider=provider_display, time=fetch_time)
            next_fetch = t("gui.statusbar.update_next", time=fetch_time)
            update_text = f"{schedule}{sep}{next_fetch}"
        else:
            update_text = t("gui.statusbar.update_off")

        parts = [
            t("gui.statusbar.image", name=image_name),
            t("gui.statusbar.provider", name=self._provider_name(provider)),
            update_text,
        ]
        self.set_info(sep.join(parts))

    @staticmethod
    def _next_fetch_time(timer_path: Path) -> str:
        """Parse the systemd timer's OnCalendar and format the next run."""
        hour = 9
        minute = 0  # defaults match the shipped timer template (09:00)
        try:
            for line in timer_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("OnCalendar="):
                    spec = line.split("=", 1)[1].strip()
                    # e.g. "*-*-* 09:00:00"
                    time_part = spec.split()[-1]
                    parts = time_part.split(":")
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                    break
        except (OSError, ValueError):
            pass

        now = datetime.now()
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return candidate.strftime("%d %b %Y %H:%M")

    # ------------------------------------------------------------------
    # Wallpaper actions
    # ------------------------------------------------------------------
    def _load_current_wallpaper(self) -> None:
        """Load and display the current wallpaper."""
        self.preview_widget.load_current_wallpaper()

    def _set_local_image(self, path: str) -> None:
        """Set a user-picked local image as the wallpaper."""
        from muralis.app import MuralisApp

        from .dialogs import warning

        self.set_message(t("gui.status.updating"))
        try:
            app = MuralisApp(str(config_path()))
            if app.set_local_image(path):
                self.set_message(t("gui.preview.set_success"), 3000)
                self._load_current_wallpaper()
                self._update_status_bar()
            else:
                self.set_message(t("gui.preview.set_failed"), 3000)
                warning(self, t("gui.dialog.error_title"), t("gui.preview.set_failed"))
        except Exception as e:
            self.set_message(t("gui.status.error", error=str(e)), 5000)
            warning(self, t("gui.dialog.error_title"), t("gui.preview.not_image"))

    def _refresh_wallpaper(self) -> None:
        """Fetch and apply a new wallpaper."""
        from muralis.app import MuralisApp

        self.set_message(t("gui.status.updating"))
        try:
            app = MuralisApp(str(config_path()))
            if app.run_once():
                self.set_message(t("gui.status.success"), 3000)
                self._load_current_wallpaper()
                self.history_tab.refresh_history()
                self._update_status_bar()
            else:
                self.set_message(t("gui.status.failed"), 3000)
                from .dialogs import warning

                warning(self, t("gui.dialog.error_title"), t("gui.dialog.failed_update"))
        except Exception as e:
            self.set_message(t("gui.status.error", error=str(e)), 5000)
            from .dialogs import critical

            critical(
                self,
                t("gui.dialog.error_title"),
                t("gui.dialog.failed_update_detail", error=str(e)),
            )

    def _setup_auto_update_scheduler(self, enable: bool) -> None:
        """Install or remove the background (systemd) daily timer."""
        from muralis.app import MuralisApp
        from muralis.scheduler import SchedulerManager

        app = MuralisApp(str(config_path()))
        scheduler = SchedulerManager(app.config)
        if enable:
            scheduler.setup()
        else:
            scheduler.disable()

    # ------------------------------------------------------------------
    # Periodic refresh
    # ------------------------------------------------------------------
    def _build_refresh_timer(self) -> None:
        """Refresh the preview once a minute, and check the daily update."""
        self._last_daily_run: Optional[str] = None
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._auto_refresh_preview)
        self.refresh_timer.start(_REFRESH_INTERVAL_MS)

    def _auto_refresh_preview(self) -> None:
        self.preview_widget.refresh_preview()
        self._check_scheduled_update()

    def _check_scheduled_update(self) -> None:
        """Run the wallpaper update if auto-update is on and the time matches."""
        from datetime import date

        try:
            if not self._read_config().getboolean("general", "auto_update", fallback=True):
                return
            time_str = self._read_config().get("scheduling", "update_time", fallback="09:00")
            hour, minute = map(int, time_str.split(":"))
            now = datetime.now()
            if (
                now.hour == hour
                and now.minute == minute
                and self._last_daily_run != date.today().isoformat()
            ):
                self._last_daily_run = date.today().isoformat()
                self._refresh_wallpaper()
        except (ValueError, AttributeError):
            pass

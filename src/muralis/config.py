"""Configuration management for Muralis, backed by Gesso.

The schema below is the single source of truth for what Muralis can be
configured with: every setting's type, default and constraints. Gesso handles
the rest — the file format, coercion, validation and atomic writes.

It replaces a stringly-typed ``DEFAULT_CONFIG``, in which every value was a
string and every read site had to remember to convert it. That is the kind of
design that works right up until a second file format arrives, at which point
``auto_update = "true"`` becomes a *string* in TOML and the bugs start.

The INI format is gone. A legacy ``config.ini`` is still imported **once**, on
first load, and then deleted; nothing writes INI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from gesso.config import ConfigError, ConfigStore, Option, Schema, Section

from muralis.context import APP
from muralis.context import config_path as app_config_path
from muralis.i18n import t
from muralis.providers import ALL_PROVIDERS
from muralis.providers.pexels import PexelsProvider


class ConfigValidationError(Exception):
    """Raised when a value is not acceptable for its setting."""


def available_config_formats() -> List[str]:
    """The configuration formats this installation can both read and write.

    Deliberately dynamic rather than a constant: TOML and YAML need optional
    dependencies, so offering them as a choice when they cannot be used would
    turn a clear "install this extra" message into a confusing failure.
    """
    from gesso.config import builtin_codecs

    return [codec.name for codec in builtin_codecs() if codec.available()]


#: ``1920x1080`` and friends.
_RESOLUTION = r"^\d{3,4}x\d{3,4}$"
#: ``HH:MM``, 24-hour.
_TIME = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"

_EFFECTS = ["none", "blur", "darken", "grayscale", "vibrant", "vignette"]

# ----------------------------------------------------------------------
# The schema
# ----------------------------------------------------------------------
MURALIS_SCHEMA = Schema(
    [
        Section(
            "general",
            title="General",
            options=(
                Option(
                    "provider", str, "bing", "Default wallpaper provider.", choices=ALL_PROVIDERS
                ),
                Option("auto_update", bool, True, "Update the wallpaper on a schedule."),
                Option(
                    "update_interval",
                    int,
                    86400,
                    "Seconds between updates.",
                    minimum=300,
                    maximum=604800,
                ),
                Option("randomize_provider", bool, False, "Pick a random provider each day."),
                Option(
                    "fallback_provider",
                    str,
                    "bing",
                    "Used when the primary fails.",
                    choices=ALL_PROVIDERS,
                ),
                Option("timezone", str, "UTC", "Timezone for scheduling."),
                Option("offline_mode", bool, False, "Never make network requests."),
                Option("network_timeout", int, 30, "Network timeout, in seconds."),
                Option("retry_attempts", int, 3, "Attempts before giving up."),
            ),
        ),
        Section(
            "image",
            title="Image",
            options=(
                Option(
                    "resolution", str, "3840x2160", "Requested wallpaper size.", pattern=_RESOLUTION
                ),
                Option("apply_effects", bool, False, "Apply an image effect."),
                Option("effect_type", str, "none", "Which effect to apply.", choices=_EFFECTS),
                Option("jpeg_quality", int, 90, "JPEG quality.", minimum=1, maximum=100),
                Option(
                    "fit_mode",
                    str,
                    "zoom",
                    "How the image is fitted.",
                    choices=["zoom", "fill", "fit", "stretch", "center"],
                ),
                Option("upscale_image", bool, False, "Upscale small images."),
                Option("upscale_factor", int, 2, "Upscale multiplier."),
                Option("maintain_aspect_ratio", bool, True, "Preserve the aspect ratio."),
                Option(
                    "image_format",
                    str,
                    "jpg",
                    "Saved image format.",
                    choices=["jpg", "png", "webp"],
                ),
                Option("color_profile", str, "auto", "Colour profile handling."),
                Option("watermark", bool, False, "Overlay a watermark."),
                Option("watermark_position", str, "bottom-right", "Watermark corner."),
                Option("watermark_text", str, "Muralis", "Watermark text."),
            ),
        ),
        Section(
            "storage",
            title="Storage",
            options=(
                Option("save_downloads", bool, True, "Keep downloaded wallpapers."),
                Option("download_dir", str, "~/Pictures/Muralis", "Where wallpapers are saved."),
                Option("max_files", int, 100, "Maximum files to keep.", minimum=0, maximum=10000),
                Option("max_days", int, 30, "Maximum age in days.", minimum=0, maximum=365),
                Option("keep_favorites", bool, False, "Never delete favourited images."),
                Option("organize_by", str, "date", "How the directory is organised."),
                Option("create_subdirs", bool, True, "Create subdirectories."),
                Option("auto_tag", bool, True, "Tag downloads automatically."),
                Option("sync_to_cloud", bool, False, "Sync the library to cloud storage."),
                Option("sync_path", str, "", "Cloud sync location."),
                Option("compression_level", int, 6, "Compression level.", minimum=0, maximum=9),
            ),
        ),
        Section(
            "scheduling",
            title="Scheduling",
            options=(
                Option("update_time", str, "09:00", "Time of day to update.", pattern=_TIME),
                Option(
                    "random_delay_minutes",
                    int,
                    30,
                    "Random delay before updating.",
                    minimum=0,
                    maximum=120,
                ),
                Option("update_on_boot", bool, False, "Update at login."),
                Option("update_on_wake", bool, True, "Update after resuming."),
                Option(
                    "minimum_interval_hours",
                    int,
                    6,
                    "Minimum hours between updates.",
                    minimum=1,
                    maximum=24,
                ),
                Option("skip_on_battery", bool, False, "Skip when on battery."),
                Option("only_on_wifi", bool, True, "Only update on Wi-Fi."),
            ),
        ),
        Section(
            "networking",
            title="Networking",
            options=(
                Option("proxy_enabled", bool, False, "Use a proxy."),
                Option("proxy_url", str, "", "Proxy URL."),
                Option("proxy_username", str, "", "Proxy username."),
                Option("proxy_password", str, "", "Proxy password."),
                Option("user_agent", str, "Muralis/1.0", "HTTP User-Agent."),
                Option("verify_ssl", bool, True, "Verify TLS certificates."),
                Option("download_timeout", int, 30, "Download timeout, in seconds."),
                Option("max_redirects", int, 5, "Maximum HTTP redirects."),
            ),
        ),
        Section(
            "wallpaper_effects",
            title="Wallpaper effects",
            options=(
                Option("daily_theme", bool, False, "Vary the effect through the day."),
                Option("morning_effect", str, "bright", "Morning effect."),
                Option("afternoon_effect", str, "vibrant", "Afternoon effect."),
                Option("evening_effect", str, "warm", "Evening effect."),
                Option("night_effect", str, "dark", "Night effect."),
                Option("auto_adjust_brightness", bool, False, "Adjust brightness automatically."),
                Option("auto_adjust_contrast", bool, False, "Adjust contrast automatically."),
                Option("dominant_color", bool, False, "Theme from the dominant colour."),
            ),
        ),
        Section(
            "logging",
            title="Logging",
            options=(
                Option(
                    "log_level",
                    str,
                    "INFO",
                    "Logging verbosity.",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                ),
                Option("log_file", str, "~/.local/share/muralis/muralis.log", "Log file."),
                Option("log_rotation_days", int, 30, "Days before a log is rotated."),
                Option("debug_mode", bool, False, "Enable debug logging."),
                Option("log_http_traffic", bool, False, "Log HTTP requests."),
            ),
        ),
        Section(
            "notifications",
            title="Notifications",
            options=(Option("enabled", bool, True, "Show desktop notifications."),),
        ),
        Section(
            "advanced",
            title="Advanced",
            options=(
                Option("config_version", int, 2, "Schema version, for migrations."),
                Option("experimental_features", bool, False, "Enable unfinished features."),
                Option("cache_enabled", bool, True, "Cache provider responses."),
                Option("cache_size_mb", int, 500, "Cache size, in MB.", minimum=100, maximum=5000),
                Option("parallel_downloads", int, 1, "Concurrent downloads.", minimum=1, maximum=5),
                Option("max_connections", int, 5, "Maximum concurrent connections."),
            ),
        ),
        Section(
            "api_keys",
            title="API keys",
            description=(
                "Credentials for providers that need them. Prefer the platform "
                "keyring over this file; see the roadmap."
            ),
            options=(
                Option("unsplash_key", str, "", "Unsplash access key."),
                # Public demo key (rate-limited). Users should register their own
                # at https://www.pexels.com/api and override with
                # `muralis --set-key pexels ...`.
                Option("pexels_key", str, PexelsProvider.API_KEY, "Pexels access key."),
                Option("flickr_key", str, "", "Flickr API key."),
                Option("flickr_secret", str, "", "Flickr API secret."),
            ),
        ),
    ]
)


class _SectionView(dict):
    """A live, mutating view of one config section.

    ``config["general"]["provider"] = "nasa"`` has to keep working, but the
    value must still pass through the typed store rather than being written
    into a plain dict. Subclassing ``dict`` keeps the read side (``in``,
    iteration, ``.get``, ``.items``) honest, and routes writes back through
    :meth:`ConfigManager.set_value`.
    """

    def __init__(self, manager: "ConfigManager", section: str) -> None:
        super().__init__(manager._store.get(section) or {})
        self._manager = manager
        self._section = section

    def __setitem__(self, key: str, value: Any) -> None:
        self._manager.set_value(self._section, key, value, save=False)
        super().__setitem__(key, self._manager._store.get(self._section, {}).get(key))

    def update(self, *args: Any, **kwargs: Any) -> None:
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key not in self:
            self[key] = default
        return self[key]


class ConfigManager:
    """Muralis's configuration, on top of Gesso's typed store.

    The public surface is deliberately the one Muralis already had, so the CLI,
    the GUI, the scheduler and the updater did not have to change shape.
    """

    # Class-level cache: resolved path -> instance
    _instances: Dict[str, "ConfigManager"] = {}

    # The Gesso store backing this manager; assigned in ``__init__``. Declared
    # here so ``_SectionView`` (defined above) and the cached-instance branch
    # can use it before mypy sees the assignment.
    _store: ConfigStore

    def __new__(cls, config_path: Optional[str] = None, **kwargs: Any) -> ConfigManager:
        """Create or return the instance for a given config path.

        The format participates in the cache key, so asking for the same path
        in two different formats does not silently hand back the first one.
        """
        resolved = str(cls._resolve_path(config_path, kwargs.get("format")))
        if resolved in cls._instances:
            return cls._instances[resolved]
        instance = super().__new__(cls)
        cls._instances[resolved] = instance
        return instance

    def __init__(self, config_path: Optional[str] = None, *, format: Optional[str] = None):
        """Open Muralis's configuration.

        Args:
            config_path: An explicit file. Its suffix picks the format. When
                omitted, the path comes from the application context and the
                format is discovered.
            format: Force a format (``json``, ``toml`` or ``yaml``) instead.
        """
        if getattr(self, "_initialised", False):
            # Cached instance: refresh from disk so external edits take effect.
            self._store.load()
            return

        self.config_path = self._resolve_path(config_path, format)
        try:
            self._store = ConfigStore.for_path(MURALIS_SCHEMA, self.config_path)
        except ConfigError as exc:
            raise ConfigValidationError(str(exc)) from exc
        self._store.load()

        self._initialised = True
        if self._import_legacy_ini():
            return
        if not self.config_path.exists():
            self._store.save()
            print(t("cli.config.created", path=self.config_path))

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_path(config_path: Optional[str] = None, format: Optional[str] = None) -> Path:
        """Work out which file to use.

        An explicit path wins; otherwise the application context decides, and
        *format* selects the extension.

        A ``.ini`` path is deliberately reinterpreted as its sibling in the
        application's default format. INI is no longer a supported format, so
        an older caller — or a user's shell history — still gets a working
        configuration, with their old settings imported, rather than an error.
        """
        if config_path:
            path = Path(config_path).expanduser().absolute()
        else:
            path = app_config_path()
        if format is not None:
            path = path.with_suffix(f".{format.lstrip('.')}")
        elif path.suffix.lower() == ".ini":
            path = path.with_suffix(f".{APP.default_config_format}")
        return path

    # ------------------------------------------------------------------
    # Legacy INI import (one time only)
    # ------------------------------------------------------------------
    def _import_legacy_ini(self) -> bool:
        """Import a pre-0.5 ``config.ini`` once, then delete it.

        Only runs when the target file does not exist, so it can never
        overwrite settings the user has since changed. Values that no longer
        satisfy the schema are dropped rather than imported.
        """
        legacy = self.config_path.with_suffix(".ini")
        if legacy == self.config_path or not legacy.exists() or self.config_path.exists():
            return False

        import configparser

        parser = configparser.ConfigParser()
        try:
            parser.read(legacy)
        except Exception:
            return False

        known = {section.name for section in MURALIS_SCHEMA.sections}
        for section in parser.sections():
            if section not in known:
                continue
            for key, value in parser.items(section):
                try:
                    self.set_value(section, key, value, save=False)
                except ConfigValidationError:
                    # A legacy value the current schema rejects is not worth
                    # failing the upgrade over; the default stands.
                    pass
        self._store.save()
        try:
            legacy.unlink()
        except OSError:
            pass
        return True

    # ------------------------------------------------------------------
    # Instance cache helpers
    # ------------------------------------------------------------------
    @classmethod
    def clear_cache(cls):
        cls._instances.clear()

    @classmethod
    def get_instance_count(cls) -> int:
        return len(cls._instances)

    @classmethod
    def get_instance_paths(cls) -> List[str]:
        return list(cls._instances.keys())

    # ------------------------------------------------------------------
    # Disk I/O
    # ------------------------------------------------------------------
    def load(self):
        """Re-read the configuration from disk."""
        self._store.load()

    def save(self):
        """Write the configuration to disk, atomically."""
        self._store.save()

    def create_default(self):
        """Reset every setting to its schema default and write it out."""
        self._store.reset()
        self._store.save()
        print(t("cli.config.created", path=self.config_path))

    # ------------------------------------------------------------------
    # Format
    # ------------------------------------------------------------------
    @property
    def format(self) -> str:
        """The format of the file in use (``json``, ``toml`` or ``yaml``)."""
        return self._store.format

    def convert(self, fmt: str) -> Path:
        """Rewrite the configuration in another format, and return its path.

        The previous file is kept alongside as ``<name>.bak``, so changing your
        mind is a rename rather than a lost configuration.
        """
        try:
            new_path = self._store.convert_to(fmt)
        except ConfigError as exc:
            raise ConfigValidationError(str(exc)) from exc

        # Re-key the instance cache: the manager now belongs to the new file,
        # and asking for the old path must not hand back this same object.
        for key, instance in list(type(self)._instances.items()):
            if instance is self:
                del type(self)._instances[key]
        type(self)._instances[str(new_path)] = self

        self.config_path = new_path
        return new_path

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> List[str]:
        """Report problems with the current settings, and return them.

        Advisory: this never raises and never mutates. A malformed preference
        should not stop someone opening their application.
        """
        errors = self._store.validate()
        if errors:
            print(t("cli.warn.validation"))
            for error in errors:
                print(f"  • {error}")
            print(t("cli.warn.validation_continue"))
        return errors

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------
    def get_str(self, section: str, key: str, fallback: str = "") -> str:
        value = self._store.get(f"{section}.{key}")
        return str(value) if value is not None else fallback

    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """Read a boolean.

        Lenient on purpose: a key the schema does not know about is stored
        verbatim, so a string from an imported or hand-edited file is still
        worth interpreting rather than silently falling back.
        """
        value = self._store.get(f"{section}.{key}")
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "1", "on", "enabled")
        return fallback

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Read an integer, tolerating a numeric string for an unknown key."""
        value = self._store.get(f"{section}.{key}")
        if isinstance(value, bool):
            return fallback
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return fallback
        return fallback

    def get_optional(self, section: str, key: str) -> Optional[str]:
        value = self._store.get(f"{section}.{key}")
        if value is None or value == "":
            return None
        return str(value)

    # ------------------------------------------------------------------
    # ConfigParser-compatible surface
    #
    # Thin aliases so the GUI and legacy call sites can keep using
    # ConfigParser-style calls without a separate facade.
    # ------------------------------------------------------------------
    def get(self, section: str, key: str, fallback: str = "") -> str:
        """ConfigParser-style ``get`` (alias for ``get_str``)."""
        return self.get_str(section, key, fallback)

    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """ConfigParser-style ``getboolean`` (alias for ``get_bool``)."""
        return self.get_bool(section, key, fallback)

    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        """ConfigParser-style ``getint`` (alias for ``get_int``)."""
        return self.get_int(section, key, fallback)

    def has_section(self, section: str) -> bool:
        """ConfigParser-style ``has_section``."""
        return section in self

    def setdefault_section(self, section: str) -> Dict[str, Any]:
        """Return (creating if needed) the mutable mapping for a section."""
        return self[section]

    def __contains__(self, section: object) -> bool:
        return isinstance(self._store.get(str(section)), dict)

    def __getitem__(self, section: str) -> _SectionView:
        return _SectionView(self, section)

    def __setitem__(self, section: str, options: Dict[str, Any]) -> None:
        for key, value in options.items():
            self.set_value(section, key, value, save=False)

    def __iter__(self) -> Iterator[str]:
        return iter(self.config)

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------
    def set_value(self, section: str, key: str, value: Any, *, save: bool = True) -> None:
        """Set one value, rejecting anything the schema will not accept.

        Unlike the old ConfigParser-style ``set``, this refuses a value that is
        the wrong type or outside its constraints rather than storing it and
        discovering the problem later.
        """
        try:
            self._store.set(f"{section}.{key}", value)
        except ConfigError as exc:
            raise ConfigValidationError(str(exc)) from exc
        if save:
            self._store.save()

    def set(self, section: str, key: str, value: Any, *, save: bool = True) -> None:
        """Alias for :meth:`set_value`, saving immediately by default."""
        self.set_value(section, key, value, save=save)

    @property
    def config(self) -> Dict[str, Dict[str, Any]]:
        """A snapshot of the whole configuration."""
        return self._store.as_dict()

    def get_all(self) -> Dict[str, Any]:
        return self._store.as_dict()

    def get_download_dir(self) -> Path:
        return Path(self.get_str("storage", "download_dir", "~/Pictures/Muralis")).expanduser()

    def get_log_file(self) -> Path:
        return Path(
            self.get_str("logging", "log_file", "~/.local/share/muralis/muralis.log")
        ).expanduser()

    def get_proxy_settings(self) -> Optional[Dict]:
        if not self.get_bool("networking", "proxy_enabled", False):
            return None
        proxy_url = self.get_str("networking", "proxy_url", "")
        if not proxy_url:
            return None
        username = self.get_str("networking", "proxy_username", "")
        password = self.get_str("networking", "proxy_password", "")
        if username and password:
            from urllib.parse import urlparse

            parsed = urlparse(proxy_url)
            proxy_url = f"{parsed.scheme}://{username}:{password}@{parsed.netloc}{parsed.path}"
        return {"http": proxy_url, "https": proxy_url}

    def get_update_time(self) -> str:
        return self.get_str("scheduling", "update_time", "09:00")

    def get_api_key(self, provider: str) -> Optional[str]:
        return self.get_optional("api_keys", f"{provider}_key")

    def set_api_key(self, provider: str, key: str):
        self.set_value("api_keys", f"{provider}_key", key)

    # ------------------------------------------------------------------
    # Display / import / export
    # ------------------------------------------------------------------
    def display(self):
        print("\n" + "=" * 60)
        print(t("cli.config.title"))
        print("=" * 60)
        print(t("cli.config.file", path=self.config_path))
        print("=" * 60)
        for section, options in self._store.as_dict().items():
            print(f"\n[{section}]")
            for key, value in options.items():
                if not isinstance(value, dict):
                    continue
                rendered = str(value)
                if "key" in key or "password" in key or "secret" in key:
                    if len(rendered) > 8:
                        rendered = rendered[:4] + "..." + rendered[-4:]
                    elif rendered:
                        rendered = "***"
                if isinstance(value, bool):
                    rendered = "✓" if value else "✗"
                print(f"  {key:25} = {rendered}")
        print("\n" + "=" * 60)

    def export_json(self, filepath: str):
        export_path = Path(filepath).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as handle:
            json.dump(self._store.as_dict(), handle, indent=2, ensure_ascii=False)
        print(t("cli.ok.exported", path=export_path))

    def import_json(self, filepath: str):
        import_path = Path(filepath).expanduser()
        try:
            with open(import_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigValidationError(str(exc)) from exc
        if not isinstance(data, dict):
            raise ConfigValidationError(f"{import_path}: expected a table of sections")
        for section, options in data.items():
            if not isinstance(options, dict):
                continue
            for key, value in options.items():
                try:
                    self.set_value(str(section), str(key), value, save=False)
                except ConfigValidationError:
                    pass
        self._store.save()
        print(t("cli.ok.imported", path=import_path))

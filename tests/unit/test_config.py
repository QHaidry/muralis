#!/usr/bin/env python3
"""Tests for configuration management."""

import json
import tempfile
from pathlib import Path

import pytest

from muralis.config import ConfigManager, ConfigValidationError


class TestConfigManager:
    """Test ConfigManager class."""

    def setup_method(self):
        """Setup test fixtures."""
        ConfigManager.clear_cache()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.config = ConfigManager(str(self.config_path))

    def test_create_default_config(self):
        """Test default config creation."""
        assert self.config_path.exists()

        # Test default values
        provider = self.config.get_str("general", "provider", "")
        assert provider == "bing"

        resolution = self.config.get_str("image", "resolution", "")
        assert resolution == "3840x2160"

    def test_defaults_are_stored_with_real_types(self):
        """The file holds booleans and integers, not their string forms.

        This is the point of the typed schema: a stringly-typed file cannot
        survive being re-serialised as TOML, where "true" is not True.
        """
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        assert payload["general"]["auto_update"] is True
        assert payload["general"]["update_interval"] == 86400
        assert payload["image"]["apply_effects"] is False

    def test_get_str(self):
        """Test getting string values."""
        value = self.config.get_str("general", "non_existent", "default")
        assert value == "default"

    def test_get_bool(self):
        """Test getting boolean values."""
        self.config.set("general", "test_true", "true")
        self.config.set("general", "test_false", "false")

        assert self.config.get_bool("general", "test_true") is True
        assert self.config.get_bool("general", "test_false") is False

    def test_set_and_get(self):
        """Test setting and getting values."""
        self.config.set("test", "key", "value")
        value = self.config.get_str("test", "key", "")
        assert value == "value"

    def test_set_rejects_a_malformed_value(self):
        """A value that does not match its option's format never lands."""
        with pytest.raises(ConfigValidationError):
            self.config.set("image", "resolution", "invalid")
        # The previous value is untouched.
        assert self.config.get_str("image", "resolution") == "3840x2160"

    def test_set_rejects_an_unknown_choice(self):
        with pytest.raises(ConfigValidationError):
            self.config.set("general", "provider", "nonsense")

    def test_set_rejects_an_out_of_range_number(self):
        with pytest.raises(ConfigValidationError):
            self.config.set("image", "jpeg_quality", 500)

    def test_set_coerces_before_storing(self):
        self.config.set("image", "jpeg_quality", "75")
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        assert payload["image"]["jpeg_quality"] == 75

    def test_validate_reports_unknown_keys(self):
        self.config.set("image", "mystery", "1")  # unknown keys are preserved
        problems = self.config.validate()
        assert any("image.mystery" in problem for problem in problems)

    def test_validate_is_quiet_for_a_valid_config(self):
        assert self.config.validate() == []

    def test_section_view_writes_through_to_the_store(self):
        """`config["image"]["jpeg_quality"] = 75` must persist, typed."""
        view = self.config["image"]
        view["jpeg_quality"] = 75
        self.config.save()

        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        assert payload["image"]["jpeg_quality"] == 75
        assert self.config.get_int("image", "jpeg_quality") == 75

    def test_export_import_json(self):
        """Test exporting and importing JSON."""
        export_path = Path(self.temp_dir.name) / "export.json"
        self.config.export_json(str(export_path))
        assert export_path.exists()

        # Create new config and import
        ConfigManager.clear_cache()
        new_config = ConfigManager(str(Path(self.temp_dir.name) / "new_config.json"))
        new_config.import_json(str(export_path))
        assert new_config.get_str("general", "provider") == "bing"

    def test_get_download_dir(self):
        """Test getting download directory."""
        download_dir = self.config.get_download_dir()
        assert isinstance(download_dir, Path)
        # Default is ~/Pictures/Muralis
        assert "Muralis" in str(download_dir)

    def test_get_proxy_settings(self):
        """Test proxy settings."""
        self.config.set("networking", "proxy_enabled", "true")
        self.config.set("networking", "proxy_url", "http://example.com:8080")

        proxy = self.config.get_proxy_settings()
        assert proxy is not None
        assert "http" in proxy

    def test_migration(self):
        """A legacy config.ini is imported once, then removed."""
        legacy = Path(self.temp_dir.name) / "legacy.ini"
        legacy.write_text(
            "[general]\nprovider = nasa\n[image]\nresolution = 1920x1080\n",
            encoding="utf-8",
        )

        ConfigManager.clear_cache()
        migrated = ConfigManager(str(Path(self.temp_dir.name) / "legacy.json"))

        assert migrated.get_str("general", "provider") == "nasa"
        assert migrated.get_str("image", "resolution") == "1920x1080"
        # Defaults are filled in for everything the INI did not mention.
        assert migrated.get_str("image", "effect_type") == "none"
        # The legacy file is gone, and the new one exists.
        assert not legacy.exists()
        assert Path(self.temp_dir.name, "legacy.json").exists()

    def test_migration_does_not_overwrite_an_existing_config(self):
        self.config.set("general", "provider", "nasa")
        legacy = Path(self.temp_dir.name) / "config.ini"
        legacy.write_text("[general]\nprovider = pexels\n", encoding="utf-8")

        ConfigManager.clear_cache()
        reopened = ConfigManager(str(self.config_path))
        assert reopened.get_str("general", "provider") == "nasa"

    def teardown_method(self):
        """Clean test fixtures."""
        ConfigManager.clear_cache()
        self.temp_dir.cleanup()

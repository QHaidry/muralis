#!/usr/bin/env python3
"""Tests for the Muralis command-line interface."""

from unittest.mock import patch, MagicMock

from muralis.__main__ import main


def _run(argv, return_values=None):
    """Run main() with the given argv and a mocked MuralisApp.

    ``return_values`` maps attribute names to the values their mocked method
    should return when main() calls them.
    """
    return_values = return_values or {}
    with patch("sys.argv", ["muralis"] + argv):
        with patch("muralis.__main__.MuralisApp") as app_cls:
            app = MagicMock()
            for name, value in return_values.items():
                getattr(app, name).return_value = value
            app_cls.return_value = app
            rc = main()
    return rc, app


class TestCliActions:
    """Exercise the action dispatch in the CLI entry point."""

    def test_set_image_success(self):
        """--set-image calls app.set_local_image and exits 0 on success."""
        rc, app = _run(["--set-image", "/path/wall.jpg"], {"set_local_image": True})
        app.set_local_image.assert_called_once_with("/path/wall.jpg")
        assert rc == 0

    def test_set_image_failure(self):
        """--set-image exits non-zero when the call fails."""
        rc, app = _run(["--set-image", "/path/wall.jpg"], {"set_local_image": False})
        assert rc == 1

    def test_get_image_success(self):
        """--get-image calls app.fetch_image_only and exits 0 on success."""
        rc, app = _run(["--get-image"], {"fetch_image_only": "/path/out.jpg"})
        app.fetch_image_only.assert_called_once_with(None)
        assert rc == 0

    def test_get_image_failure(self):
        """--get-image exits non-zero when fetch returns None."""
        rc, app = _run(["--get-image"], {"fetch_image_only": None})
        assert rc == 1

    def test_set_image_is_actionable(self):
        """--set-image/--get-image should not fall through to show_help."""
        with patch("sys.argv", ["muralis", "--get-image"]):
            with patch("muralis.__main__.MuralisApp") as app_cls:
                app = MagicMock()
                app.fetch_image_only.return_value = "/out.jpg"
                app_cls.return_value = app
                with patch("muralis.__main__.show_help") as help_mock:
                    rc = main()
        assert rc == 0
        help_mock.assert_not_called()


class TestCliConfiguration:
    """The config subcommands, driven against a real ConfigManager."""

    @staticmethod
    def _app_with(tmp_path, monkeypatch):
        from muralis.config import ConfigManager

        ConfigManager.clear_cache()
        config = ConfigManager(str(tmp_path / "config.json"))

        class FakeApp:
            pass

        app = FakeApp()
        app.config = config
        monkeypatch.setattr("muralis.__main__.MuralisApp", lambda *a, **k: app)
        return config

    def test_get_prints_a_zero(self, tmp_path, monkeypatch, capsys):
        """Zero is a value, not an absence — `if value:` said otherwise."""
        self._app_with(tmp_path, monkeypatch).set("storage", "max_files", 0)

        with patch("sys.argv", ["muralis", "--get", "storage.max_files"]):
            assert main() == 0

        assert capsys.readouterr().out.strip().splitlines()[-1] == "0"

    def test_get_reports_a_missing_key(self, tmp_path, monkeypatch, capsys):
        self._app_with(tmp_path, monkeypatch)

        with patch("sys.argv", ["muralis", "--get", "general.nope"]):
            assert main() == 0

        assert "not found" in capsys.readouterr().err

    def test_set_rejects_a_malformed_section_key(self, tmp_path, monkeypatch, capsys):
        self._app_with(tmp_path, monkeypatch)

        with patch("sys.argv", ["muralis", "--get", "no-dot"]):
            assert main() == 0

        assert "SECTION.KEY" in capsys.readouterr().err

    def test_set_writes_through_the_schema(self, tmp_path, monkeypatch, capsys):
        config = self._app_with(tmp_path, monkeypatch)

        with patch("sys.argv", ["muralis", "--set", "general.provider", "nasa"]):
            assert main() == 0

        assert config.get_str("general", "provider") == "nasa"
        assert "nasa" in capsys.readouterr().out

    def test_a_provider_flag_reaches_run_once(self):
        rc, app = _run(["--once", "--provider", "nasa"], {"run_once": True})
        app.run_once.assert_called_once_with("nasa")
        assert rc == 0

    def test_export_config_calls_the_config(self):
        rc, app = _run(["--export-config", "/tmp/x.json"])
        app.config.export_json.assert_called_once_with("/tmp/x.json")
        assert rc == 0

    def test_convert_config_error_is_reported(self, capsys):
        from muralis.config import ConfigValidationError

        rc, app = _run(["--convert-config", "json"])
        app.config.convert.side_effect = ConfigValidationError("nope")
        with patch("sys.argv", ["muralis", "--convert-config", "json"]):
            with patch("muralis.__main__.MuralisApp", return_value=app):
                rc = main()

        assert rc == 0
        assert "error: nope" in capsys.readouterr().err


def test_list_providers_names_every_provider(capsys):
    from muralis.__main__ import list_providers
    from muralis.providers import ALL_PROVIDERS

    assert list_providers() == 0

    out = capsys.readouterr().out
    for name in ALL_PROVIDERS:
        assert name in out


def test_show_help_prints_the_banner(capsys):
    from muralis.__main__ import show_help

    show_help()

    out = capsys.readouterr().out
    assert "Muralis v" in out
    assert "QUICK START" in out

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

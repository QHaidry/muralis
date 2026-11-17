#!/usr/bin/env python3
"""Tests for the download helper.

The streaming/retry path used to be entirely uncovered (18%), which is why a
User-Agent regression — the downloader overwriting the one the configured
session had just been given — went unnoticed.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from muralis.context import USER_AGENT
from muralis.utils.downloader import DEFAULT_USER_AGENT, download_image


def _response(body: bytes = b"payload", content_type: str = "image/jpeg", error=None):
    response = MagicMock()
    response.headers = {"content-type": content_type}
    if error is not None:
        response.raise_for_status.side_effect = error
    response.iter_content.return_value = [body]
    return response


@pytest.fixture
def session():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    return session


def test_downloads_the_body_to_disk(tmp_path, session):
    session.get.return_value = _response(b"abc")
    target = tmp_path / "out" / "image.jpg"

    assert download_image("https://example.com/a.jpg", str(target), session=session) is True
    assert target.read_bytes() == b"abc"


def test_it_creates_the_parent_directory(tmp_path, session):
    session.get.return_value = _response()
    target = tmp_path / "nested" / "deeper" / "image.jpg"

    assert download_image("https://example.com/a.jpg", str(target), session=session) is True
    assert target.exists()


def test_a_meaningless_session_user_agent_is_replaced(tmp_path, session):
    session.get.return_value = _response()

    download_image("https://example.com/a.jpg", str(tmp_path / "i.jpg"), session=session)

    sent = session.get.call_args.kwargs["headers"]
    assert sent["User-Agent"] == DEFAULT_USER_AGENT


def test_a_configured_user_agent_is_preserved(tmp_path, session):
    """`networking.user_agent` must survive the download path.

    The downloader used to overwrite it unconditionally, so the setting worked
    for provider API calls and silently did not for the images themselves.
    """
    session.headers = {"User-Agent": "Custom/9.9"}
    session.get.return_value = _response()

    download_image("https://example.com/a.jpg", str(tmp_path / "i.jpg"), session=session)

    sent = session.get.call_args.kwargs["headers"]
    assert "User-Agent" not in sent or sent["User-Agent"] == "Custom/9.9"
    assert session.headers["User-Agent"] == "Custom/9.9"


def test_explicit_headers_win(tmp_path, session):
    session.headers = {"User-Agent": "Custom/9.9"}
    session.get.return_value = _response()

    download_image(
        "https://example.com/a.jpg",
        str(tmp_path / "i.jpg"),
        session=session,
        headers={"User-Agent": "Override/1.0"},
    )

    assert session.get.call_args.kwargs["headers"]["User-Agent"] == "Override/1.0"


def test_the_agent_carries_the_version_and_the_project_url():
    assert USER_AGENT == DEFAULT_USER_AGENT
    assert USER_AGENT.startswith("Muralis/")
    assert "github.com/QHaidry/muralis" in USER_AGENT


def test_a_transport_error_is_retried_then_reported(tmp_path, session):
    session.get.side_effect = requests.ConnectionError("boom")

    with patch("time.sleep") as sleep:
        ok = download_image("https://example.com/a.jpg", str(tmp_path / "i.jpg"), session=session)

    assert ok is False
    assert session.get.call_count == 3  # the default retries
    assert sleep.call_count == 2  # backoff between attempts, not after the last


def test_retries_can_be_tuned(tmp_path, session):
    session.get.side_effect = requests.ConnectionError("boom")

    with patch("time.sleep"):
        download_image(
            "https://example.com/a.jpg", str(tmp_path / "i.jpg"), session=session, retries=1
        )

    assert session.get.call_count == 1


def test_a_second_attempt_can_succeed(tmp_path, session):
    session.get.side_effect = [requests.ConnectionError("boom"), _response(b"ok")]

    with patch("time.sleep"):
        ok = download_image("https://example.com/a.jpg", str(tmp_path / "i.jpg"), session=session)

    assert ok is True
    assert (tmp_path / "i.jpg").read_bytes() == b"ok"


def test_an_empty_body_is_not_a_success(tmp_path, session):
    session.get.return_value = _response(b"")

    assert (
        download_image("https://example.com/a.jpg", str(tmp_path / "i.jpg"), session=session)
        is False
    )


def test_a_non_image_content_type_is_downloaded_but_warned_about(tmp_path, session, capsys):
    session.get.return_value = _response(b"<html>", content_type="text/html")

    assert (
        download_image("https://example.com/a.jpg", str(tmp_path / "i.jpg"), session=session)
        is True
    )
    assert "may not be an image" in capsys.readouterr().out


def test_an_unexpected_error_is_not_retried(tmp_path, session):
    session.get.side_effect = RuntimeError("nope")

    assert (
        download_image("https://example.com/a.jpg", str(tmp_path / "i.jpg"), session=session)
        is False
    )
    assert session.get.call_count == 1

#!/usr/bin/env python3
"""Tests for wallpaper providers.

Every provider is exercised against a mocked HTTP layer, including the paths
that used to fail silently in production: a missing API key, a rejected key, a
non-image APOD, and an API whose parameters do not mean what they look like.
"""

from unittest.mock import MagicMock, patch

import pytest

from muralis.config import ConfigManager
from muralis.providers import ALL_PROVIDERS, get_provider
from muralis.providers.artinstitute import ArtInstituteProvider
from muralis.providers.bing import BingProvider
from muralis.providers.nasa import NasaProvider
from muralis.providers.pexels import PexelsProvider
from muralis.providers.unsplash import UnsplashProvider
from muralis.providers.wallhaven import WallhavenProvider
from muralis.providers.wikimedia import WikimediaProvider


@pytest.fixture
def config(tmp_path):
    """A real ConfigManager in a temporary profile."""
    ConfigManager.clear_cache()
    yield ConfigManager(str(tmp_path / "config.json"))
    ConfigManager.clear_cache()


@pytest.fixture
def http():
    """Patch the session every provider funnels its requests through."""
    with patch("requests.Session.get") as get:
        get.return_value.status_code = 200
        get.return_value.headers = {"content-type": "image/jpeg"}
        yield get


def _json(http, payload):
    http.return_value.json.return_value = payload


# ----------------------------------------------------------------------
# Bing
# ----------------------------------------------------------------------


class TestBing:
    def test_daily_url_is_absolute(self, http):
        _json(http, {"images": [{"url": "/th?id=OHR.X_1920x1080.jpg"}]})
        url = BingProvider().get_daily_url()
        assert url == "https://www.bing.com/th?id=OHR.X_1920x1080.jpg"

    def test_uhd_resolution_becomes_bings_uhd_parameter(self, http):
        """3840x2160 is not a URL Bing serves; `UHD` is."""
        _json(http, {"images": [{"url": "/th?id=OHR.X_1920x1080.jpg"}]})
        url = BingProvider().get_daily_url("3840x2160")
        assert url is not None
        assert "UHD" in url
        assert "1920x1080" not in url

    def test_metadata_falls_back_when_the_response_is_empty(self, http):
        _json(http, {"images": []})
        assert "title" in BingProvider().get_metadata()

    def test_a_transport_error_yields_none(self, http):
        http.side_effect = OSError("network down")
        assert BingProvider().get_daily_url() is None


# ----------------------------------------------------------------------
# NASA
# ----------------------------------------------------------------------


class TestNasa:
    def test_prefers_hdurl(self, http):
        _json(
            http,
            {"media_type": "image", "hdurl": "https://nasa/hd.jpg", "url": "https://nasa/x.jpg"},
        )
        assert NasaProvider().get_daily_url() == "https://nasa/hd.jpg"

    def test_falls_back_to_url(self, http):
        _json(http, {"media_type": "image", "url": "https://nasa/x.jpg"})
        assert NasaProvider().get_daily_url() == "https://nasa/x.jpg"

    def test_a_video_is_not_a_wallpaper(self, http):
        _json(http, {"media_type": "video", "url": "https://youtube/watch?v=1"})
        assert NasaProvider().get_daily_url() is None

    @pytest.mark.parametrize(
        "url",
        [
            "https://science.nasa.gov/wp-content/themes/nasa-child/assets/images/nasa-logo@2x.png",
            "https://www.nasa.gov/logo.png",
        ],
    )
    def test_site_furniture_is_rejected(self, http, url):
        """APOD's `url` can be the NASA logo; setting it as wallpaper is a bug."""
        _json(http, {"media_type": "image", "url": url})
        assert NasaProvider().get_daily_url() is None


# ----------------------------------------------------------------------
# Pexels
# ----------------------------------------------------------------------


class TestPexels:
    def test_with_a_configured_key_it_returns_a_photo(self, http, config):
        config.set("api_keys", "pexels_key", "k" * 32)
        _json(http, {"photos": [{"src": {"original": "https://pexels/1.jpg"}}]})

        assert PexelsProvider(config).get_daily_url() == "https://pexels/1.jpg"

    def test_without_a_key_it_makes_no_request(self, http, config):
        """There is no public demo key, so an unconfigured Pexels must not call."""
        assert PexelsProvider(config).get_daily_url() is None
        http.assert_not_called()

    def test_the_configured_key_is_sent(self, http, config):
        config.set("api_keys", "pexels_key", "secret-key-value")
        _json(http, {"photos": []})

        PexelsProvider(config).get_daily_url()

        headers = http.call_args.kwargs["headers"]
        assert headers["Authorization"] == "secret-key-value"


# ----------------------------------------------------------------------
# Wikimedia
# ----------------------------------------------------------------------


class TestWikimedia:
    PAGE = {
        "query": {
            "pages": {
                "1": {
                    "pageid": 1,
                    "title": "File:Painting.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/commons/a/ab/Painting-name.jpg",
                            "thumburl": "https://upload.wikimedia.org/thumb/500px-Painting.jpg",
                        }
                    ],
                }
            }
        }
    }

    def test_requests_a_generator_without_a_conflicting_list(self, http):
        """`list=random` and `generator=...` share a slot; combining them
        returned pages with no imageinfo, so this provider never worked."""
        _json(http, self.PAGE)
        WikimediaProvider().get_daily_url("1920x1080")

        params = http.call_args.kwargs["params"]
        assert params["generator"] == "random"
        assert "list" not in params

    def test_prefers_the_requested_thumbnail_size(self, http):
        _json(http, self.PAGE)
        url = WikimediaProvider().get_daily_url("1920x1080")
        assert url is not None
        assert "/thumb/" in url

    def test_the_url_is_returned_verbatim(self, http):
        """The old path mangling stripped every hyphen and produced dead URLs."""
        _json(http, self.PAGE)
        url = WikimediaProvider().get_daily_url()
        assert url is not None
        assert "Painting-name" in url or "Painting" in url

    def test_pages_without_imageinfo_are_skipped(self, http):
        _json(http, {"query": {"pages": {"1": {"pageid": 1, "title": "Commons:Help"}}}})
        assert WikimediaProvider().get_daily_url() is None

    def test_thumbnail_width_is_capped(self):
        assert WikimediaProvider._thumb_width("7680x4320") == 4000
        assert WikimediaProvider._thumb_width("1920x1080") == 1920
        assert WikimediaProvider._thumb_width("nonsense") == 1920


# ----------------------------------------------------------------------
# Art Institute / Wallhaven
# ----------------------------------------------------------------------


class TestArtInstitute:
    def test_builds_a_iiif_url(self, http):
        _json(http, {"data": [{"image_id": "abc-123", "title": "Test"}]})
        url = ArtInstituteProvider().get_daily_url()
        assert url is not None
        assert "abc-123" in url

    def test_artwork_without_an_image_is_skipped(self, http):
        _json(http, {"data": [{"image_id": None}]})
        assert ArtInstituteProvider().get_daily_url() is None


class TestWallhaven:
    def test_returns_the_path_field(self, http):
        _json(http, {"data": [{"path": "https://w.wallhaven.cc/full/x.jpg"}]})
        assert WallhavenProvider().get_daily_url() == "https://w.wallhaven.cc/full/x.jpg"

    def test_an_empty_result_is_none(self, http):
        _json(http, {"data": []})
        assert WallhavenProvider().get_daily_url() is None


# ----------------------------------------------------------------------
# Unsplash
# ----------------------------------------------------------------------


class TestUnsplash:
    KEY = "a" * 32

    def test_requires_a_key(self, http):
        assert UnsplashProvider().get_daily_url() is None
        http.assert_not_called()

    def test_a_malformed_key_is_refused_before_the_request(self, http, config):
        config.set("api_keys", "unsplash_key", "short")
        assert UnsplashProvider(config).get_daily_url() is None
        http.assert_not_called()

    def test_a_valid_key_produces_a_sized_url(self, http, config):
        config.set("api_keys", "unsplash_key", self.KEY)
        _json(http, {"urls": {"raw": "https://images.unsplash.com/photo-1"}})

        url = UnsplashProvider(config).get_daily_url("1920x1080")

        assert url is not None
        assert "w=1920" in url and "h=1080" in url

    def test_a_401_is_reported_not_raised(self, http, config):
        import requests

        config.set("api_keys", "unsplash_key", self.KEY)
        response = MagicMock(status_code=401)
        http.side_effect = requests.exceptions.HTTPError(response=response)

        assert UnsplashProvider(config).get_daily_url() is None


# ----------------------------------------------------------------------
# The registry
# ----------------------------------------------------------------------


def test_every_registered_provider_is_constructible():
    for name in ALL_PROVIDERS:
        provider = get_provider(name)
        assert provider.name == name


def test_an_unknown_provider_names_the_alternatives():
    with pytest.raises(ValueError) as excinfo:
        get_provider("nope")
    assert "bing" in str(excinfo.value)

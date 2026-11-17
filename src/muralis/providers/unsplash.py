"""Unsplash wallpaper provider with API key support."""

import logging
from typing import Dict, Optional

import requests

from .base import WallpaperProvider

logger = logging.getLogger(__name__)


class UnsplashProvider(WallpaperProvider):
    """Fetches random curated photos from Unsplash."""

    API_URL = "https://api.unsplash.com/photos/random"

    @property
    def name(self) -> str:
        return "unsplash"

    def _get_api_key(self) -> Optional[str]:
        """Get Unsplash API key from config."""
        if self.config:
            key = self.config.get_api_key("unsplash")
            if key and key.strip():
                return key.strip()
        return None

    def _check_api_key(self) -> bool:
        """Check if API key is configured."""
        key = self._get_api_key()
        if not key:
            logger.warning(
                "Unsplash needs a free API key: register at "
                "https://unsplash.com/developers and add it with "
                "`muralis --set-key unsplash YOUR_KEY`."
            )
            return False

        # Basic format validation
        if len(key) != 32 or not all(c.isalnum() or c in "-_" for c in key):
            logger.warning(
                "Unsplash keys are 32 characters, letters/digits/-/_; update yours "
                "with `muralis --set-key unsplash YOUR_KEY`."
            )
            return False

        return True

    def get_daily_url(self, resolution: str = "1920x1080") -> Optional[str]:
        """Get random Unsplash photo URL."""
        if not self._check_api_key():
            return None

        try:
            api_key = self._get_api_key()
            headers = {"Authorization": f"Client-ID {api_key}"}

            # Parse resolution for width/height
            if "x" in resolution:
                width, height = resolution.split("x")
            else:
                width, height = "1920", "1080"

            params = {
                "orientation": "landscape",
                "content_filter": "high",
                "w": width,
                "h": height,
                "fit": "crop",
            }

            response = self._get(self.API_URL, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Get the raw image URL (highest quality)
            urls = data.get("urls", {})
            raw = urls.get("raw")

            # Unsplash's `raw` URL takes size parameters, but the URL does not
            # contain the word "raw" — the old `"raw" in image_url` test never
            # matched, so the requested resolution was silently ignored.
            if isinstance(raw, str) and raw:
                separator = "&" if "?" in raw else "?"
                return f"{raw}{separator}w={width}&h={height}&fit=crop"

            for size in ("full", "regular"):
                candidate = urls.get(size)
                if isinstance(candidate, str) and candidate:
                    return candidate
            return None

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                logger.error(
                    "Unsplash rejected the API key (401). Check it with "
                    "`muralis --check-keys` and replace it with "
                    "`muralis --set-key unsplash YOUR_KEY`."
                )
            else:
                logger.error(f"Error fetching Unsplash photo: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Unsplash photo: {e}")
            return None

    def get_metadata(self) -> Dict:
        """Get Unsplash photo metadata."""
        if not self._check_api_key():
            return {"title": "Unsplash Photo", "copyright": "Unsplash (API key required)"}

        try:
            api_key = self._get_api_key()
            headers = {"Authorization": f"Client-ID {api_key}"}

            response = self._get(self.API_URL, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            photographer = data.get("user", {}).get("name", "Unknown Photographer")
            photographer_username = data.get("user", {}).get("username", "")

            return {
                "title": data.get("alt_description", "Unsplash Photo"),
                "copyright": f"📷 {photographer} / Unsplash",
                "photographer": photographer,
                "username": photographer_username,
                "likes": data.get("likes", 0),
                "downloads": data.get("downloads", 0),
                "provider": "Unsplash",
                "profile_url": (
                    f"https://unsplash.com/@{photographer_username}"
                    if photographer_username
                    else ""
                ),
            }
        except Exception as e:
            logger.error(f"Error fetching Unsplash metadata: {e}")
            return {"title": "Unsplash Photo", "copyright": "Unsplash"}

    def get_available_resolutions(self) -> list:
        """Unsplash supports various resolutions."""
        return ["1920x1080", "2560x1440", "3840x2160", "4096x2160", "5120x2880"]

    def supports_resolution(self, resolution: str) -> bool:
        """Unsplash supports high resolutions."""
        return True

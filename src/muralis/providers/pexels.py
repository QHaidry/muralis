"""Pexels wallpaper provider - Free stock photos."""

import logging
from typing import Dict, Optional

from .base import WallpaperProvider

logger = logging.getLogger(__name__)


class PexelsProvider(WallpaperProvider):
    """Fetches curated photos from Pexels."""

    # Pexels does not publish a demo key, so there is nothing sensible to ship
    # as a default: an unconfigured Pexels is reported as such rather than
    # spending a request on a key the API will reject with 401.
    API_URL = "https://api.pexels.com/v1/curated"

    @property
    def name(self) -> str:
        return "pexels"

    def _get_api_key(self) -> Optional[str]:
        """Return the configured key, or None when the user has not set one."""
        if self.config:
            key = self.config.get_api_key("pexels")
            if key and key.strip():
                return key.strip()
        return None

    def get_daily_url(self, resolution: str = "1920x1080") -> Optional[str]:
        """Get random curated photo from Pexels."""
        api_key = self._get_api_key()
        if not api_key:
            logger.warning(
                "Pexels needs a free API key: register at https://www.pexels.com/api "
                "and add it with `muralis --set-key pexels YOUR_KEY`."
            )
            return None

        try:
            headers = {"Authorization": api_key}
            params = {"per_page": 30}

            response = self._get(self.API_URL, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("photos") and len(data["photos"]) > 0:
                # Select random photo from curated list
                import random

                photo = random.choice(data["photos"])

                # Get largest available size
                src = photo.get("src", {})
                for size in ["original", "large2x", "large", "medium"]:
                    url = src.get(size)
                    if isinstance(url, str) and url:
                        return url
                return None
            return None

        except Exception as e:
            logger.error(f"Error fetching Pexels photo: {e}")
            return None

    def get_metadata(self) -> Dict:
        """Get Pexels photo metadata."""
        api_key = self._get_api_key()
        if not api_key:
            return {"title": "Pexels Photo", "copyright": "Pexels (API key required)"}

        try:
            headers = {"Authorization": api_key}
            response = self._get(self.API_URL, headers=headers, params={"per_page": 1})
            response.raise_for_status()
            data = response.json()

            if data.get("photos") and len(data["photos"]) > 0:
                photo = data["photos"][0]
                return {
                    "title": photo.get("alt", "Pexels Photo"),
                    "copyright": f"📷 {photo.get('photographer', 'Photographer')} / Pexels",
                    "photographer_url": photo.get("photographer_url", ""),
                    "provider": "Pexels",
                }
        except Exception as e:
            logger.error(f"Error fetching Pexels metadata: {e}")
        return {"title": "Pexels Photo", "copyright": "Pexels"}

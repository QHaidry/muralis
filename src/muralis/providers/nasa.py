"""NASA Astronomy Picture of the Day provider."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .base import WallpaperProvider

logger = logging.getLogger(__name__)


class NasaProvider(WallpaperProvider):
    """Fetches NASA's Astronomy Picture of the Day."""

    API_URL = "https://api.nasa.gov/planetary/apod"
    API_KEY = "DEMO_KEY"  # Replace with your API key for production

    @property
    def name(self) -> str:
        return "nasa"

    @staticmethod
    def _usable(url: Any) -> Optional[str]:
        """An image URL worth setting as a wallpaper, or None.

        APOD's ``url`` field is not always the astronomy picture: when the
        entry is a video, or when the payload is incomplete, it falls back to a
        NASA site asset (the logo), which is a perfectly valid image and a
        useless wallpaper. Those are rejected rather than downloaded.
        """
        if not isinstance(url, str) or not url:
            return None
        lowered = url.lower()
        if "wp-content/themes" in lowered or "logo" in lowered:
            return None
        return url

    def get_daily_url(self, resolution: str = "1920x1080") -> Optional[str]:
        """Get NASA APOD image URL."""
        try:
            params: Dict[str, Any] = {"api_key": self.API_KEY, "hd": "true"}
            response = self._get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check if it's an image (not video)
            if data.get("media_type") != "image":
                logger.info(
                    "NASA APOD is not an image today (media_type=%s)", data.get("media_type")
                )
                return None

            return self._usable(data.get("hdurl")) or self._usable(data.get("url"))
        except Exception as e:
            logger.error(f"Error fetching NASA APOD: {e}")
            return None

    def get_metadata(self) -> Dict:
        """Get NASA APOD metadata."""
        try:
            params = {"api_key": self.API_KEY}
            response = self._get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return {
                "title": data.get("title", "Astronomy Picture of the Day"),
                "copyright": data.get("copyright", "NASA"),
                "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
                "explanation": data.get("explanation", ""),
                "provider": "NASA",
            }
        except Exception as e:
            logger.error(f"Error fetching NASA metadata: {e}")
        return {"title": "NASA APOD", "copyright": "NASA"}

    def supports_resolution(self, resolution: str) -> bool:
        """NASA images are usually very high resolution."""
        return True

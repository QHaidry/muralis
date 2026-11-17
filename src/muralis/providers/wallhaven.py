"""Wallhaven.cc wallpaper provider."""

import logging
from random import choice
from typing import Dict, Optional

from .base import WallpaperProvider

logger = logging.getLogger(__name__)


class WallhavenProvider(WallpaperProvider):
    """Fetches wallpapers from Wallhaven.cc."""

    API_URL = "https://wallhaven.cc/api/v1/search"

    @property
    def name(self) -> str:
        return "wallhaven"

    def get_daily_url(self, resolution: str = "1920x1080") -> Optional[str]:
        """Get random wallpaper from Wallhaven."""
        try:
            # Search parameters for popular wallpapers
            params = {
                "categories": "111",  # General, Anime, People
                "purity": "100",  # SFW only
                "sorting": "relevance",
                "order": "desc",
                "resolutions": resolution,
                "ratios": "16x9",
            }

            response = self._get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("data") and len(data["data"]) > 0:
                # Pick a random wallpaper from results
                wallpaper = choice(data["data"])
                url = wallpaper.get("path")
                return url if isinstance(url, str) else None
            return None
        except Exception as e:
            logger.error(f"Error fetching Wallhaven wallpaper: {e}")
            return None

    def get_metadata(self) -> Dict:
        """Get Wallhaven wallpaper metadata."""
        try:
            params = {"categories": "111", "purity": "100"}
            response = self._get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("data") and len(data["data"]) > 0:
                wallpaper = choice(data["data"])
                return {
                    "title": f"Wallhaven ID: {wallpaper.get('id', 'Unknown')}",
                    "copyright": f"© {wallpaper.get('uploader', {}).get('username', 'Artist')}",
                    "views": wallpaper.get("views", 0),
                    "favorites": wallpaper.get("favorites", 0),
                    "provider": "Wallhaven",
                }
        except Exception:
            pass
        return {"title": "Wallhaven Wallpaper", "copyright": "Wallhaven.cc"}

    def get_available_resolutions(self) -> list:
        """Common wallpaper resolutions."""
        return ["1920x1080", "2560x1440", "3840x2160", "1920x1200"]

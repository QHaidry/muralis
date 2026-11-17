"""Wikimedia Commons provider - Public domain artwork."""

import logging
import random
from typing import Any, Dict, Optional

from .base import WallpaperProvider

logger = logging.getLogger(__name__)

#: ``1920x1080`` -> a thumbnail width Wikimedia can serve.
_MAX_THUMB_WIDTH = 4000


class WikimediaProvider(WallpaperProvider):
    """Fetches public domain artwork from Wikimedia Commons."""

    API_URL = "https://commons.wikimedia.org/w/api.php"

    # Categories of interesting artwork
    CATEGORIES = [
        "Featured_pictures_on_Wikimedia_Commons",
        "Quality_images",
        "Valued_images",
        "Landscape_paintings",
        "Nature_photographs",
    ]

    @property
    def name(self) -> str:
        return "wikimedia"

    @staticmethod
    def _thumb_width(resolution: str) -> int:
        """The thumbnail width to ask for, capped at something Commons serves."""
        try:
            width = int(resolution.lower().split("x")[0])
        except (ValueError, AttributeError):
            return 1920
        return max(320, min(width, _MAX_THUMB_WIDTH))

    def get_daily_url(self, resolution: str = "1920x1080") -> Optional[str]:
        """Get a random file from a curated Commons category.

        ``generator=random`` and ``list=random`` cannot be combined — a
        ``list`` module and a ``generator`` share the same result slot, so the
        API silently returned non-file pages with no ``imageinfo`` at all and
        this method always produced ``None``. Using the generator alone yields
        file pages, each carrying its own image URLs.
        """
        try:
            params: Dict[str, Any] = {
                "action": "query",
                "format": "json",
                "generator": "random",
                "grnnamespace": 6,  # File namespace
                "grnlimit": 10,  # the API caps this at 10 for anonymous callers
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": self._thumb_width(resolution),
            }

            response = self._get(self.API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            pages = list(data.get("query", {}).get("pages", {}).values())
            with_images = [page for page in pages if page.get("imageinfo")]
            if not with_images:
                logger.warning("Wikimedia returned no files with image info")
                return None

            info = random.choice(with_images)["imageinfo"][0]
            # thumburl is the server-rendered size we asked for; url is the
            # original. Either is usable, and neither is rewritten: the old
            # `replace("px-", "").replace("-", "")` mangled every hyphen in the
            # path and produced URLs that 404'd.
            url = info.get("thumburl") or info.get("url")
            return url if isinstance(url, str) and url else None

        except Exception as e:
            logger.error(f"Error fetching Wikimedia image: {e}")
            return None

    def get_metadata(self) -> Dict:
        """Get artwork metadata."""
        try:
            params: Dict[str, Any] = {
                "action": "query",
                "format": "json",
                "list": "random",
                "rnnamespace": 6,
                "rnlimit": 1,
            }

            response = self._get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("query", {}).get("random"):
                item = data["query"]["random"][0]
                return {
                    "title": item.get("title", "Wikimedia Artwork"),
                    "copyright": "Public Domain / Wikimedia Commons",
                    "provider": "Wikimedia Commons",
                }
        except Exception as e:
            logger.error(f"Error fetching Wikimedia metadata: {e}")
        return {"title": "Wikimedia Artwork", "copyright": "Public Domain"}

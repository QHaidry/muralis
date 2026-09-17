"""Themes for Muralis, backed by Gesso.

Gesso owns the token contract, the base stylesheet and the manager — including
the ``QPalette``, which native popups read. Muralis owns its palettes
(``gui/themes/*.json``) and nothing else.

Muralis's three palettes already satisfied Gesso's token contract exactly, so
this replaced 250 lines of local manager and QSS template without changing a
single colour.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from gesso.ui.theme import ThemeManager as _ThemeManager

from muralis.context import user_themes_dir

__all__ = ["DEFAULT_THEME", "BUILTIN_THEMES_DIR", "ThemeManager"]

#: The palette Muralis starts on.
DEFAULT_THEME = "reasonix"

#: Muralis's own palettes.
BUILTIN_THEMES_DIR = Path(__file__).parent / "themes"


class ThemeManager(_ThemeManager):
    """Muralis's themes, on Gesso's manager.

    Gesso's built-in palettes are deliberately *not* layered underneath: they
    are a neutral starting point for an application that ships none, and mixing
    them in would offer a "light" theme that is not Muralis's.
    """

    def __init__(
        self,
        app: Any = None,
        themes_dir: Optional[Path] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(
            app,
            builtin_dirs=[BUILTIN_THEMES_DIR],
            # Resolved through the application context, so a test — or a
            # relocated profile — can point themes elsewhere without touching
            # the developer's real ~/.config.
            user_dir=themes_dir if themes_dir is not None else user_themes_dir(),
            default=DEFAULT_THEME,
            # Copy the palettes into the user's directory so they can be
            # edited, without ever overwriting an edit already made.
            seed=True,
            parent=parent,
        )

    # ------------------------------------------------------------------
    # The shape the rest of Muralis already calls
    # ------------------------------------------------------------------
    def list_themes(self) -> List[str]:
        """Available theme ids, sorted. (Gesso calls this ``names``.)"""
        return self.names()

    def load_colors(self, theme_id: str) -> Dict[str, str]:
        """A theme's resolved palette. (Gesso returns a whole ``Theme``.)"""
        return self.load(theme_id).colors

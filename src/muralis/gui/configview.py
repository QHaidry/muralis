"""Config-view helper for the GUI.

Historically the GUI read settings through a ConfigParser-style facade over the
JSON-backed configuration. ``ConfigManager`` now exposes that same surface
directly (``get``/``getboolean``/``getint``/``set``/``has_section``/``save``
and section subscripting), so this module is just a thin factory returning a
``ConfigManager`` for the app config path.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from muralis.config import ConfigManager


def config_view(config_path: Optional[str] = None) -> "ConfigManager":
    """Return a ``ConfigManager`` for the app config.

    Args:
        config_path: Path to the config file (default: whatever Muralis's
            application context resolves, ~/.config/muralis/config.json).
    """
    from muralis.config import ConfigManager
    from muralis.context import config_path as resolved_config_path

    if config_path is None:
        config_path = str(resolved_config_path())
    return ConfigManager(config_path)

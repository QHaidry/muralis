"""Muralis - Smart Wallpaper Manager for Linux."""

from muralis._version import __version__

__author__ = "Qamber Haidry"
__license__ = "MIT"
__copyright__ = "Copyright (c) 2026 Quoxiom"

from muralis.app import MuralisApp
from muralis.config import ConfigManager

__all__ = ["MuralisApp", "ConfigManager", "__version__"]

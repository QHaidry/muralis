"""Internationalisation for Muralis, backed by Gesso.

Gesso owns the machinery — catalog merging, language detection, and the
framework/application/user override layers. Muralis owns only its strings,
which live in ``src/muralis/i18n/<language>.json``.

The module-level :func:`t` is kept because that is what almost every call site
uses. It delegates to a single process-wide translator built for Muralis's
:func:`~muralis.context.context`, so the language is detected once and the
user's overrides are found beside their settings rather than at a path written
out here.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from gesso.i18n import DEFAULT_LANGUAGE as DEFAULT_LANG
from gesso.i18n import Translator, detect_language, normalize_lang

from muralis.context import LOCALES_DIR, context

__all__ = [
    "DEFAULT_LANG",
    "Translator",
    "detect_language",
    "normalize_lang",
    "get_translator",
    "set_language",
    "t",
]

_translator: Optional[Translator] = None
_lock = threading.Lock()


def get_translator() -> Translator:
    """The process-wide translator, built on first use.

    Gesso deliberately ships no such global. Muralis keeps one because a single
    application having a single active language is simply the truth — and
    unlike a framework global, this one belongs to the application.
    """
    global _translator
    with _lock:
        if _translator is None:
            _translator = Translator.for_app(context(), locale_dir=LOCALES_DIR)
        return _translator


def set_language(lang: str) -> None:
    """Force a language (mainly for tests)."""
    get_translator().set_language(lang)


def t(key_name: str, **kwargs: Any) -> str:
    """Translate a dotted key using the process-wide translator."""
    return get_translator().t(key_name, **kwargs)

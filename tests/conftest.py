"""Shared test configuration.

Qt runs headless. The ``offscreen`` platform plugin needs no display, so the
GUI tests behave identically on a developer's desktop and in CI — no xvfb, no
windows appearing while the suite runs.

The environment variable must be set before Qt is imported anywhere, which is
why it is the first thing this module does.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

"""Shared test configuration.

Qt runs headless. The ``offscreen`` platform plugin needs no display, so the
GUI tests behave identically on a developer's desktop and in CI — no xvfb, no
windows appearing while the suite runs.

The environment variable must be set before Qt is imported anywhere, which is
why it is the first thing this module does.
"""

import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402  (after the environment is prepared)


@pytest.fixture(autouse=True, scope="session")
def _destroy_qt_objects_while_the_application_is_alive():
    """Tear the Qt object graph down before Python finalises.

    PySide registers an exit hook that destroys the ``QCoreApplication`` and
    *then* every remaining ``QObject`` wrapper. A widget still alive at that
    point is destroyed after the application's backing store is gone, which
    crashes inside ``QWidget::destroy`` → ``invalidateBackingStore``. The
    process exits 139 (SIGSEGV) with every test already reported as passed,
    so CI showed "220 passed" immediately above a segmentation fault.

    Widgets normally die at the end of the test that created them, but a
    widget wired as ``signal.connect(lambda: self._handler())`` sits in a
    reference cycle — the signal holds the lambda, the lambda holds the
    widget, and the widget owns the item that owns the signal. Cycles are only
    broken by the cyclic collector, whose timing (and therefore whether the
    run crashes) is not deterministic.

    Collecting here, while the ``QApplication`` is still alive, makes the
    teardown deterministic. It requests nothing, so a run that never touches
    Qt pays nothing for it.
    """
    yield

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:  # the GUI extra is not installed
        return

    app = QApplication.instance()
    if app is None:  # no Qt test ran
        return

    # Break the cycles while the application still owns the platform state.
    gc.collect()

    # Anything still parented to nothing is a top-level window.
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.processEvents()

    # Deleting the windows released more cycles.
    gc.collect()
    app.processEvents()

#!/usr/bin/env python3
"""Tests for the scheduler.

This module decides whether a user's wallpaper updates itself at all, and it
was the least covered part of the package (17%). The unit files it writes are
the contract with systemd, so they are asserted on directly.
"""

from unittest.mock import patch

import pytest
from gesso.core.paths import AppPaths

from muralis import context
from muralis.config import ConfigManager
from muralis.scheduler import (
    CRON_TEMPLATE,
    SYSTEMD_SERVICE_TEMPLATE,
    SYSTEMD_TIMER_TEMPLATE,
    SchedulerManager,
)


@pytest.fixture
def profile(tmp_path):
    """An isolated profile, so no test writes to ~/.config/systemd."""
    context.use_paths(AppPaths.resolve("muralis", config_home=tmp_path / "config"))
    ConfigManager.clear_cache()
    yield tmp_path
    context.reset()
    ConfigManager.clear_cache()


@pytest.fixture
def config(profile):
    return ConfigManager(str(profile / "config.json"))


@pytest.fixture
def scheduler(config):
    return SchedulerManager(config)


# ----------------------------------------------------------------------
# The unit templates
# ----------------------------------------------------------------------


def test_the_service_is_pulled_in_by_a_user_target():
    """The system-wide target is never reached by `systemctl --user`, so a
    unit enabled against it did nothing at login."""
    directives = [
        line for line in SYSTEMD_SERVICE_TEMPLATE.splitlines() if not line.startswith("#")
    ]
    assert "WantedBy=default.target" in directives


def test_the_service_does_not_set_a_user():
    """`User=` has no meaning inside a user manager."""
    assert "User=" not in SYSTEMD_SERVICE_TEMPLATE


def test_the_units_point_at_the_current_repository():
    for template in (SYSTEMD_SERVICE_TEMPLATE, SYSTEMD_TIMER_TEMPLATE):
        assert "Documentation=https://github.com/QHaidry/muralis" in template


def test_the_timer_runs_once_a_day_at_the_configured_time():
    rendered = SYSTEMD_TIMER_TEMPLATE.format(time="07:30")
    assert "OnCalendar=*-*-* 07:30:00" in rendered
    assert "Persistent=true" in rendered


def test_the_cron_line_carries_the_time_and_the_script():
    line = CRON_TEMPLATE.format(minute=5, hour=6, script_path="/usr/bin/muralis")
    schedule = [ln for ln in line.splitlines() if not ln.startswith("#")][0]
    assert schedule.startswith("5 6 * * *")
    assert schedule.endswith("/usr/bin/muralis --once")


# ----------------------------------------------------------------------
# Parsing the configured time
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("09:00", (9, 0)),
        ("23:59", (23, 59)),
        ("00:00", (0, 0)),
        ("7:5", (7, 5)),
        ("9", (9, 0)),
    ],
)
def test_update_time_is_parsed(scheduler, value, expected):
    scheduler.update_time = value
    assert scheduler._hour_minute() == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("garbage", (9, 0)),
        ("99:99", (23, 59)),
        ("-1:-1", (0, 0)),
    ],
)
def test_a_nonsense_time_does_not_crash_the_scheduler(scheduler, value, expected):
    scheduler.update_time = value
    assert scheduler._hour_minute() == expected


# ----------------------------------------------------------------------
# Installing and removing
# ----------------------------------------------------------------------


def test_setup_writes_the_units_into_the_users_systemd_directory(scheduler, profile):
    with patch("subprocess.check_output", return_value="1000"):
        with patch("subprocess.run"):
            with patch("shutil.which", return_value="/usr/bin/muralis"):
                assert scheduler.setup() is True

    user_dir = context.systemd_user_dir()
    assert user_dir.exists()
    assert (user_dir / "muralis.service").exists()
    assert (user_dir / "muralis.timer").exists()

    service = (user_dir / "muralis.service").read_text()
    assert "ExecStart=/usr/bin/muralis --once" in service
    assert "unix:path=/run/user/1000/bus" in service


def test_disable_removes_the_units(scheduler):
    with patch("subprocess.check_output", return_value="1000"):
        with patch("subprocess.run"):
            scheduler.setup()

    assert context.systemd_unit("muralis.timer").exists()

    with patch("subprocess.run"):
        assert scheduler.disable() is True

    assert not context.systemd_unit("muralis.timer").exists()
    assert not context.systemd_unit("muralis.service").exists()


def test_disable_is_false_when_nothing_is_installed(scheduler):
    with patch("subprocess.run") as run:
        run.return_value.returncode = 1
        assert scheduler.disable() is False


def test_the_script_path_comes_from_path(scheduler):
    """The console script on PATH is the entry point systemd must run.

    The old lookup started with ``sys.argv[0]``, so installing the timer from a
    test runner, a wrapper or a ``python -m`` invocation wrote *that* program
    into ExecStart.
    """
    with patch("shutil.which", return_value="/opt/bin/muralis"):
        assert scheduler._get_script_path() == "/opt/bin/muralis"


def test_the_script_path_falls_back_to_argv_zero(scheduler):
    with patch("shutil.which", return_value=None):
        with patch("sys.argv", ["/srv/src/muralis"]):
            assert scheduler._get_script_path() == "/srv/src/muralis"


# ----------------------------------------------------------------------
# The foreground loop
# ----------------------------------------------------------------------


def test_the_daemon_loop_calls_back_and_stops(scheduler, config):
    config.set("general", "update_interval", 300)
    calls = []

    def callback():
        calls.append(1)
        raise RuntimeError("stop the loop")

    def fake_sleep(_seconds):
        raise KeyboardInterrupt

    with patch("time.sleep", side_effect=fake_sleep):
        with pytest.raises(KeyboardInterrupt):
            scheduler.start(run_callback=callback)

    assert len(calls) == 1


def test_the_daemon_respects_auto_update_being_off(scheduler, config):
    config.set("general", "auto_update", "false")
    scheduler.auto_update = False

    with patch("time.sleep") as sleep:
        scheduler.start(run_callback=lambda: None)

    sleep.assert_not_called()

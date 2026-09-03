"""Unit tests for the stopwatch / checklist state machine.

The AHT numbers this app reports are the whole point of the product, so the
timing logic is tested with an injected clock rather than real time - the
assertions are exact, not approximate, and the suite runs instantly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod.session import (IDLE, OVER, PAUSED, RUNNING, WARN, Session,
                              format_duration, parse_duration)


class FakeClock:
    """Monotonic clock the tests advance by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_session(target: int = 300):
    clock = FakeClock()
    session = Session(clock=clock)
    session.bind_case({"id": "voice", "name": "Voice Chat", "target_s": target},
                      autostart=False)
    session.sync_checks([{"id": "a"}, {"id": "b"}])
    return session, clock


# ----------------------------------------------------------------------
# Duration helpers
# ----------------------------------------------------------------------
def test_format_duration_pads_and_rolls_over_to_hours():
    assert format_duration(0) == "00:00"
    assert format_duration(65) == "01:05"
    assert format_duration(600) == "10:00"
    assert format_duration(3725) == "1:02:05"


def test_format_duration_never_shows_negative_time():
    assert format_duration(-30) == "00:00"


def test_parse_duration_reads_a_bare_number_as_minutes():
    # AHT targets are discussed in minutes, so "5" must mean five minutes.
    assert parse_duration("5") == 300
    assert parse_duration("4.5") == 270


def test_parse_duration_reads_clock_notation():
    assert parse_duration("05:30") == 330
    assert parse_duration("1:30:00") == 5400
    assert parse_duration(" 2:05 ") == 125


def test_parse_duration_rejects_garbage():
    for value in ("", "abc", "1:2:3:4", None):
        assert parse_duration(value) is None


# ----------------------------------------------------------------------
# Stopwatch
# ----------------------------------------------------------------------
def test_new_session_is_idle_with_no_elapsed_time():
    session, _clock = make_session()
    assert session.state == IDLE
    assert session.elapsed == 0


def test_elapsed_accumulates_only_while_running():
    session, clock = make_session()
    session.start()
    clock.advance(30)
    assert session.elapsed == 30

    session.pause()
    clock.advance(120)                 # paused: must not count as handle time
    assert session.elapsed == 30
    assert session.paused_seconds == 120

    session.start()
    clock.advance(10)
    assert session.elapsed == 40


def test_paused_time_can_be_included_on_request():
    session, clock = make_session()
    session.start()
    clock.advance(20)
    session.pause()
    clock.advance(15)
    assert session.billable(count_paused=False) == 20
    assert session.billable(count_paused=True) == 35


def test_toggle_alternates_between_running_and_paused():
    session, _clock = make_session()
    session.toggle()
    assert session.state == RUNNING
    session.toggle()
    assert session.state == PAUSED


def test_reset_clears_time_and_checks_but_keeps_the_case_type():
    session, clock = make_session()
    session.start()
    clock.advance(90)
    session.toggle_check("a")

    session.reset(keep_case=True)
    assert session.state == IDLE
    assert session.elapsed == 0
    assert session.cleared_count == 0
    assert session.case_id == "voice"
    assert session.target_s == 300


def test_reset_can_also_drop_the_case_type():
    session, _clock = make_session()
    session.reset(keep_case=False)
    assert session.case_id is None
    assert session.target_s == 0


# ----------------------------------------------------------------------
# AHT status
# ----------------------------------------------------------------------
def test_status_moves_ok_warn_over_around_the_target():
    session, clock = make_session(target=100)
    session.start()
    assert session.status(warn_pct=80) == "ok"

    clock.advance(80)                  # exactly at the warning threshold
    assert session.status(warn_pct=80) == WARN

    clock.advance(25)                  # past the target
    assert session.status(warn_pct=80) == OVER


def test_status_is_always_ok_when_no_target_is_set():
    session, clock = make_session(target=0)
    session.start()
    clock.advance(10_000)
    assert session.status() == "ok"
    assert session.progress == 0.0


def test_progress_and_remaining_track_the_target():
    session, clock = make_session(target=200)
    session.start()
    clock.advance(50)
    assert session.progress == 0.25
    assert session.remaining == 150

    clock.advance(200)
    assert session.progress == 1.25
    assert session.remaining == -50


# ----------------------------------------------------------------------
# Checklist
# ----------------------------------------------------------------------
def test_toggle_check_flips_one_item_and_reports_the_new_value():
    session, _clock = make_session()
    assert session.toggle_check("a") is True
    assert session.toggle_check("a") is False


def test_all_clear_requires_every_item():
    session, _clock = make_session()
    assert not session.all_clear
    session.set_all_checks(True)
    assert session.all_clear
    assert session.pending_count == 0


def test_sync_checks_preserves_existing_ticks_when_the_list_changes():
    # Editing the checklist in Dev Mode must not wipe work already done.
    session, _clock = make_session()
    session.toggle_check("a")
    session.sync_checks([{"id": "a"}, {"id": "b"}, {"id": "c"}])
    assert session.checks == {"a": True, "b": False, "c": False}


def test_sync_checks_drops_items_that_no_longer_exist():
    session, _clock = make_session()
    session.sync_checks([{"id": "b"}])
    assert list(session.checks) == ["b"]


def test_missing_checks_returns_the_labels_still_open():
    session, _clock = make_session()
    session.toggle_check("a")
    items = [{"id": "a", "label": "Escalation"}, {"id": "b", "label": "Evidence"}]
    assert session.missing_checks(items) == ["Evidence"]


def test_has_activity_flags_a_case_worth_confirming_before_discarding():
    session, clock = make_session()
    assert not session.has_activity
    session.start()
    clock.advance(2)
    assert session.has_activity


# ----------------------------------------------------------------------
# History record
# ----------------------------------------------------------------------
def test_snapshot_captures_aggregates_and_no_identifying_data():
    session, clock = make_session(target=100)
    session.start()
    clock.advance(60)
    session.toggle_check("a")

    record = session.snapshot()
    assert record["case_id"] == "voice"
    assert record["duration_s"] == 60
    assert record["target_s"] == 100
    assert record["within_target"] is True
    assert record["cleared"] == 1
    assert record["total_checks"] == 2
    # Privacy guarantee: nothing that could identify a user, case or subject.
    assert set(record) == {
        "ts", "case_id", "case_name", "duration_s", "target_s",
        "effective_target_s", "paused_s", "checks", "cleared", "total_checks",
        "within_target",
    }


def test_snapshot_records_both_the_configured_and_the_adaptive_target():
    """Adaptive targets must not erase what the type is actually budgeted at."""
    session, clock = make_session(target=300)
    session.set_target(240)               # adaptive target for this case
    session.start()
    clock.advance(250)
    record = session.snapshot()
    assert record["target_s"] == 300      # the configured budget
    assert record["effective_target_s"] == 240


def test_restore_puts_a_completed_case_back_on_the_clock():
    """"Undo last case" has to return elapsed time and ticks, paused."""
    session, clock = make_session(target=300)
    session.start()
    clock.advance(120)
    session.toggle_check("a")
    record = session.snapshot()
    session.reset()

    session.restore(record)
    assert session.case_id == "voice"
    assert session.elapsed == 120
    assert session.state == PAUSED
    assert session.checks == {"a": True, "b": False}

    clock.advance(30)
    assert session.elapsed == 120          # stays paused until resumed
    session.start()
    clock.advance(10)
    assert session.elapsed == 130


def test_snapshot_marks_a_case_that_ran_over_target():
    session, clock = make_session(target=30)
    session.start()
    clock.advance(45)
    assert session.snapshot()["within_target"] is False


# ----------------------------------------------------------------------
# Suspended machines
# ----------------------------------------------------------------------
class FakeWall:
    """Wall clock the tests advance independently of the monotonic one."""

    def __init__(self) -> None:
        self.now = 1_700_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_sleepy_session(target: int = 300):
    """A session with both clocks under the test's control."""
    clock, wall = FakeClock(), FakeWall()
    session = Session(clock=clock, wall_clock=wall)
    session.bind_case({"id": "voice", "name": "Voice Chat", "target_s": target},
                      autostart=False)
    session.sync_checks([{"id": "a"}, {"id": "b"}])
    return session, clock, wall


def both(clock, wall, seconds):
    """Advance both clocks together - ordinary running time."""
    clock.advance(seconds)
    wall.advance(seconds)


def test_time_the_machine_slept_through_still_counts():
    """Windows freezes time.monotonic() while suspended; wall time covers it."""
    session, clock, wall = make_sleepy_session()
    session.start()
    both(clock, wall, 60)
    assert session.elapsed == 60

    # The moderator locks the PC and it suspends for ten minutes: real time
    # passes but the monotonic clock does not move.
    wall.advance(600)
    assert session.elapsed == 660

    both(clock, wall, 30)
    assert session.elapsed == 690


def test_a_sleep_gap_is_kept_across_a_pause():
    session, clock, wall = make_sleepy_session()
    session.start()
    both(clock, wall, 10)
    wall.advance(300)               # suspended while running
    session.pause()
    assert session.elapsed == 310

    both(clock, wall, 5)            # paused time does not count
    assert session.elapsed == 310


def test_paused_time_also_covers_a_sleep_gap():
    session, clock, wall = make_sleepy_session()
    session.start()
    both(clock, wall, 10)
    session.pause()
    wall.advance(120)               # suspended while paused
    assert session.paused_seconds == 120
    assert session.elapsed == 10


def test_a_backwards_clock_correction_cannot_shorten_a_case():
    """Taking the max of both deltas makes the stopwatch monotonic in effect."""
    session, clock, wall = make_sleepy_session()
    session.start()
    both(clock, wall, 100)
    wall.advance(-3600)             # NTP correction, or DST on a naive clock
    assert session.elapsed == 100


def test_elapsed_never_goes_negative():
    session, clock, wall = make_sleepy_session()
    session.start()
    wall.advance(-50)
    assert session.elapsed >= 0

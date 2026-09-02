"""Unit tests for the local history log, its statistics and CSV export."""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod.history import History


def record(duration=300, target=300, within=True, checks=None, ts=None,
           name="Voice Chat", case_id=None):
    return {
        "ts": ts if ts is not None else int(time.time()),
        "case_id": case_id or name.split()[0].lower(), "case_name": name,
        "duration_s": duration, "target_s": target, "paused_s": 0,
        "checks": checks if checks is not None else {"a": True, "b": True},
        "cleared": 2, "total_checks": 2, "within_target": within,
    }


def make_history(tmp_path, enabled=True) -> History:
    return History(path=tmp_path / "history.jsonl", enabled=enabled)


# ----------------------------------------------------------------------
# Writing and reading
# ----------------------------------------------------------------------
def test_append_then_load_round_trips_a_record(tmp_path):
    history = make_history(tmp_path)
    assert history.append(record(duration=123))
    rows = history.load()
    assert len(rows) == 1 and rows[0]["duration_s"] == 123


def test_disabling_history_makes_append_a_no_op(tmp_path):
    history = make_history(tmp_path, enabled=False)
    assert history.append(record()) is False
    assert history.load() == []
    assert not (tmp_path / "history.jsonl").exists()


def test_loading_a_missing_file_is_not_an_error(tmp_path):
    assert make_history(tmp_path).load() == []


def test_a_truncated_line_does_not_poison_the_rest_of_the_log(tmp_path):
    path = tmp_path / "history.jsonl"
    history = History(path=path)
    history.append(record(duration=100))
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"ts": 1, "duration_s"\n')      # power loss mid-write
    history.append(record(duration=200))

    rows = history.load()
    assert [row["duration_s"] for row in rows] == [100, 200]


# ----------------------------------------------------------------------
# Retention
# ----------------------------------------------------------------------
def test_prune_drops_records_older_than_the_retention_window(tmp_path):
    history = make_history(tmp_path)
    old = int(time.time()) - 40 * 86400
    history.append(record(ts=old))
    history.append(record())

    assert history.prune(retention_days=30) == 1
    assert len(history.load()) == 1


def test_prune_keeps_everything_when_retention_is_disabled(tmp_path):
    history = make_history(tmp_path)
    history.append(record(ts=int(time.time()) - 4000 * 86400))
    assert history.prune(retention_days=0) == 0
    assert len(history.load()) == 1


def test_wipe_removes_the_log_entirely(tmp_path):
    history = make_history(tmp_path)
    history.append(record())
    assert history.wipe()
    assert history.load() == []


# ----------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------
def test_stats_on_an_empty_log_are_zeroed_not_undefined(tmp_path):
    stats = make_history(tmp_path).stats()
    assert stats["count"] == 0
    assert stats["avg_s"] == 0
    assert stats["by_case"] == {}


def test_stats_average_within_target_and_clean_rates(tmp_path):
    history = make_history(tmp_path)
    history.append(record(duration=100, within=True, checks={"a": True, "b": True}))
    history.append(record(duration=200, within=False, checks={"a": True, "b": False}))

    stats = history.stats()
    assert stats["count"] == 2
    assert stats["avg_s"] == 150
    assert stats["within_pct"] == 50.0
    assert stats["clean_pct"] == 50.0
    assert stats["misses"] == {"b": 1}


def test_stats_group_by_case_type(tmp_path):
    history = make_history(tmp_path)
    history.append(record(duration=100, name="Voice Chat"))
    history.append(record(duration=300, name="Voice Chat"))
    history.append(record(duration=60, name="Island"))

    by_case = history.stats()["by_case"]
    assert by_case["Voice Chat"] == {"count": 2, "total_s": 400, "avg_s": 200}
    assert by_case["Island"]["avg_s"] == 60


def test_today_means_since_local_midnight_not_the_last_24_hours(tmp_path):
    history = make_history(tmp_path)
    history.append(record(ts=int(time.time()) - 2 * 86400))
    history.append(record())
    assert history.stats(window_days=1)["count"] == 1


# ----------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------
def test_csv_export_uses_checklist_labels_as_column_headers(tmp_path):
    history = make_history(tmp_path)
    history.append(record(checks={"escalation": True, "evidence": False}))
    target = tmp_path / "out.csv"

    assert history.export_csv(target, {"escalation": "Escalation Adherence",
                                       "evidence": "Evidence Adherence"})
    with open(target, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows[0][-2:] == ["Escalation Adherence", "Evidence Adherence"]
    assert rows[1][-2:] == ["yes", "no"]
    assert rows[1][2] == "Voice Chat"


def test_csv_export_writes_a_readable_mmss_column(tmp_path):
    history = make_history(tmp_path)
    history.append(record(duration=125))
    target = tmp_path / "out.csv"
    history.export_csv(target)

    with open(target, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert "02:05" in rows[1]


# ----------------------------------------------------------------------
# Weekly plan
# ----------------------------------------------------------------------
CASES = [
    {"id": "voice", "name": "Voice Chat", "target_s": 900},
    {"id": "text", "name": "Text Chat", "target_s": 600},
]


def test_week_start_lands_on_the_most_recent_sunday_midnight():
    from checkmod.history import week_start

    # 2026-09-02 is a Wednesday; the week began on Sunday 2026-08-30.
    wednesday = time.mktime((2026, 9, 2, 14, 30, 0, 0, 0, -1))
    start = time.localtime(week_start(wednesday, starts_on="sunday"))
    assert (start.tm_year, start.tm_mon, start.tm_mday) == (2026, 8, 30)
    assert (start.tm_hour, start.tm_min, start.tm_sec) == (0, 0, 0)
    assert start.tm_wday == 6                      # Sunday


def test_week_start_can_follow_the_iso_monday_convention():
    from checkmod.history import week_start

    wednesday = time.mktime((2026, 9, 2, 14, 30, 0, 0, 0, -1))
    start = time.localtime(week_start(wednesday, starts_on="monday"))
    assert (start.tm_year, start.tm_mon, start.tm_mday) == (2026, 8, 31)
    assert start.tm_wday == 0                      # Monday


def test_week_start_on_a_sunday_is_that_same_midnight():
    from checkmod.history import week_start

    sunday = time.mktime((2026, 8, 30, 9, 0, 0, 0, 0, -1))
    start = time.localtime(week_start(sunday, starts_on="sunday"))
    assert (start.tm_mon, start.tm_mday) == (8, 30)


def test_weekly_plan_reports_the_average_and_the_surplus():
    from checkmod.history import weekly_plan

    rows = [record(duration=1080, name="Voice Chat"),
            record(duration=960, name="Voice Chat"),
            record(duration=1020, name="Voice Chat"),
            record(duration=840, name="Voice Chat")]
    entry = weekly_plan(rows, CASES)["voice"]

    assert entry["count"] == 4
    assert entry["total_s"] == 3900
    assert entry["avg_s"] == 975              # 16:15
    assert entry["debt_s"] == 300             # 5:00 over a 4 x 15:00 budget
    assert entry["on_track"] is False


def test_weekly_plan_projects_the_aht_needed_over_the_next_n_cases():
    from checkmod.history import weekly_plan

    # 300 s of debt against a 900 s target.
    rows = [record(duration=1200, name="Voice Chat")]
    entry = weekly_plan(rows, CASES)["voice"]
    assert entry["debt_s"] == 300

    required = {p["cases"]: p["required_s"] for p in entry["projections"]}
    assert required[5] == 900 - 300 // 5      # 840 -> 14:00
    assert required[10] == 870                # 14:30
    assert required[20] == 885                # 14:45


def test_weekly_plan_flags_a_recovery_that_is_not_reachable():
    from checkmod.history import weekly_plan

    # An hour of debt against a 15:00 target: repaying it over five cases
    # would demand 3:00 each, far under the 9:00 floor. Spread over twenty it
    # is 12:00 each, which is demanding but reachable - and the plan should
    # say so rather than printing an impossible number.
    rows = [record(duration=900 + 3600, name="Voice Chat")]
    entry = weekly_plan(rows, CASES, min_factor=0.6)["voice"]
    by_horizon = {p["cases"]: p for p in entry["projections"]}

    assert by_horizon[5]["required_s"] == 180        # 3:00 - not credible
    assert by_horizon[5]["feasible"] is False
    assert by_horizon[20]["required_s"] == 720       # 12:00 - tight but real
    assert by_horizon[20]["feasible"] is True


def test_weekly_plan_counts_the_cases_needed_at_the_fastest_pace():
    from checkmod.history import weekly_plan

    # debt 360 s, target 900 s, floor 540 s -> gap 360 s -> exactly one case.
    rows = [record(duration=1260, name="Voice Chat")]
    entry = weekly_plan(rows, CASES, min_factor=0.6)["voice"]
    assert entry["debt_s"] == 360
    assert entry["cases_at_floor"] == 1


def test_weekly_plan_gives_back_slack_when_under_budget():
    from checkmod.history import weekly_plan

    rows = [record(duration=540, name="Text Chat", target=600)]
    entry = weekly_plan(rows, CASES, recovery_cases=10)["text"]
    assert entry["debt_s"] == -60
    assert entry["on_track"] is True
    assert entry["adaptive_target_s"] == 606          # 600 + 60/10
    assert entry["cases_at_floor"] is None


def test_the_adaptive_target_is_clamped_at_both_ends():
    from checkmod.history import weekly_plan

    huge_debt = [record(duration=900 + 36000, name="Voice Chat")]
    entry = weekly_plan(huge_debt, CASES, min_factor=0.6)["voice"]
    assert entry["adaptive_target_s"] == int(round(900 * 0.6))

    huge_credit = [record(duration=60, name="Voice Chat") for _ in range(20)]
    entry = weekly_plan(huge_credit, CASES, max_factor=1.25)["voice"]
    assert entry["adaptive_target_s"] == int(round(900 * 1.25))


def test_weekly_plan_reports_zeros_for_a_type_with_no_cases():
    from checkmod.history import weekly_plan

    entry = weekly_plan([], CASES)["voice"]
    assert entry["count"] == 0 and entry["avg_s"] == 0
    assert entry["adaptive_target_s"] == 900       # falls back to the target


def test_remove_last_deletes_only_the_newest_record(tmp_path):
    history = make_history(tmp_path)
    history.append(record(duration=100))
    history.append(record(duration=200))

    removed = history.remove_last()
    assert removed["duration_s"] == 200
    assert [r["duration_s"] for r in history.load()] == [100]


def test_remove_last_on_an_empty_log_returns_none(tmp_path):
    assert make_history(tmp_path).remove_last() is None

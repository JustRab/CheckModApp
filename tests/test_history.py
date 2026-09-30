"""Unit tests for the local history log, its statistics and CSV export."""

from __future__ import annotations

import csv
import json
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


# ----------------------------------------------------------------------
# Caching
# ----------------------------------------------------------------------
def test_repeated_reads_parse_the_file_once(tmp_path, monkeypatch):
    """One user action asks for the log several times; that was N re-parses."""
    import builtins

    history = make_history(tmp_path)
    for _ in range(5):
        history.append(record())

    opens = []
    real_open = builtins.open

    def counting_open(file, *args, **kwargs):
        if str(file) == str(history.path) and (not args or "r" in str(args[0])):
            opens.append(file)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", counting_open)
    for _ in range(6):
        assert len(history.load()) == 5
    assert len(opens) == 1, f"parsed the file {len(opens)} times, expected 1"


def test_a_new_record_invalidates_the_cache(tmp_path):
    history = make_history(tmp_path)
    history.append(record(duration=100))
    assert len(history.load()) == 1

    history.append(record(duration=200))
    assert [r["duration_s"] for r in history.load()] == [100, 200]


def test_removing_the_last_record_invalidates_the_cache(tmp_path):
    history = make_history(tmp_path)
    history.append(record(duration=100))
    history.append(record(duration=200))
    history.load()
    history.remove_last()
    assert [r["duration_s"] for r in history.load()] == [100]


def test_wiping_invalidates_the_cache(tmp_path):
    history = make_history(tmp_path)
    history.append(record())
    history.load()
    history.wipe()
    assert history.load() == []


def test_an_external_edit_is_picked_up(tmp_path):
    """The signature is (mtime, size), so another writer is not missed."""
    history = make_history(tmp_path)
    history.append(record(duration=100))
    assert len(history.load()) == 1

    with open(history.path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record(duration=300)) + "\n")
    assert [r["duration_s"] for r in history.load()] == [100, 300]


def test_the_cached_records_cannot_be_mutated_by_a_caller(tmp_path):
    history = make_history(tmp_path)
    history.append(record())
    rows = history.load()
    rows.append({"ts": 0})
    assert len(history.load()) == 1


# ----------------------------------------------------------------------
# Date ranges and the ranged CSV export (1.4.0)
# ----------------------------------------------------------------------
import datetime                                            # noqa: E402

from checkmod import history as history_mod                # noqa: E402


def midnight(year, month, day) -> float:
    return time.mktime((year, month, day, 0, 0, 0, 0, 0, -1))


def test_a_typed_date_becomes_local_midnight():
    assert history_mod.parse_day("2026-09-30") == midnight(2026, 9, 30)


def test_spreadsheet_separators_are_accepted():
    for text in ("2026/09/30", "2026.09.30", "  2026-09-30 "):
        assert history_mod.parse_day(text) == midnight(2026, 9, 30)


def test_a_date_that_is_not_a_date_is_refused():
    for text in ("", "   ", "yesterday", "30-09-2026x", "2026-02-30", "2026-13-01"):
        assert history_mod.parse_day(text) is None


def test_the_end_date_is_inclusive_for_the_person_typing_it():
    """A case logged at 16:40 on the end date belongs in the report."""
    since, until = history_mod.day_bounds("2026-09-01", "2026-09-07")
    assert since == midnight(2026, 9, 1)
    assert until == midnight(2026, 9, 8)
    assert midnight(2026, 9, 7) + 16 * 3600 < until


def test_reversed_dates_are_swapped_rather_than_returning_nothing():
    assert history_mod.day_bounds("2026-09-07", "2026-09-01") == \
        history_mod.day_bounds("2026-09-01", "2026-09-07")


def test_an_open_bound_stays_open():
    since, until = history_mod.day_bounds("2026-09-01", "")
    assert since == midnight(2026, 9, 1) and until is None
    since, until = history_mod.day_bounds("", "2026-09-07")
    assert since is None and until == midnight(2026, 9, 8)


def test_the_range_presets_line_up_with_the_calendar():
    now = midnight(2026, 9, 30) + 14 * 3600          # a Wednesday afternoon
    bounds = {key: history_mod.range_bounds(key, now, "sunday")
              for key in ("all", "today", "this_week", "last_week",
                          "last_7", "last_30", "this_month", "last_month")}

    assert bounds["all"] == (None, None)
    assert bounds["today"] == (midnight(2026, 9, 30), midnight(2026, 10, 1))
    # Trust & Safety weeks run Sunday to Saturday.
    assert bounds["this_week"][0] == midnight(2026, 9, 27)
    assert bounds["last_week"] == (midnight(2026, 9, 20), midnight(2026, 9, 27))
    assert bounds["last_7"][0] == midnight(2026, 9, 24)
    assert bounds["last_30"][0] == midnight(2026, 9, 1)
    assert bounds["this_month"][0] == midnight(2026, 9, 1)
    assert bounds["last_month"] == (midnight(2026, 8, 1), midnight(2026, 9, 1))


def test_a_monday_week_start_is_honoured():
    now = midnight(2026, 9, 30) + 14 * 3600
    assert history_mod.range_bounds("this_week", now, "monday")[0] == \
        midnight(2026, 9, 28)


def test_last_month_in_january_rolls_back_a_year():
    now = midnight(2026, 1, 15) + 9 * 3600
    assert history_mod.range_bounds("last_month", now) == (
        midnight(2025, 12, 1), midnight(2026, 1, 1))


def test_a_ranged_preset_never_produces_an_inverted_window():
    now = time.time()
    for key in history_mod.RANGE_KEYS:
        since, until = history_mod.range_bounds(key, now)
        if since is not None and until is not None:
            assert since < until, key


def test_a_day_long_range_is_correct_across_a_daylight_saving_change():
    """Adding 86400 would be an hour out on the day the clocks change."""
    since, until = history_mod.day_bounds("2026-03-29", "2026-03-29")
    assert until > since
    assert (until - since) in (82800.0, 86400.0, 90000.0)


def test_the_export_covers_only_the_requested_period(tmp_path):
    history = make_history(tmp_path)
    inside = midnight(2026, 9, 2) + 10 * 3600
    history.append(record(ts=int(midnight(2026, 8, 31)), duration=100))   # before
    history.append(record(ts=int(inside), duration=200))                  # inside
    history.append(record(ts=int(midnight(2026, 9, 9)), duration=300))    # after

    target = tmp_path / "range.csv"
    since, until = history_mod.day_bounds("2026-09-01", "2026-09-07")
    assert history.export_csv(target, since=since, until=until) is True

    with open(target, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["duration_s"] for row in rows] == ["200"]


def test_a_record_on_the_boundary_is_in_exactly_one_of_two_exports(tmp_path):
    """``until`` is exclusive, so adjacent ranges cannot double-count."""
    history = make_history(tmp_path)
    boundary = midnight(2026, 9, 7) + 23 * 3600 + 59 * 60
    history.append(record(ts=int(boundary), duration=555))

    first = tmp_path / "week1.csv"
    second = tmp_path / "week2.csv"
    week1_since, week1_until = history_mod.day_bounds("2026-09-01", "2026-09-07")
    week2_since, week2_until = history_mod.day_bounds("2026-09-08", "2026-09-14")
    history.export_csv(first, since=week1_since, until=week1_until)
    history.export_csv(second, since=week2_since, until=week2_until)

    def durations(path):
        with open(path, newline="", encoding="utf-8-sig") as handle:
            return [row["duration_s"] for row in csv.DictReader(handle)]

    assert durations(first) == ["555"]
    assert durations(second) == []


def test_an_empty_range_still_writes_a_header(tmp_path):
    """A report that says 'no cases' beats a zero-byte file that looks broken."""
    history = make_history(tmp_path)
    history.append(record(ts=int(midnight(2026, 9, 2))))
    target = tmp_path / "empty.csv"
    since, until = history_mod.day_bounds("2026-01-01", "2026-01-07")
    assert history.export_csv(target, since=since, until=until) is True

    with open(target, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 1 and rows[0][0] == "date"


def test_an_unbounded_export_still_covers_everything(tmp_path):
    history = make_history(tmp_path)
    for day in (1, 15, 30):
        history.append(record(ts=int(midnight(2026, 9, day))))
    target = tmp_path / "all.csv"
    assert history.export_csv(target) is True
    with open(target, newline="", encoding="utf-8-sig") as handle:
        assert len(list(csv.DictReader(handle))) == 3


def test_format_day_round_trips_a_bound():
    value = midnight(2026, 9, 30)
    assert history_mod.format_day(value) == "2026-09-30"
    assert history_mod.format_day(None) == ""
    assert history_mod.parse_day(history_mod.format_day(value)) == value


def test_the_calendar_helpers_agree_with_datetime():
    """Guards against an off-by-one in the month arithmetic."""
    now = midnight(2026, 3, 1) + 12 * 3600
    since, until = history_mod.range_bounds("last_month", now)
    first = datetime.date.fromtimestamp(since)
    last_exclusive = datetime.date.fromtimestamp(until)
    assert (first.year, first.month, first.day) == (2026, 2, 1)
    assert (last_exclusive.year, last_exclusive.month, last_exclusive.day) == (2026, 3, 1)

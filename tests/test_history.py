"""Unit tests for the local history log, its statistics and CSV export."""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checkmod.history import History


def record(duration=300, target=300, within=True, checks=None, ts=None, name="Voice Chat"):
    return {
        "ts": ts if ts is not None else int(time.time()),
        "case_id": "voice", "case_name": name,
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

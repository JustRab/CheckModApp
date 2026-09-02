"""Local, append-only history log and the statistics derived from it.

Storage format is JSON Lines: one small JSON object per completed case. That
choice is intentional -

* appending is a single ``open(..., "a")`` + one line, so a crash can never
  corrupt more than the last record;
* the file is greppable and reviewable by anyone (including a privacy or
  security reviewer) without special tooling;
* deleting history is deleting one file.

Nothing in a record identifies a person, a case or a subject: only the case
type, durations and which adherence items were cleared. See
``docs/PRIVACY.md``.
"""

from __future__ import annotations

import csv
import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional

from . import paths

#: Never let the log grow without bound, even with retention disabled.
MAX_RECORDS = 20000


class History:
    """Reader/writer for the case history log."""

    def __init__(self, path=None, enabled: bool = True) -> None:
        self.path = path or paths.history_file()
        self.enabled = enabled

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------
    def append(self, record: Dict[str, Any]) -> bool:
        """Append one completed-case record. No-op when history is disabled."""
        if not self.enabled:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            return True
        except OSError:
            return False

    def prune(self, retention_days: int = 30) -> int:
        """Drop records older than ``retention_days``; returns rows removed.

        ``retention_days <= 0`` keeps everything (bar :data:`MAX_RECORDS`).
        """
        records = self.load()
        if not records:
            return 0
        keep = records
        if retention_days and retention_days > 0:
            cutoff = time.time() - retention_days * 86400
            keep = [r for r in records if r.get("ts", 0) >= cutoff]
        if len(keep) > MAX_RECORDS:
            keep = keep[-MAX_RECORDS:]
        removed = len(records) - len(keep)
        if removed:
            self._rewrite(keep)
        return removed

    def _rewrite(self, records: Iterable[Dict[str, Any]]) -> bool:
        """Atomically replace the log with ``records``."""
        try:
            tmp = str(self.path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    def wipe(self) -> bool:
        """Delete the history file entirely."""
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def load(self, since_ts: Optional[float] = None) -> List[Dict[str, Any]]:
        """Read records, skipping any line that is not valid JSON."""
        records: List[Dict[str, Any]] = []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(record, dict):
                        continue
                    if since_ts is not None and record.get("ts", 0) < since_ts:
                        continue
                    records.append(record)
        except FileNotFoundError:
            return []
        except OSError:
            return []
        return records

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def stats(self, window_days: Optional[int] = None) -> Dict[str, Any]:
        """Aggregate the log into the numbers shown in Dev Mode.

        ``window_days=None`` covers the whole log; ``1`` means "since local
        midnight" rather than "the last 24 hours", which is what an agent
        means by "today".
        """
        since = None
        if window_days == 1:
            since = _local_midnight()
        elif window_days:
            since = time.time() - window_days * 86400

        records = self.load(since_ts=since)
        summary: Dict[str, Any] = {
            "count": len(records),
            "avg_s": 0,
            "within_target": 0,
            "within_pct": 0.0,
            "clean": 0,
            "clean_pct": 0.0,
            "by_case": {},
            "misses": {},
        }
        if not records:
            return summary

        total = 0
        for record in records:
            duration = int(record.get("duration_s", 0) or 0)
            total += duration
            name = record.get("case_name") or record.get("case_id") or "?"
            bucket = summary["by_case"].setdefault(name, {"count": 0, "total_s": 0, "avg_s": 0})
            bucket["count"] += 1
            bucket["total_s"] += duration

            if record.get("within_target", True):
                summary["within_target"] += 1
            checks = record.get("checks") or {}
            if checks and all(checks.values()):
                summary["clean"] += 1
            for check_id, value in checks.items():
                if not value:
                    summary["misses"][check_id] = summary["misses"].get(check_id, 0) + 1

        count = len(records)
        summary["avg_s"] = int(round(total / float(count)))
        summary["within_pct"] = round(100.0 * summary["within_target"] / count, 1)
        summary["clean_pct"] = round(100.0 * summary["clean"] / count, 1)
        for bucket in summary["by_case"].values():
            bucket["avg_s"] = int(round(bucket["total_s"] / float(bucket["count"])))
        return summary

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export_csv(self, target_path, check_labels: Optional[Dict[str, str]] = None) -> bool:
        """Write the log to ``target_path`` as a spreadsheet-friendly CSV."""
        records = self.load()
        labels = check_labels or {}
        check_ids: List[str] = []
        for record in records:
            for check_id in (record.get("checks") or {}):
                if check_id not in check_ids:
                    check_ids.append(check_id)
        header = ["date", "time", "case_type", "duration_s", "duration_mmss",
                  "target_s", "within_target"] + [labels.get(c, c) for c in check_ids]
        try:
            with open(target_path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                for record in records:
                    stamp = time.localtime(record.get("ts", 0))
                    duration = int(record.get("duration_s", 0) or 0)
                    checks = record.get("checks") or {}
                    writer.writerow([
                        time.strftime("%Y-%m-%d", stamp),
                        time.strftime("%H:%M:%S", stamp),
                        record.get("case_name", ""),
                        duration,
                        f"{duration // 60:02d}:{duration % 60:02d}",
                        record.get("target_s", 0),
                        "yes" if record.get("within_target", True) else "no",
                    ] + ["yes" if checks.get(c) else "no" for c in check_ids])
            return True
        except OSError:
            return False


def _local_midnight() -> float:
    """Epoch seconds of the most recent local midnight."""
    now = time.localtime()
    return time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0,
                        now.tm_wday, now.tm_yday, now.tm_isdst))

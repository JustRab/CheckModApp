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
import datetime
import json
import math
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import paths

#: Never let the log grow without bound, even with retention disabled.
MAX_RECORDS = 20000


class History:
    """Reader/writer for the case history log."""

    def __init__(self, path=None, enabled: bool = True) -> None:
        self.path = path or paths.history_file()
        self.enabled = enabled
        # Parsed records, memoised against the file's identity. One user
        # action can ask for the log several times over - today's summary, the
        # weekly plan, the adaptive target - and each was a fresh read and
        # re-parse of every line.
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_signature = None

    def signature(self):
        """Cheap identity for the file: ``(mtime_ns, size)``, or ``None``."""
        try:
            info = os.stat(self.path)
        except OSError:
            return None
        return (info.st_mtime_ns, info.st_size)

    def invalidate(self) -> None:
        """Forget the cached records after this process changes the file."""
        self._cache = None
        self._cache_signature = None

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
            self.invalidate()
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
            self.invalidate()
            return True
        except OSError:
            self.invalidate()
            return False

    def remove_last(self) -> Optional[Dict[str, Any]]:
        """Delete and return the most recent record, or ``None`` if empty.

        Backs the "undo last case" button: agents mis-click Complete, and a
        wrong record quietly skews the weekly average it feeds.
        """
        records = self.load()
        if not records:
            return None
        removed = records[-1]
        if not self._rewrite(records[:-1]):
            return None
        return removed

    def wipe(self) -> bool:
        """Delete the history file entirely."""
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
            self.invalidate()
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def load(self, since_ts: Optional[float] = None) -> List[Dict[str, Any]]:
        """Read records, skipping any line that is not valid JSON.

        The parse is memoised against the file's mtime and size, so repeated
        queries in one refresh cost one read. An edit made by anything else -
        a hand-edit, another copy of the app - changes the signature and is
        picked up on the next call.
        """
        signature = self.signature()
        if self._cache is not None and signature == self._cache_signature:
            return ([r for r in self._cache if r.get("ts", 0) >= since_ts]
                    if since_ts is not None else list(self._cache))

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
                    records.append(record)
        except FileNotFoundError:
            self._cache, self._cache_signature = [], signature
            return []
        except OSError:
            return []

        self._cache, self._cache_signature = records, signature
        if since_ts is not None:
            return [r for r in records if r.get("ts", 0) >= since_ts]
        return list(records)

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

    def week_records(self, starts_on: str = "sunday"):
        """Records logged since the start of the current week."""
        return self.load(since_ts=week_start(starts_on=starts_on))

    def weekly_plan(self, case_types, recovery_cases: int = 10,
                    min_factor: float = 0.6, max_factor: float = 1.25,
                    starts_on: str = "sunday"):
        """:func:`weekly_plan` applied to this week's records."""
        return weekly_plan(self.week_records(starts_on), case_types,
                           recovery_cases, min_factor, max_factor)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export_csv(self, target_path, check_labels: Optional[Dict[str, str]] = None,
                   since: Optional[float] = None,
                   until: Optional[float] = None) -> bool:
        """Write the log to ``target_path`` as a spreadsheet-friendly CSV.

        ``since`` and ``until`` bound the export in epoch seconds; either may
        be ``None`` for "no bound". ``since`` is inclusive and ``until`` is
        exclusive, which is what :func:`day_bounds` produces - so a report for
        a single day covers that day's midnight up to the next, with no risk
        of a case landing in both of two adjacent exports.

        An empty range still writes the header row: a report that reads
        "no cases between these dates" is a result, and a zero-byte file
        looks like a failure.
        """
        records = [r for r in self.load(since_ts=since)
                   if until is None or r.get("ts", 0) < until]
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


def week_start(now: Optional[float] = None, starts_on: str = "sunday") -> float:
    """Epoch seconds of the current week's first midnight.

    Trust & Safety weeks are quoted Sunday-to-Saturday, so that is the
    default; ``starts_on="monday"`` is offered for teams that use ISO weeks.
    """
    stamp = time.localtime(now if now is not None else time.time())
    # tm_wday: Monday=0 ... Sunday=6
    if starts_on == "monday":
        days_back = stamp.tm_wday
    else:
        days_back = (stamp.tm_wday + 1) % 7
    midnight = time.mktime((stamp.tm_year, stamp.tm_mon, stamp.tm_mday, 0, 0, 0,
                            stamp.tm_wday, stamp.tm_yday, stamp.tm_isdst))
    return midnight - days_back * 86400


def weekly_plan(records, case_types, recovery_cases: int = 10,
                min_factor: float = 0.6, max_factor: float = 1.25):
    """Per-case-type weekly AHT position, and what it takes to recover.

    For each case type this returns the week's count and average, the running
    surplus or deficit against the target, and the answer to the question an
    agent actually asks: *how many more cases, and at what AHT, to bring the
    weekly average back to target?*

    The arithmetic, for ``n`` cases totalling ``total`` against target ``T``:

        debt        = total - n * T          (>0 = over budget)
        required(m) = T - debt / m           (AHT for the next m cases)
        cases_at(d) = debt / (T - d)         (m needed at a fixed pace d)

    ``required`` can come out implausibly low - or negative - when the debt is
    large relative to ``m``; the caller is told so via ``feasible`` rather
    than being handed a target nobody can hit.
    """
    plan = {}
    for case in case_types:
        case_id = case.get("id")
        target = int(case.get("target_s", 0) or 0)
        mine = [r for r in records if (r.get("case_id") or r.get("case_name")) == case_id]
        count = len(mine)
        total = sum(int(r.get("duration_s", 0) or 0) for r in mine)
        average = int(round(total / count)) if count else 0
        debt = total - count * target if target else 0

        entry = {
            "id": case_id,
            "name": case.get("name", ""),
            "color": case.get("color", ""),
            "count": count,
            "total_s": total,
            "avg_s": average,
            "target_s": target,
            "debt_s": debt,
            "on_track": debt <= 0,
            "projections": [],
            "cases_at_floor": None,
            "adaptive_target_s": target,
        }

        if target > 0:
            floor = max(1, int(round(target * min_factor)))
            ceiling = int(round(target * max_factor))

            for horizon in (5, 10, 20):
                required = target - debt / float(horizon)
                entry["projections"].append({
                    "cases": horizon,
                    "required_s": int(round(required)),
                    "feasible": required >= floor,
                })

            if debt > 0:
                # Cases needed if every one of them runs at the fastest pace
                # we are willing to ask for.
                gap = target - floor
                entry["cases_at_floor"] = int(math.ceil(debt / gap)) if gap > 0 else None

            adaptive = target - debt / float(max(1, recovery_cases))
            entry["adaptive_target_s"] = int(round(max(floor, min(ceiling, adaptive))))

        plan[case_id] = entry
    return plan


def _local_midnight() -> float:
    """Epoch seconds of the most recent local midnight."""
    now = time.localtime()
    return time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0,
                        now.tm_wday, now.tm_yday, now.tm_isdst))


# ----------------------------------------------------------------------
# Date ranges (CSV export)
# ----------------------------------------------------------------------
#: Ranges offered by the export dialog, in the order they are shown. The UI
#: supplies the wording; the arithmetic lives here so it can be tested without
#: a display. ``custom`` is the two typed dates.
RANGE_KEYS = ("all", "today", "this_week", "last_week", "last_7", "last_30",
              "this_month", "last_month", "custom")


def _midnight_of(day: datetime.date) -> float:
    """Epoch seconds of local midnight on ``day``.

    ``tm_isdst=-1`` asks the C library to work out the offset for that date,
    so ranges stay correct across a daylight-saving change - adding 86400 to
    an epoch would be an hour out for one day a year.
    """
    return time.mktime((day.year, day.month, day.day, 0, 0, 0, 0, 0, -1))


def parse_day(text: Optional[str]) -> Optional[float]:
    """Parse ``YYYY-MM-DD`` into local midnight, or ``None`` if unusable.

    ``/`` and ``.`` are accepted as separators because spreadsheets hand out
    all three. Anything else returns ``None`` so the caller can say "that is
    not a date" instead of exporting a surprising range.
    """
    cleaned = (text or "").strip().replace("/", "-").replace(".", "-")
    if not cleaned:
        return None
    parts = cleaned.split("-")
    if len(parts) != 3:
        return None
    try:
        day = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
    return _midnight_of(day)


def day_bounds(since_text: Optional[str] = "",
               until_text: Optional[str] = "") -> Tuple[Optional[float], Optional[float]]:
    """Turn two typed dates into ``(since, until)`` epoch bounds.

    Both dates are inclusive to the person typing them, so ``until`` is
    returned as the *following* midnight - a case logged at 16:40 on the end
    date belongs in the report. Either side may be blank for an open bound,
    and reversed dates are swapped rather than yielding nothing.
    """
    since = parse_day(since_text)
    end = parse_day(until_text)
    if since is not None and end is not None and end < since:
        since, end = end, since
    until = None
    if end is not None:
        day = datetime.date.fromtimestamp(end) + datetime.timedelta(days=1)
        until = _midnight_of(day)
    return since, until


def range_bounds(key: str, now: Optional[float] = None,
                 starts_on: str = "sunday",
                 since_text: str = "", until_text: str = ""
                 ) -> Tuple[Optional[float], Optional[float]]:
    """Epoch bounds for one of :data:`RANGE_KEYS`.

    ``until`` is exclusive throughout, and ``None`` on either side means "no
    bound". Weeks follow the same Sunday-to-Saturday convention as the weekly
    plan, so an exported week matches the numbers on screen.
    """
    stamp = time.localtime(now if now is not None else time.time())
    today = datetime.date(stamp.tm_year, stamp.tm_mon, stamp.tm_mday)
    tomorrow = _midnight_of(today + datetime.timedelta(days=1))
    week = week_start(now, starts_on)

    if key == "today":
        return _midnight_of(today), tomorrow
    if key == "this_week":
        return week, tomorrow
    if key == "last_week":
        previous = datetime.date.fromtimestamp(week) - datetime.timedelta(days=7)
        return _midnight_of(previous), week
    if key == "last_7":
        return _midnight_of(today - datetime.timedelta(days=6)), tomorrow
    if key == "last_30":
        return _midnight_of(today - datetime.timedelta(days=29)), tomorrow
    if key == "this_month":
        return _midnight_of(today.replace(day=1)), tomorrow
    if key == "last_month":
        first = today.replace(day=1)
        previous = (first - datetime.timedelta(days=1)).replace(day=1)
        return _midnight_of(previous), _midnight_of(first)
    if key == "custom":
        return day_bounds(since_text, until_text)
    return None, None                      # "all", and anything unrecognised


def format_day(value: Optional[float]) -> str:
    """``YYYY-MM-DD`` for an epoch bound, or ``""`` for no bound."""
    if value is None:
        return ""
    return time.strftime("%Y-%m-%d", time.localtime(value))

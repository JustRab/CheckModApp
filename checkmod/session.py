"""Case session: the stopwatch and checklist state machine.

Deliberately free of any Tkinter import so the behaviour that matters most
(AHT accounting) can be unit-tested headlessly and reasoned about on its own.
The UI observes this object and paints it; it never owns timing logic.

Time is measured with :func:`time.monotonic` so the elapsed value cannot be
corrupted by daylight-saving changes or a clock sync mid-case.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, Iterable, List, Optional

#: Lifecycle states of a session.
IDLE = "idle"
RUNNING = "running"
PAUSED = "paused"

#: Timer health, derived from elapsed time versus the AHT target.
OK = "ok"
WARN = "warn"
OVER = "over"


def format_duration(seconds: float, force_hours: bool = False) -> str:
    """Format a duration as ``mm:ss`` (or ``h:mm:ss`` past one hour)."""
    seconds = int(max(0, round(seconds)))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours or force_hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_duration(text: str) -> Optional[int]:
    """Parse ``"5"``, ``"5:30"``, ``"1:05:00"`` or ``"330"`` into seconds.

    A bare number is read as **minutes** because that is how AHT targets are
    discussed day to day. Returns ``None`` when the text is not a duration.
    """
    text = (text or "").strip().replace(" ", "")
    if not text:
        return None
    parts = text.split(":")
    try:
        if len(parts) == 1:
            return max(0, int(round(float(parts[0]) * 60)))
        if len(parts) == 2:
            return max(0, int(parts[0]) * 60 + int(parts[1]))
        if len(parts) == 3:
            return max(0, int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
    except ValueError:
        return None
    return None


class Session:
    """One moderation case in progress.

    Parameters
    ----------
    clock:
        Injectable monotonic time source. Tests pass a fake so elapsed time
        can be advanced deterministically.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.case_id: Optional[str] = None
        self.case_name: str = ""
        self.target_s: int = 0
        self.state: str = IDLE
        self._started_at: Optional[float] = None   # monotonic mark of the run
        self._accumulated: float = 0.0             # completed run segments
        self._paused_total: float = 0.0            # time spent paused
        self._paused_at: Optional[float] = None
        self.checks: Dict[str, bool] = {}
        self.started_wall: Optional[float] = None  # epoch, for the history log

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def bind_case(self, case: Dict, autostart: bool = True) -> None:
        """Attach a case type (and its AHT target) to this session."""
        self.case_id = case.get("id")
        self.case_name = case.get("name", "")
        self.target_s = int(case.get("target_s", 0) or 0)
        if autostart and self.state == IDLE:
            self.start()

    def set_target(self, seconds: int) -> None:
        """Change the AHT target mid-case (Dev Mode / quick AHT editor)."""
        self.target_s = max(0, int(seconds))

    def sync_checks(self, items: Iterable[Dict]) -> None:
        """Add/remove check slots so they mirror the configured checklist.

        Existing ticks are preserved, which means editing the checklist in
        Dev Mode never silently clears work already done on the open case.
        """
        wanted = [item["id"] for item in items]
        self.checks = {cid: self.checks.get(cid, False) for cid in wanted}

    # ------------------------------------------------------------------
    # Stopwatch
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start (or resume) the stopwatch."""
        if self.state == RUNNING:
            return
        now = self._clock()
        if self.state == PAUSED and self._paused_at is not None:
            self._paused_total += now - self._paused_at
        self._paused_at = None
        self._started_at = now
        if self.started_wall is None:
            self.started_wall = time.time()
        self.state = RUNNING

    def pause(self) -> None:
        """Freeze the stopwatch, keeping the time accumulated so far."""
        if self.state != RUNNING:
            return
        now = self._clock()
        if self._started_at is not None:
            self._accumulated += now - self._started_at
        self._started_at = None
        self._paused_at = now
        self.state = PAUSED

    def toggle(self) -> None:
        """Start when idle/paused, pause when running."""
        self.pause() if self.state == RUNNING else self.start()

    def reset(self, keep_case: bool = True) -> None:
        """Return to a pristine state, optionally keeping the case type."""
        self.state = IDLE
        self._started_at = None
        self._accumulated = 0.0
        self._paused_total = 0.0
        self._paused_at = None
        self.started_wall = None
        self.checks = {cid: False for cid in self.checks}
        if not keep_case:
            self.case_id = None
            self.case_name = ""
            self.target_s = 0

    # ------------------------------------------------------------------
    # Derived values
    # ------------------------------------------------------------------
    @property
    def elapsed(self) -> float:
        """Seconds of *active* handling time (paused time excluded)."""
        total = self._accumulated
        if self.state == RUNNING and self._started_at is not None:
            total += self._clock() - self._started_at
        return total

    @property
    def paused_seconds(self) -> float:
        """Seconds spent paused so far."""
        total = self._paused_total
        if self.state == PAUSED and self._paused_at is not None:
            total += self._clock() - self._paused_at
        return total

    def billable(self, count_paused: bool = False) -> float:
        """Elapsed time as it should be reported, per the user's preference."""
        return self.elapsed + (self.paused_seconds if count_paused else 0.0)

    @property
    def remaining(self) -> float:
        """Seconds left before the AHT target (negative once exceeded)."""
        return self.target_s - self.elapsed

    @property
    def progress(self) -> float:
        """Elapsed / target, unclamped so >1.0 means over target."""
        if self.target_s <= 0:
            return 0.0
        return self.elapsed / float(self.target_s)

    def status(self, warn_pct: int = 80) -> str:
        """Return :data:`OK`, :data:`WARN` or :data:`OVER`."""
        if self.target_s <= 0:
            return OK
        pct = self.progress * 100.0
        if pct >= 100.0:
            return OVER
        if pct >= max(1, warn_pct):
            return WARN
        return OK

    # ------------------------------------------------------------------
    # Checklist
    # ------------------------------------------------------------------
    def toggle_check(self, check_id: str) -> bool:
        """Flip one checklist item and return its new value."""
        value = not self.checks.get(check_id, False)
        self.checks[check_id] = value
        return value

    def set_all_checks(self, value: bool) -> None:
        """Tick or untick every checklist item at once."""
        self.checks = {cid: value for cid in self.checks}

    @property
    def cleared_count(self) -> int:
        """How many checklist items are ticked."""
        return sum(1 for value in self.checks.values() if value)

    @property
    def pending_count(self) -> int:
        """How many checklist items are still open."""
        return len(self.checks) - self.cleared_count

    @property
    def all_clear(self) -> bool:
        """``True`` when every configured item is ticked."""
        return bool(self.checks) and self.pending_count == 0

    @property
    def has_activity(self) -> bool:
        """``True`` when there is anything worth confirming before discarding."""
        return self.elapsed > 0.5 or self.cleared_count > 0

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def snapshot(self, count_paused: bool = False) -> Dict:
        """Build the history record for a completed case.

        Only aggregate, non-identifying data is captured: case type, duration,
        target and which adherence items were cleared. There is deliberately
        no field for a case id, a user id or free text.
        """
        return {
            "ts": int(time.time()),
            "case_id": self.case_id or "",
            "case_name": self.case_name,
            "duration_s": int(round(self.billable(count_paused))),
            "target_s": int(self.target_s),
            "paused_s": int(round(self.paused_seconds)),
            "checks": dict(self.checks),
            "cleared": self.cleared_count,
            "total_checks": len(self.checks),
            "within_target": bool(self.target_s <= 0 or self.elapsed <= self.target_s),
        }

    def missing_checks(self, items: List[Dict]) -> List[str]:
        """Labels of the checklist items still unticked (for the UI hint)."""
        return [item["label"] for item in items if not self.checks.get(item["id"], False)]

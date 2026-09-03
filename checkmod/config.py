"""Settings model: defaults, validation, persistence and change notification.

The settings file is plain JSON on purpose. A team lead can open it in
Notepad, diff it, mail it to a colleague or drop a team-wide preset next to
the executable. :class:`Config` guarantees that whatever it reads is merged
onto the defaults, so a truncated, hand-edited or older file can never stop
the app from starting.
"""

from __future__ import annotations

import copy
import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from . import paths

#: Bumped whenever :data:`DEFAULTS` changes shape in a way that needs a
#: migration step in :func:`migrate`.
SCHEMA_VERSION = 2


#: AHT target used for a newly created case type, and as the fallback when a
#: hand-edited settings file carries an unparseable one.
DEFAULT_TARGET_S = 600


def _case(cid: str, name: str, target: int, color: str) -> Dict[str, Any]:
    """Build a case-type record (a work item with its own AHT target)."""
    return {"id": cid, "name": name, "target_s": target, "color": color, "enabled": True}


def _check(cid: str, label: str, hint: str, applies_to=None) -> Dict[str, Any]:
    """Build a checklist-item record.

    ``applies_to`` lists the case-type ids the item is required for. An empty
    list means "every case type", which is the common case and keeps the
    settings file readable.
    """
    return {"id": cid, "label": label, "hint": hint, "enabled": True,
            "applies_to": list(applies_to or [])}


#: Every setting the app understands, with the value used on first run.
#: ``Config`` deep-merges the on-disk file onto this dictionary, so adding a
#: key here is all that is needed to introduce a new setting.
DEFAULTS: Dict[str, Any] = {
    "schema": SCHEMA_VERSION,
    # ----- General ---------------------------------------------------------
    "language": "en",             # any key of checkmod.i18n.STRINGS
    "mode": "user",               # "user" | "dev"
    "first_run": True,            # drives the one-time tutorial
    # ----- Appearance ------------------------------------------------------
    "theme": "midnight",          # key of checkmod.theme.PRESETS
    "accent": "",                 # "" = use the theme's own accent
    "palette_overrides": {},      # token -> "#rrggbb", applied last
    "font_family": "",            # "" = auto-detect the best available
    "font_scale": 1.0,            # 0.8 .. 1.4
    "corner_radius": 12,
    "opacity": 0.97,              # 0.35 .. 1.0
    "show_ring": True,            # circular timer vs. slim bar
    "show_footer_stats": True,
    "compact": False,             # collapsed "pill" layout
    # ----- Window ----------------------------------------------------------
    "always_on_top": True,
    "frameless": True,            # custom title bar instead of the OS one
    # A borderless window is a "tool window" to the Windows shell, which hides
    # it from the taskbar and Alt+Tab. This forces it back into both.
    "show_in_taskbar": True,
    "snap_to_edges": True,
    "snap_threshold": 18,
    "remember_position": True,
    "window": {"x": None, "y": None, "w": 360, "h": 600},
    # ----- Timer behaviour -------------------------------------------------
    "auto_start_on_select": True,   # picking a case type starts the clock
    "warn_at_pct": 80,              # amber threshold, % of the AHT target
    "alert_on_over": True,          # red state + optional beep past target
    # On by default: an AHT alert nobody switched on is an alert nobody hears.
    "sound_enabled": True,
    "confirm_reset": True,
    "require_all_checks": False,    # block "Complete" until every box is ticked
    "count_paused_time": False,
    # Heads-up alert a few seconds before the target is reached, so the agent
    # can start wrapping up rather than discovering the overrun afterwards.
    "prealert_enabled": True,
    "prealert_seconds": 10,
    # ----- Adaptive AHT ----------------------------------------------------
    # The timer target can track the weekly average instead of sitting on the
    # static per-type number: run long on a few cases and the next ones ask
    # for a little less, which is what actually keeps a weekly AHT on plan.
    "adaptive_target": True,
    "adaptive_recovery_cases": 10,  # spread any correction over this many cases
    "adaptive_min_factor": 0.6,     # never demand less than 60% of the target
    "adaptive_max_factor": 1.25,    # never hand back more than 125% of it
    "week_starts_on": "sunday",     # "sunday" | "monday"
    # ----- Data ------------------------------------------------------------
    "history_enabled": True,
    "history_retention_days": 30,
    # ----- Domain data -----------------------------------------------------
    "case_types": [
        _case("voice", "Voice Chat", 900, "#7C5CFF"),    # 15:00
        _case("text", "Text Chat", 600, "#2BB3A3"),      # 10:00
        _case("island", "Island", 1200, "#F2A03D"),      # 20:00
    ],
    "checklist": [
        _check("escalation", "Escalation Adherence",
               "The case was escalated to the right queue / tier when required."),
        _check("enforcement", "Enforcement Adherence",
               "The action applied matches the policy and the severity tier."),
        # Voice and Text chat cases carry no evidence to attach, so this item
        # only applies to Island.
        _check("evidence", "Evidence Adherence",
               "Evidence is attached, legible and sufficient to justify the action.",
               applies_to=["island"]),
        _check("comment", "Comment Adherence",
               "The internal comment explains the reasoning clearly and completely."),
    ],
}

#: Hard bounds applied on load so a hand-edited file cannot produce an
#: unusable window (invisible, zero-sized, off-screen...).
LIMITS = {
    "opacity": (0.35, 1.0),
    "font_scale": (0.8, 1.4),
    "corner_radius": (0, 24),
    "warn_at_pct": (10, 100),
    "snap_threshold": (0, 60),
    "history_retention_days": (0, 3650),
    "prealert_seconds": (0, 120),
    "adaptive_recovery_cases": (1, 200),
    "adaptive_min_factor": (0.2, 1.0),
    "adaptive_max_factor": (1.0, 3.0),
    "window.w": (280, 900),
    "window.h": (320, 1400),
}


def new_id(prefix: str) -> str:
    """Return a short unique identifier for user-created records."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _deep_merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``incoming`` onto a copy of ``base``.

    Lists are replaced wholesale (the user's case types win over the
    defaults); dictionaries are merged key by key so new default keys appear
    automatically in old settings files.
    """
    out = copy.deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Upgrade a settings dictionary to :data:`SCHEMA_VERSION`.

    Kept as an explicit hook so future releases can reshape settings without
    ever discarding a user's configuration.
    """
    schema = int(data.get("schema", 0) or 0)

    if schema < 2:
        # Schema 2 introduced per-case-type checklist applicability. Existing
        # items keep applying everywhere (an empty list), except the built-in
        # Evidence item, which only ever made sense for Island cases.
        for item in data.get("checklist") or []:
            if not isinstance(item, dict) or "applies_to" in item:
                continue
            item["applies_to"] = ["island"] if item.get("id") == "evidence" else []

    data["schema"] = max(schema, SCHEMA_VERSION)
    return data


class Config:
    """Mutable, observable application settings backed by a JSON file.

    Values are addressed with dotted paths (``"window.w"``), which keeps the
    UI code free of nested-dictionary plumbing::

        config.get("opacity")
        config.set("window.w", 420)
        config.subscribe(on_change)
    """

    def __init__(self, path=None, autosave: bool = True) -> None:
        self.path = path or paths.settings_file()
        self.autosave = autosave
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULTS)
        self._listeners: List[Callable[[str], None]] = []
        self._muted = False
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Read the settings file, falling back to defaults on any error."""
        raw: Dict[str, Any] = {}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, dict):
                raw = {}
        except FileNotFoundError:
            raw = {}
        except (OSError, ValueError):
            # Corrupted file: keep a copy so nothing is silently destroyed.
            self._quarantine()
            raw = {}
        self.data = self.validate(_deep_merge(DEFAULTS, migrate(raw)))

    def _quarantine(self) -> None:
        """Rename an unreadable settings file instead of overwriting it."""
        try:
            broken = f"{self.path}.broken-{int(time.time())}"
            import os

            os.replace(self.path, broken)
        except OSError:
            pass

    def save(self) -> bool:
        """Write settings atomically. Returns ``True`` on success."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            # Keep the previous revision so Dev Mode can offer a rollback.
            if self.path.exists():
                try:
                    import shutil

                    shutil.copyfile(self.path, paths.backup_file())
                except OSError:
                    pass
            import os

            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        """Return the value at ``dotted`` path, or ``default`` if missing."""
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any, notify: bool = True) -> None:
        """Assign ``value`` at ``dotted`` path, then persist and notify."""
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if node.get(parts[-1]) == value:
            return
        node[parts[-1]] = value
        self.data = self.validate(self.data)
        if self.autosave:
            self.save()
        if notify:
            self.notify(dotted)

    def update(self, values: Dict[str, Any]) -> None:
        """Apply several dotted assignments with a single notification."""
        self._muted = True
        try:
            for key, value in values.items():
                self.set(key, value, notify=False)
        finally:
            self._muted = False
        self.notify("*")

    def reset(self) -> None:
        """Restore every setting to its factory value."""
        self.data = copy.deepcopy(DEFAULTS)
        self.data["first_run"] = False
        if self.autosave:
            self.save()
        self.notify("*")

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------
    def subscribe(self, callback: Callable[[str], None]) -> Callable[[str], None]:
        """Register ``callback(dotted_key)``; returns it for easy removal."""
        self._listeners.append(callback)
        return callback

    def unsubscribe(self, callback: Callable[[str], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify(self, key: str = "*") -> None:
        """Tell every subscriber that ``key`` changed (``"*"`` = everything)."""
        if self._muted:
            return
        for callback in list(self._listeners):
            try:
                callback(key)
            except Exception:  # pragma: no cover - a broken view must not
                pass          # take the whole application down.

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce ``data`` into something the UI can always render."""
        for dotted, (low, high) in LIMITS.items():
            parts = dotted.split(".")
            node = data
            ok = True
            for part in parts[:-1]:
                node = node.get(part) if isinstance(node, dict) else None
                if not isinstance(node, dict):
                    ok = False
                    break
            if not ok:
                continue
            current = node.get(parts[-1])
            if isinstance(current, bool) or current is None:
                continue
            if isinstance(current, (int, float)):
                clamped = _clamp(float(current), low, high)
                node[parts[-1]] = type(current)(clamped) if isinstance(current, int) else clamped

        from .i18n import DEFAULT_LANGUAGE, STRINGS

        data["mode"] = "dev" if data.get("mode") == "dev" else "user"
        if data.get("language") not in STRINGS:
            data["language"] = DEFAULT_LANGUAGE
        data["case_types"] = self._clean_cases(data.get("case_types"))
        data["checklist"] = self._clean_checks(data.get("checklist"))
        return data

    @staticmethod
    def _clean_cases(items: Any) -> List[Dict[str, Any]]:
        """Drop malformed case types and guarantee at least one exists."""
        cleaned: List[Dict[str, Any]] = []
        for item in items or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            try:
                target = int(item.get("target_s", DEFAULT_TARGET_S))
            except (TypeError, ValueError):
                target = DEFAULT_TARGET_S
            cleaned.append({
                "id": str(item.get("id") or new_id("case")),
                "name": str(item["name"])[:40],
                "target_s": max(10, min(24 * 3600, target)),
                "color": str(item.get("color") or "#5B8CFF"),
                "enabled": bool(item.get("enabled", True)),
            })
        return cleaned or copy.deepcopy(DEFAULTS["case_types"])

    @staticmethod
    def _clean_checks(items: Any) -> List[Dict[str, Any]]:
        """Drop malformed checklist items; an empty checklist is allowed."""
        cleaned: List[Dict[str, Any]] = []
        for item in items or []:
            if not isinstance(item, dict) or not item.get("label"):
                continue
            applies = item.get("applies_to")
            if not isinstance(applies, list):
                applies = []
            cleaned.append({
                "id": str(item.get("id") or new_id("chk")),
                "label": str(item["label"])[:60],
                "hint": str(item.get("hint", ""))[:240],
                "enabled": bool(item.get("enabled", True)),
                "applies_to": [str(value) for value in applies if value],
            })
        return cleaned

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------
    def active_cases(self) -> List[Dict[str, Any]]:
        """Case types the user actually wants to see in User Mode."""
        return [c for c in self.get("case_types", []) if c.get("enabled", True)]

    def active_checks(self, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Checklist items in force, optionally narrowed to one case type.

        An item with an empty ``applies_to`` applies everywhere; otherwise it
        only appears for the case types it names. Passing ``case_id=None``
        returns every enabled item, which is what the Dev Mode editor wants.
        """
        items = [c for c in self.get("checklist", []) if c.get("enabled", True)]
        if case_id is None:
            return items
        return [c for c in items
                if not c.get("applies_to") or case_id in c["applies_to"]]

    def case_by_id(self, case_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Look up a case type by id, or ``None``."""
        for case in self.get("case_types", []):
            if case.get("id") == case_id:
                return case
        return None

    # ------------------------------------------------------------------
    # Import / export (team presets)
    # ------------------------------------------------------------------
    def export_to(self, path) -> bool:
        """Write the current settings to ``path`` as a shareable preset."""
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
            return True
        except OSError:
            return False

    def import_from(self, path) -> bool:
        """Merge a preset file onto the current settings."""
        try:
            with open(path, "r", encoding="utf-8") as handle:
                incoming = json.load(handle)
            if not isinstance(incoming, dict):
                return False
        except (OSError, ValueError):
            return False
        incoming.pop("first_run", None)
        self.data = self.validate(_deep_merge(self.data, migrate(incoming)))
        if self.autosave:
            self.save()
        self.notify("*")
        return True

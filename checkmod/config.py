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
SCHEMA_VERSION = 1


def _case(cid: str, name: str, target: int, color: str) -> Dict[str, Any]:
    """Build a case-type record (a work item with its own AHT target)."""
    return {"id": cid, "name": name, "target_s": target, "color": color, "enabled": True}


def _check(cid: str, label: str, hint: str) -> Dict[str, Any]:
    """Build a checklist-item record."""
    return {"id": cid, "label": label, "hint": hint, "enabled": True}


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
    "snap_to_edges": True,
    "snap_threshold": 18,
    "remember_position": True,
    "window": {"x": None, "y": None, "w": 360, "h": 600},
    # ----- Timer behaviour -------------------------------------------------
    "auto_start_on_select": True,   # picking a case type starts the clock
    "warn_at_pct": 80,              # amber threshold, % of the AHT target
    "alert_on_over": True,          # red state + optional beep past target
    "sound_enabled": False,
    "confirm_reset": True,
    "require_all_checks": False,    # block "Complete" until every box is ticked
    "count_paused_time": False,
    # ----- Data ------------------------------------------------------------
    "history_enabled": True,
    "history_retention_days": 30,
    # ----- Domain data -----------------------------------------------------
    "case_types": [
        _case("voice", "Voice Chat", 300, "#7C5CFF"),
        _case("text", "Text Chat", 240, "#2BB3A3"),
        _case("island", "Island", 420, "#F2A03D"),
    ],
    "checklist": [
        _check("escalation", "Escalation Adherence",
               "The case was escalated to the right queue / tier when required."),
        _check("enforcement", "Enforcement Adherence",
               "The action applied matches the policy and the severity tier."),
        _check("evidence", "Evidence Adherence",
               "Evidence is attached, legible and sufficient to justify the action."),
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
    # if schema < 2: ...  (future migrations land here)
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
                target = int(item.get("target_s", 300))
            except (TypeError, ValueError):
                target = 300
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
            cleaned.append({
                "id": str(item.get("id") or new_id("chk")),
                "label": str(item["label"])[:60],
                "hint": str(item.get("hint", ""))[:240],
                "enabled": bool(item.get("enabled", True)),
            })
        return cleaned

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------
    def active_cases(self) -> List[Dict[str, Any]]:
        """Case types the user actually wants to see in User Mode."""
        return [c for c in self.get("case_types", []) if c.get("enabled", True)]

    def active_checks(self) -> List[Dict[str, Any]]:
        """Checklist items currently enabled."""
        return [c for c in self.get("checklist", []) if c.get("enabled", True)]

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

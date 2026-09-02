"""Application shell: window management, state wiring and the tick loop.

:class:`App` owns the three long-lived objects (:class:`~checkmod.config.Config`,
:class:`~checkmod.session.Session`, :class:`~checkmod.history.History`) and the
Tk root window. Views are throwaway: any settings change that affects layout
rebuilds them, which keeps the rendering path simple and stateless.

Window strategy
---------------
With ``frameless`` enabled the OS decorations are removed
(``overrideredirect``) and CheckMod paints its own title bar. That is what
allows a small, always-on-top companion window that looks the same
everywhere. The trade-off - no taskbar button, no OS minimise - is covered by
the compact layout and can be turned off in Dev Mode.

Nothing here touches the registry, installs a service or hooks the keyboard
globally: shortcuts are bound to this window only, so the app needs no
elevation and no IT involvement.
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import List, Optional, Tuple

from . import APP_NAME, __version__, paths
from .config import Config
from .history import History
from .i18n import Translator
from .session import Session
from .theme import build_theme
from .ui import dialogs
from .ui.dev_view import DevView
from .ui.fonts import build_fonts
from .ui.titlebar import ResizeGrip, TitleBar
from .ui.tutorial import Tutorial
from .ui.user_view import UserView

#: Display refresh period. 200 ms keeps the seconds column honest while
#: costing a fraction of a percent of one CPU core.
TICK_MS = 200

#: Height of the compact layout, in pixels (title bar excluded).
COMPACT_BODY_H = 104


class App:
    """The CheckMod application."""

    def __init__(self) -> None:
        self.config = Config()
        self.translator = Translator(self.config.get("language", "en"))
        self.session = Session()
        self.history = History(paths.history_file(),
                               enabled=bool(self.config.get("history_enabled", True)))
        self.history.prune(int(self.config.get("history_retention_days", 30)))

        self.root = tk.Tk()
        self.theme = build_theme(self.config)
        self.fonts = build_fonts(self.config)

        self.body: Optional[tk.Frame] = None
        self.titlebar: Optional[TitleBar] = None
        self.grip: Optional[ResizeGrip] = None
        self.view = None
        self.tutorial: Optional[Tutorial] = None
        self._restyle_job = None
        self._tick_job = None
        self._over_alerted = False
        self._flash_state = False

        self._setup_root()
        self.rebuild_shell()
        self.config.subscribe(self._on_config_change)

        # Restore the previously selected case type so the app is usable the
        # instant it opens.
        cases = self.config.active_cases()
        if cases:
            self.session.bind_case(cases[0], autostart=False)
        self.sync_checklist()

        if self.config.get("first_run", True):
            self.root.after(350, self.show_tutorial)

        self._tick()

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def t(self, key: str, **fmt) -> str:
        """Shorthand for the active translation."""
        return self.translator.t(key, **fmt)

    # ------------------------------------------------------------------
    # Root window
    # ------------------------------------------------------------------
    def _setup_root(self) -> None:
        root = self.root
        root.title(f"{APP_NAME} {__version__}")
        root.configure(bg=self.theme["bg"])
        root.minsize(280, 160)
        self._load_icon()

        geometry = self.config.get("window", {}) or {}
        width = int(geometry.get("w") or 360)
        height = int(geometry.get("h") or 600)
        x, y = geometry.get("x"), geometry.get("y")
        if not self.config.get("remember_position", True) or x is None or y is None:
            x = (root.winfo_screenwidth() - width) // 2
            y = max(30, (root.winfo_screenheight() - height) // 3)
        x, y = self._clamp_to_screen(int(x), int(y), width, height)
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.apply_window_flags()
        self._bind_shortcuts()

    def _load_icon(self) -> None:
        """Best-effort window icon; a missing icon is never fatal."""
        try:
            ico = paths.resource_dir() / "assets" / "icon.ico"
            if ico.exists() and sys.platform.startswith("win"):
                self.root.iconbitmap(default=str(ico))
                return
            png = paths.resource_dir() / "assets" / "icon.png"
            if png.exists():
                self._icon_image = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._icon_image)
        except tk.TclError:
            pass

    def apply_window_flags(self) -> None:
        """Push always-on-top, opacity and decoration settings to the OS."""
        root = self.root
        try:
            root.wm_attributes("-topmost", bool(self.config.get("always_on_top", True)))
        except tk.TclError:
            pass
        try:
            root.wm_attributes("-alpha", float(self.config.get("opacity", 0.97)))
        except tk.TclError:
            pass
        try:
            root.overrideredirect(bool(self.config.get("frameless", True)))
        except tk.TclError:
            pass

    def _bind_shortcuts(self) -> None:
        """Window-scoped keyboard shortcuts (never a global OS hook)."""
        root = self.root
        bindings = {
            "<space>": lambda _e: self._guarded(self.toggle_timer),
            "<Control-r>": lambda _e: self._guarded(self.reset_session),
            "<Control-Return>": lambda _e: self._guarded(self.complete_case),
            "<Control-d>": lambda _e: self.toggle_mode(),
            "<Control-t>": lambda _e: self.toggle_on_top(),
            "<Control-m>": lambda _e: self.toggle_compact(),
            "<Control-q>": lambda _e: self.request_close(),
            "<F1>": lambda _e: self.show_tutorial(),
            "<Escape>": lambda _e: self._on_escape(),
        }
        for sequence, handler in bindings.items():
            root.bind(sequence, handler)
        for index in range(1, 10):
            root.bind(f"<Key-{index}>",
                      lambda _e, i=index: self._guarded(lambda: self._toggle_check_index(i - 1)))
            root.bind(f"<Alt-Key-{index}>",
                      lambda _e, i=index: self._select_case_index(i - 1))

    def _guarded(self, action) -> None:
        """Run ``action`` unless a text field currently has focus.

        Without this, typing "5" into an AHT field in Dev Mode would also tick
        the fifth checklist item.
        """
        widget = self.root.focus_get()
        if isinstance(widget, (tk.Entry, tk.Text)):
            return
        action()

    def _on_escape(self) -> None:
        if self.tutorial is not None:
            self.tutorial.close()

    # ------------------------------------------------------------------
    # Shell / views
    # ------------------------------------------------------------------
    def rebuild_shell(self) -> None:
        """Rebuild the title bar, body and grip from scratch."""
        for child in self.root.winfo_children():
            child.destroy()
        self.tutorial = None
        self.root.configure(bg=self.theme["bg"])
        self.apply_window_flags()

        frameless = bool(self.config.get("frameless", True))
        if frameless:
            self.titlebar = TitleBar(self.root, self)
            self.titlebar.pack(fill="x")
        else:
            self.titlebar = None
            self.root.title(f"{APP_NAME} {__version__}")

        self.body = tk.Frame(self.root, bg=self.theme["bg"])
        self.body.pack(fill="both", expand=True)

        if frameless:
            grip_size = ResizeGrip.size_for(self.fonts)
            footer = tk.Frame(self.root, bg=self.theme["bg_alt"], height=grip_size)
            footer.pack(fill="x", side="bottom")
            footer.pack_propagate(False)
            self.grip = ResizeGrip(footer, self)
            self.grip.pack(side="right")
        else:
            self.grip = None

        self._build_view()
        self._apply_layout_size()

    def _build_view(self) -> None:
        """Create the view matching the current mode."""
        if self.view is not None:
            try:
                self.view.destroy()
            except tk.TclError:
                pass
        if self.config.get("mode") == "dev":
            self.view = DevView(self.body, self)
        else:
            self.view = UserView(self.body, self)
        self.view.pack(fill="both", expand=True)
        if self.titlebar:
            self.titlebar.refresh()

    def _apply_layout_size(self) -> None:
        """Resize the window to fit the compact / full layout."""
        if self.config.get("mode") == "dev":
            return
        # winfo_width() reports 1 until the window is first mapped, so fall
        # back to the stored width rather than collapsing the window.
        width = self.root.winfo_width()
        if width <= 1:
            width = int(self.config.get("window.w", 360) or 360)
        chrome = self.chrome_height()
        if self.config.get("compact"):
            height = COMPACT_BODY_H + chrome
        else:
            # Grow to fit: a larger text scale or extra checklist items must
            # never push the Complete button off the bottom of the window.
            self.root.update_idletasks()
            needed = self.view.winfo_reqheight() + chrome
            stored = int(self.config.get("window.h", 600) or 600)
            height = min(max(stored, needed), self.root.winfo_screenheight() - 60)
        self.root.geometry(f"{width}x{height}")

    def chrome_height(self) -> int:
        """Pixels taken by the custom title bar and resize grip (0 if native).

        Derived from the live widgets when they exist so the value tracks the
        font scale and the display's DPI, both of which change how tall the
        title bar has to be.
        """
        if not self.config.get("frameless", True):
            return 0
        bar = self.titlebar.height if self.titlebar else TitleBar.height_for(self.fonts)
        grip = self.grip.SIZE if self.grip else ResizeGrip.size_for(self.fonts)
        return bar + grip

    def refresh_views(self) -> None:
        """Light refresh: no widget tree rebuild."""
        if isinstance(self.view, UserView):
            self.view.sync()
        if self.titlebar:
            self.titlebar.refresh()

    def schedule_restyle(self) -> None:
        """Coalesce rapid setting changes into a single rebuild.

        Dragging a slider fires dozens of changes per second; without this the
        app would rebuild its whole widget tree on each one.
        """
        if self._restyle_job:
            try:
                self.root.after_cancel(self._restyle_job)
            except tk.TclError:
                pass
        self._restyle_job = self.root.after(90, self._restyle_now)

    def _restyle_now(self) -> None:
        self._restyle_job = None
        self.theme = build_theme(self.config)
        self.fonts = build_fonts(self.config)
        section = getattr(self.view, "section", None)
        self.rebuild_shell()
        if section and isinstance(self.view, DevView):
            self.view.show(section)

    def _on_config_change(self, key: str) -> None:
        """React to a settings change coming from anywhere in the app."""
        if key in ("theme", "accent", "palette_overrides", "font_family", "font_scale",
                   "corner_radius", "compact", "show_ring", "show_footer_stats",
                   "language", "mode", "*"):
            self.schedule_restyle()
        elif key in ("always_on_top", "opacity", "frameless"):
            self.apply_window_flags()

    # ------------------------------------------------------------------
    # Window manipulation
    # ------------------------------------------------------------------
    def move_window(self, x: int, y: int) -> None:
        """Move the window during a title-bar drag."""
        self.root.geometry(f"+{int(x)}+{int(y)}")

    def resize_window(self, width: int, height: int) -> None:
        """Resize from the grip, respecting sane minimums."""
        width = max(280, min(900, int(width)))
        height = max(160, min(1400, int(height)))
        self.root.geometry(f"{width}x{height}")

    def _clamp_to_screen(self, x: int, y: int, width: int, height: int) -> Tuple[int, int]:
        """Keep the window reachable if the display layout changed."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(-width + 60, min(x, screen_w - 60))
        y = max(0, min(y, screen_h - 60))
        return x, y

    def snap_and_store(self) -> None:
        """Snap to screen edges after a drag, then remember the geometry."""
        root = self.root
        root.update_idletasks()
        x, y = root.winfo_x(), root.winfo_y()
        width, height = root.winfo_width(), root.winfo_height()

        if self.config.get("snap_to_edges", True):
            threshold = int(self.config.get("snap_threshold", 18))
            screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
            if abs(x) <= threshold:
                x = 0
            elif abs((x + width) - screen_w) <= threshold:
                x = screen_w - width
            if abs(y) <= threshold:
                y = 0
            elif abs((y + height) - screen_h) <= threshold:
                y = screen_h - height
            root.geometry(f"+{x}+{y}")

        window = dict(self.config.get("window", {}) or {})
        window.update({"x": x, "y": y, "w": width})
        if not self.config.get("compact") and self.config.get("mode") != "dev":
            window["h"] = height
        self.config.set("window", window, notify=False)

    def center_window(self) -> None:
        """Re-centre the window (recovery from an off-screen position)."""
        root = self.root
        root.update_idletasks()
        width, height = root.winfo_width(), root.winfo_height()
        x = (root.winfo_screenwidth() - width) // 2
        y = max(30, (root.winfo_screenheight() - height) // 3)
        root.geometry(f"+{x}+{y}")
        self.snap_and_store()

    # ------------------------------------------------------------------
    # Toggles
    # ------------------------------------------------------------------
    def toggle_mode(self) -> None:
        """Switch between User Mode and Dev Mode."""
        self.config.set("mode", "user" if self.config.get("mode") == "dev" else "dev")

    def toggle_on_top(self) -> None:
        self.config.set("always_on_top", not self.config.get("always_on_top", True))
        if self.titlebar:
            self.titlebar.refresh()

    def toggle_compact(self) -> None:
        self.config.set("compact", not self.config.get("compact", False))

    def set_language(self, code: str) -> None:
        """Change UI language and repaint."""
        self.translator.set_language(code)
        self.config.set("language", code)

    def set_history_enabled(self, enabled: bool) -> None:
        """Enable/disable local logging without restarting."""
        self.history.enabled = bool(enabled)

    def reload_storage(self) -> None:
        """Re-resolve the data folder (after toggling portable mode)."""
        self.config.path = paths.settings_file()
        self.config.load()
        self.history = History(paths.history_file(),
                               enabled=bool(self.config.get("history_enabled", True)))
        self.translator.set_language(self.config.get("language", "en"))
        self.schedule_restyle()

    # ------------------------------------------------------------------
    # Session actions
    # ------------------------------------------------------------------
    def select_case(self, case_id: str) -> None:
        """Bind a case type to the session (optionally starting the clock)."""
        case = self.config.case_by_id(case_id)
        if not case:
            return
        # Switching type mid-case keeps elapsed time: moderators often
        # reclassify a case after opening it.
        self.session.bind_case(case, autostart=bool(self.config.get("auto_start_on_select", True)))
        self._over_alerted = False
        self.refresh_views()

    def _select_case_index(self, index: int) -> None:
        cases = self.config.active_cases()
        if 0 <= index < len(cases):
            self.select_case(cases[index]["id"])

    def toggle_timer(self) -> None:
        """Start / pause the stopwatch."""
        if self.session.case_id is None:
            cases = self.config.active_cases()
            if not cases:
                return
            self.select_case(cases[0]["id"])
            if self.session.state == "running":
                return
        self.session.toggle()
        self.refresh_views()

    def reset_session(self) -> None:
        """Clear the timer and checklist for the current case."""
        if self.config.get("confirm_reset", True) and self.session.has_activity:
            if not dialogs.confirm(self, self.t("dlg.reset_q")):
                return
        self.session.reset(keep_case=True)
        self._over_alerted = False
        self.refresh_views()

    def complete_case(self) -> None:
        """Log the case, reset the session and get ready for the next one."""
        session = self.session
        if session.case_id is None:
            return
        if self.config.get("require_all_checks") and not session.all_clear:
            dialogs.alert(self, self.t("dlg.require_checks"))
            return
        record = session.snapshot(count_paused=bool(self.config.get("count_paused_time")))
        if self.config.get("history_enabled", True):
            self.history.append(record)
        session.reset(keep_case=True)
        self._over_alerted = False
        self.refresh_views()

    def on_check_toggled(self, _check_id: str, _value: bool) -> None:
        """Callback from a checklist row; refreshes derived UI state."""
        if isinstance(self.view, UserView):
            self.view._sync_controls()      # noqa: SLF001 - same package, intentional
            self.view._sync_mini_checks()   # noqa: SLF001

    def sync_checklist(self) -> None:
        """Mirror the configured checklist into the session and rebuild rows."""
        self.session.sync_checks(self.config.active_checks())
        if isinstance(self.view, UserView) and self.view.checklist is not None:
            self.view.checklist.rebuild()
            self.view.sync()

    def sync_session_target(self) -> None:
        """Re-read the AHT target after it was edited."""
        case = self.config.case_by_id(self.session.case_id)
        if case:
            self.session.set_target(int(case.get("target_s", 0)))
            self._over_alerted = False
        self.refresh_views()

    def update_case_target(self, case_id: str, seconds: int) -> None:
        """Persist a new AHT target for ``case_id`` (quick editor)."""
        cases = [dict(c) for c in self.config.get("case_types", [])]
        for case in cases:
            if case["id"] == case_id:
                case["target_s"] = int(seconds)
                break
        self.config.set("case_types", cases)
        self.sync_session_target()

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------
    def show_tutorial(self) -> None:
        """Open the walkthrough overlay (idempotent).

        The overlay covers the body only, never the title bar: a tutorial you
        cannot drag out of the way is worse than no tutorial, and the pin and
        close buttons have to stay reachable too.
        """
        if self.tutorial is not None:
            return
        parent = self.body if self.body is not None else self.root
        self.tutorial = Tutorial(parent, self, on_close=self._on_tutorial_closed)
        self.tutorial.place(in_=parent, relx=0, rely=0, relwidth=1, relheight=1)
        self.tutorial.lift()

    def _on_tutorial_closed(self) -> None:
        self.tutorial = None

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        """Advance the clock display and fire the over-target alert."""
        try:
            if isinstance(self.view, UserView):
                self.view.tick()
            self._update_status_dot()
            self._check_over_alert()
        except tk.TclError:  # pragma: no cover - window closing
            return
        self._tick_job = self.root.after(TICK_MS, self._tick)

    def _update_status_dot(self) -> None:
        """Keep the title-bar dot in sync with the AHT state."""
        if not self.titlebar:
            return
        status = self.session.status(int(self.config.get("warn_at_pct", 80)))
        case = self.config.case_by_id(self.session.case_id)
        if status == "ok" and case:
            color = case.get("color", self.theme["accent"])
        else:
            color = self.theme.status_color(status)
        if status == "over" and self.config.get("alert_on_over", True):
            # Slow blink so an exceeded AHT is noticeable without being noisy.
            self._flash_state = not self._flash_state
            if not self._flash_state:
                color = self.theme["bg_alt"]
        self.titlebar.set_status_color(color)

    def _check_over_alert(self) -> None:
        """Beep once, at most, when a case first passes its AHT target."""
        if self._over_alerted or not self.config.get("alert_on_over", True):
            return
        if self.session.target_s <= 0 or self.session.state != "running":
            return
        if self.session.elapsed < self.session.target_s:
            return
        self._over_alerted = True
        if self.config.get("sound_enabled", False):
            self._beep()

    def _beep(self) -> None:
        """Play a short alert using only what the platform already provides."""
        try:
            if sys.platform.startswith("win"):
                import winsound

                winsound.Beep(880, 140)
            else:
                self.root.bell()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------
    def shortcut_help(self) -> List[Tuple[str, str]]:
        """``(keys, description)`` pairs shown in Dev Mode > About."""
        return [
            ("Space", f"{self.t('user.start')} / {self.t('user.pause')}"),
            ("1 - 9", self.t("user.checklist")),
            ("Alt+1-9", self.t("user.case_type")),
            ("Ctrl+Enter", self.t("user.complete")),
            ("Ctrl+R", self.t("user.reset")),
            ("Ctrl+D", self.t("mode.to_dev")),
            ("Ctrl+T", self.t("dev.always_on_top")),
            ("Ctrl+M", self.t("tb.compact")),
            ("F1", self.t("tb.help")),
            ("Ctrl+Q", self.t("tb.close")),
        ]

    def _toggle_check_index(self, index: int) -> None:
        """Toggle the n-th checklist item (number-key shortcut)."""
        items = self.config.active_checks()
        if not (0 <= index < len(items)):
            return
        check_id = items[index]["id"]
        self.session.toggle_check(check_id)
        if isinstance(self.view, UserView):
            self.view.sync()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def request_close(self) -> None:
        """Ask for confirmation when a case is in flight, then shut down."""
        if self.session.has_activity and not dialogs.confirm(self, self.t("dlg.close_q")):
            return
        self.shutdown()

    def shutdown(self) -> None:
        """Persist geometry and destroy the window."""
        try:
            self.snap_and_store()
            self.config.save()
        except Exception:
            pass
        if self._tick_job:
            try:
                self.root.after_cancel(self._tick_job)
            except tk.TclError:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        """Enter the Tk main loop."""
        self.root.mainloop()


def main() -> int:
    """Entry point used by ``python -m checkmod`` and by the executable."""
    try:
        App().run()
    except KeyboardInterrupt:  # pragma: no cover
        return 130
    return 0

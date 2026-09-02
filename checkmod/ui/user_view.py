"""User Mode - the deliberately small surface.

Everything a moderator needs during a case and nothing else:

1. pick the case type (which selects its AHT target),
2. watch the timer,
3. clear the four adherence checks,
4. complete the case.

Two layouts share this class. The full layout uses a circular gauge; the
compact layout collapses to a single strip that can live in a screen corner
next to the moderation queue.
"""

from __future__ import annotations

import tkinter as tk
from typing import Dict

from ..session import format_duration, parse_duration
from . import dialogs
from .checkrow import ChecklistPanel
from .primitives import Bar, Button, Ring, Segmented, Tooltip, draw_round_rect


class UserView(tk.Frame):
    """The default view: case type, timer, checklist, complete."""

    def __init__(self, parent, app) -> None:
        self.app = app
        super().__init__(parent, bg=app.theme["bg"], highlightthickness=0, bd=0)
        self.compact = bool(app.config.get("compact"))
        self._mini_checks: Dict[str, tk.Canvas] = {}
        self.build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def build(self) -> None:
        """(Re)create the widget tree for the current layout and settings."""
        for child in self.winfo_children():
            child.destroy()
        self._mini_checks = {}
        self.compact = bool(self.app.config.get("compact"))
        if self.compact:
            self._build_compact()
        else:
            self._build_full()
        self.sync()

    # -- full layout ---------------------------------------------------
    def _build_full(self) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        pad = 14

        outer = tk.Frame(self, bg=theme["bg"])
        outer.pack(fill="both", expand=True, padx=pad, pady=(10, 10))

        # --- case type selector ---------------------------------------
        self._caption(outer, app.t("user.case_type")).pack(fill="x", pady=(0, 6))
        self.segmented = Segmented(
            outer, theme, fonts, app.config.active_cases(),
            on_select=app.select_case, height=36,
            radius=max(4, int(app.config.get("corner_radius", 12)) - 4),
        )
        self.segmented.pack(fill="x")
        if not app.config.active_cases():
            tk.Label(outer, text=app.t("user.no_cases"), bg=theme["bg"],
                     fg=theme["text_faint"], font=fonts["small"], wraplength=280,
                     justify="left").pack(fill="x", pady=8)

        # --- timer ----------------------------------------------------
        timer_box = tk.Frame(outer, bg=theme["bg"])
        timer_box.pack(fill="x", pady=(12, 6))
        if app.config.get("show_ring", True):
            self.ring = Ring(timer_box, theme, fonts, size=150, thickness=11, bg_token="bg")
            self.ring.pack()
            self.bar = None
        else:
            self.ring = None
            self.big_time = tk.Label(timer_box, text="00:00", bg=theme["bg"],
                                     fg=theme["text"], font=fonts["display"])
            self.big_time.pack(pady=(4, 6))
            self.bar = Bar(timer_box, theme, fonts, height=8, bg_token="bg")
            self.bar.pack(fill="x", pady=(0, 4))

        # --- target / remaining ---------------------------------------
        self.meta = tk.Canvas(outer, height=24, bg=theme["bg"], highlightthickness=0,
                              bd=0, cursor="hand2")
        self.meta.pack(fill="x", pady=(2, 10))
        self.meta.bind("<Button-1>", lambda _e: self.edit_target())
        self.meta_tip = Tooltip(self.meta, app.t("user.edit_aht"))

        # --- transport controls ---------------------------------------
        controls = tk.Frame(outer, bg=theme["bg"])
        controls.pack(fill="x")
        self.btn_toggle = Button(controls, theme, fonts, text=app.t("user.start"),
                                 command=app.toggle_timer, variant="primary", height=38,
                                 radius=max(4, int(app.config.get("corner_radius", 12)) - 2),
                                 bg_token="bg")
        self.btn_toggle.pack(side="left", fill="x", expand=True)
        self.btn_reset = Button(controls, theme, fonts, text=app.t("user.reset"),
                                command=app.reset_session, variant="soft", height=38,
                                radius=max(4, int(app.config.get("corner_radius", 12)) - 2),
                                bg_token="bg", width=86)
        self.btn_reset.pack(side="left", padx=(8, 0))

        # --- checklist ------------------------------------------------
        header = tk.Frame(outer, bg=theme["bg"])
        header.pack(fill="x", pady=(16, 6))
        self._caption(header, app.t("user.checklist")).pack(side="left")
        self.btn_mark_all = Button(header, theme, fonts, text=app.t("user.mark_all"),
                                   command=self._toggle_all, variant="ghost", height=20,
                                   radius=6, bg_token="bg", font_key="tiny", width=90)
        self.btn_mark_all.pack(side="right")

        self.checklist = ChecklistPanel(outer, app)
        self.checklist.pack(fill="x")

        self.hint = tk.Label(outer, text="", bg=theme["bg"], fg=theme["text_faint"],
                             font=fonts["tiny"], anchor="w")
        self.hint.pack(fill="x", pady=(6, 0))

        # --- complete -------------------------------------------------
        self.btn_complete = Button(
            outer, theme, fonts, text=app.t("user.complete"), command=app.complete_case,
            variant="primary", height=42,
            radius=max(4, int(app.config.get("corner_radius", 12)) - 2), bg_token="bg",
            font_key="body_bold",
        )
        self.btn_complete.pack(fill="x", pady=(10, 0))

        # --- footer stats ---------------------------------------------
        footer_row = tk.Frame(outer, bg=theme["bg"])
        footer_row.pack(fill="x", pady=(10, 0))
        self.btn_undo = Button(
            footer_row, theme, fonts, text="\u21b6", command=app.undo_last_case,
            variant="ghost", height=22, radius=6, bg_token="bg", font_key="small",
            width=28, tooltip=app.t("user.undo_last"),
        )
        self.btn_undo.pack(side="right")
        if app.config.get("show_footer_stats", True):
            self.footer = tk.Label(footer_row, text="", bg=theme["bg"],
                                   fg=theme["text_faint"], font=fonts["tiny"],
                                   anchor="w")
            self.footer.pack(side="left", fill="x", expand=True)
        else:
            self.footer = None

    # -- compact layout ------------------------------------------------
    def _build_compact(self) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts

        outer = tk.Frame(self, bg=theme["bg"])
        outer.pack(fill="both", expand=True, padx=10, pady=8)

        top = tk.Frame(outer, bg=theme["bg"])
        top.pack(fill="x")
        self.segmented = Segmented(
            top, theme, fonts, app.config.active_cases(), on_select=app.select_case,
            height=26, radius=6,
        )
        self.segmented.pack(fill="x")

        middle = tk.Frame(outer, bg=theme["bg"])
        middle.pack(fill="x", pady=(8, 4))
        self.big_time = tk.Label(middle, text="00:00", bg=theme["bg"], fg=theme["text"],
                                 font=fonts["h1"])
        self.big_time.pack(side="left")
        self.btn_toggle = Button(middle, theme, fonts, text=app.t("user.start"),
                                 command=app.toggle_timer, variant="primary", height=26,
                                 radius=6, bg_token="bg", font_key="tiny_bold", width=74)
        self.btn_toggle.pack(side="right")
        self.btn_complete = Button(middle, theme, fonts, text="OK", command=app.complete_case,
                                   variant="soft", height=26, radius=6, bg_token="bg",
                                   font_key="tiny_bold", width=42,
                                   tooltip=app.t("user.complete"))
        self.btn_complete.pack(side="right", padx=6)

        self.bar = Bar(outer, theme, fonts, height=6, bg_token="bg")
        self.bar.pack(fill="x", pady=(0, 6))
        self.ring = None

        # Mini checklist: one square per item, tooltip carries the full label.
        chips = tk.Frame(outer, bg=theme["bg"])
        chips.pack(fill="x")
        for item in app.config.active_checks(app.session.case_id):
            chip = tk.Canvas(chips, width=26, height=22, bg=theme["bg"],
                             highlightthickness=0, bd=0, cursor="hand2")
            chip.pack(side="left", padx=(0, 5))
            chip.bind("<Button-1>", lambda _e, cid=item["id"]: self._toggle_one(cid))
            Tooltip(chip, item.get("label", ""))
            self._mini_checks[item["id"]] = chip

        self.btn_undo = Button(
            chips, theme, fonts, text="\u21b6", command=app.undo_last_case,
            variant="ghost", height=22, radius=6, bg_token="bg", font_key="small",
            width=26, tooltip=app.t("user.undo_last"),
        )
        self.btn_undo.pack(side="right")

        self.meta = None
        self.checklist = None
        self.hint = None
        self.footer = None
        self.btn_reset = None
        self.btn_mark_all = None

    def _caption(self, parent, text: str) -> tk.Label:
        """Small uppercase section caption."""
        return tk.Label(parent, text=text.upper(), bg=self.app.theme["bg"],
                        fg=self.app.theme["text_faint"], font=self.app.fonts["tiny_bold"],
                        anchor="w")

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _toggle_all(self) -> None:
        """Tick everything, or untick everything when already complete."""
        target = not self.app.session.all_clear
        self.app.session.set_all_checks(target)
        self.sync()

    def _toggle_one(self, check_id: str) -> None:
        self.app.session.toggle_check(check_id)
        self.app.on_check_toggled(check_id, self.app.session.checks.get(check_id, False))
        self.sync()

    def edit_target(self) -> None:
        """Quick AHT editor for the selected case type (also in Dev Mode)."""
        app = self.app
        case = app.config.case_by_id(app.session.case_id)
        if not case:
            return
        answer = dialogs.prompt(
            app, f"{app.t('dev.target')} - {case['name']}",
            format_duration(case.get("target_s", 0)),
            "mm:ss  ·  5 = 5 min  ·  1:30:00 = 1 h 30 min",
        )
        if answer is None:
            return
        seconds = parse_duration(answer)
        if seconds is None or seconds <= 0:
            dialogs.alert(app, app.t("dlg.failed"))
            return
        app.update_case_target(case["id"], seconds)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def sync(self) -> None:
        """Repaint everything that depends on session or config state."""
        app = self.app
        session = app.session
        self.segmented.set_options(app.config.active_cases())
        self.segmented.set_selected(session.case_id)

        if self.checklist is not None:
            self.checklist.sync()
        self._sync_mini_checks()
        self._sync_controls()
        self.tick()
        self._sync_footer()

    def _sync_controls(self) -> None:
        app = self.app
        session = app.session
        running = session.state == "running"
        if session.state == "idle":
            label = app.t("user.start")
        elif running:
            label = app.t("user.pause")
        else:
            label = app.t("user.resume")
        self.btn_toggle.set_text(label)
        self.btn_toggle.set_variant("soft" if running else "primary")
        self.btn_toggle.set_enabled(session.case_id is not None)

        require_all = bool(app.config.get("require_all_checks"))
        can_complete = session.case_id is not None and (not require_all or session.all_clear)
        self.btn_complete.set_enabled(can_complete)

        if self.btn_mark_all is not None:
            self.btn_mark_all.set_text(
                app.t("user.clear_all") if session.all_clear else app.t("user.mark_all"))

        if self.hint is not None:
            pending = session.pending_count
            if not session.checks:
                text, color = "", app.theme["text_faint"]
            elif pending == 0:
                text, color = app.t("user.all_clear"), app.theme["ok"]
            else:
                key = "user.pending_one" if pending == 1 else "user.pending_many"
                text, color = app.t(key, n=pending), app.theme["text_faint"]
            self.hint.configure(text=text, fg=color)

    def _sync_mini_checks(self) -> None:
        """Paint the compact-layout checklist squares."""
        from .. import theme as theme_mod

        session = self.app.session
        theme = self.app.theme
        for check_id, chip in self._mini_checks.items():
            chip.delete("all")
            done = session.checks.get(check_id, False)
            fill = theme["ok"] if done else theme["surface"]
            outline = "" if done else theme["border"]
            draw_round_rect(chip, 1, 2, 25, 20, 5, fill=fill, outline=outline)
            if done:
                chip.create_line(7, 11, 11, 15, 19, 6,
                                 fill=theme_mod.readable_on(theme["ok"]),
                                 width=2, capstyle="round", joinstyle="round")

    def _sync_footer(self) -> None:
        """Update the one-line summary of today's work."""
        if self.footer is None:
            return
        app = self.app
        if not app.config.get("history_enabled", True):
            self.footer.configure(text=app.t("footer.history_off"))
            return
        stats = app.history.stats(window_days=1)
        today = (f"{app.t('footer.today')} {stats['count']}"
                 if stats["count"] else f"{app.t('footer.today')} 0")

        # The weekly line for the selected type: that is the average the
        # adaptive target is steering, so it belongs on screen.
        week = ""
        entry = app.weekly_plan().get(app.session.case_id) if app.session.case_id else None
        if entry and entry["count"]:
            arrow = "\u25b2" if entry["debt_s"] > 0 else "\u25bc"
            week = (f"   ·   {app.t('user.week')} {entry['count']}"
                    f"  {format_duration(entry['avg_s'])} {arrow}")
        self.footer.configure(text=today + week)

    def tick(self) -> None:
        """Called ~5x/second by the app to advance the timer display."""
        app = self.app
        session = app.session
        warn_pct = int(app.config.get("warn_at_pct", 80))
        status = session.status(warn_pct)
        case = app.config.case_by_id(session.case_id)
        case_color = (case or {}).get("color") if status == "ok" else None
        elapsed_text = format_duration(session.elapsed)

        if session.state == "running":
            state_text = app.t("user.running")
        elif session.state == "paused":
            state_text = app.t("user.paused")
        else:
            state_text = app.t("user.idle")

        if self.ring is not None:
            # Just the number: the "Meta 05:00" pill right below already
            # says what it is being compared against, and a longer string
            # would collide with the ring's inner edge.
            bottom = ""
            if session.target_s:
                remaining = session.remaining
                bottom = (f"+{format_duration(-remaining)}" if remaining < 0
                          else format_duration(remaining))
            self.ring.update_values(session.progress, status, elapsed_text,
                                    top=state_text, bottom=bottom, accent=case_color)
        else:
            self.big_time.configure(
                text=elapsed_text,
                fg=app.theme.status_color(status) if status != "ok" else app.theme["text"])
            if self.bar is not None:
                self.bar.update_values(session.progress, status, accent=case_color)

        if self.meta is not None:
            self._paint_meta(status)
            if session.base_target_s and session.target_s != session.base_target_s:
                self.meta_tip.set_text(
                    f"{app.t('user.adaptive')} - "
                    f"{app.t('user.base_target')} {format_duration(session.base_target_s)}. "
                    f"{app.t('user.edit_aht')}.")
            else:
                self.meta_tip.set_text(app.t("user.edit_aht"))

    def _paint_meta(self, status: str) -> None:
        """Draw the 'Target 05:00 · edit' strip under the timer."""
        app = self.app
        canvas = self.meta
        canvas.delete("all")
        width = canvas.winfo_width()
        if width <= 1:
            return
        theme, fonts = app.theme, app.fonts
        session = app.session
        target = format_duration(session.target_s) if session.target_s else "--:--"
        label = f"{app.t('user.target')}  {target}"
        # When the adaptive target differs from the configured one, show the
        # delta so the number never looks arbitrary.
        adapted = (session.base_target_s and session.target_s
                   and session.target_s != session.base_target_s)
        if adapted:
            delta = session.target_s - session.base_target_s
            label += f"  ({'+' if delta > 0 else '-'}{format_duration(abs(delta))})"
        pill_w = fonts.measure(label, "small") + 46
        x1 = (width - pill_w) / 2
        draw_round_rect(canvas, x1, 1, x1 + pill_w, 23, 11,
                        fill=theme["surface"], outline=theme["border"])
        color = theme["text_dim"]
        if status == "over":
            color = theme["danger"]
        elif adapted:
            color = theme["accent"]
        canvas.create_text(x1 + 14, 12, anchor="w", text=label, fill=color,
                           font=fonts["small"])
        # Pencil affordance drawn by hand (no glyph dependency).
        px = x1 + pill_w - 22
        canvas.create_line(px, 16, px + 9, 7, fill=theme["accent"], width=1.6,
                           capstyle="round")
        canvas.create_line(px + 9, 7, px + 11, 9, fill=theme["accent"], width=1.6,
                           capstyle="round")
        canvas.create_line(px, 16, px + 3, 16, fill=theme["accent"], width=1.6,
                           capstyle="round")

    # ------------------------------------------------------------------
    def restyle(self, theme, fonts) -> None:
        """A theme/font change rebuilds this view outright (cheap and safe)."""
        self.configure(bg=theme["bg"])
        self.build()

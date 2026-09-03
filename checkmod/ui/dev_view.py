"""Dev Mode - the full configuration surface.

Everything the product can do is exposed here, grouped into eight sections a
chip bar switches between. Only one section is built at a time: the window is
small, and rebuilding a section is fast enough (a few dozen canvas widgets)
that keeping the whole tree alive would only cost memory and redraw time.

Sections
--------
appearance  theme, accent, fonts, radius, opacity, layout switches
window      always-on-top, custom title bar, snapping, position
cases       case types and their AHT targets  (the core requirement)
checklist   adherence items - add, rename, describe, reorder, disable
behaviour   timer rules, warning thresholds, confirmations
data        history, retention, exports, portable mode, erase
stats       aggregates computed from the local history
about       version, storage path, shortcuts, tutorial
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import tkinter as tk
from typing import Callable, Dict, Optional

from .. import (__author__, __version__, alerts, paths, shortcuts,
                theme as theme_mod)
from ..config import DEFAULT_TARGET_S, new_id
from ..session import format_duration, parse_duration
from . import dialogs
from .fonts import PREFERRED_FAMILIES, available_families
from .primitives import (Button, ScrollFrame, Switch, Slider, Tooltip,
                         draw_round_rect, widget_size)


class DevView(tk.Frame):
    """Scrollable, sectioned settings panel."""

    #: ``(key, chip label, section heading)`` - the chip bar is only ~70 px
    #: per cell, so chips use the short form and headings the full one.
    SECTIONS = [
        ("appearance", "dev.tab.appearance", "dev.appearance"),
        ("window", "dev.tab.window", "dev.window"),
        ("cases", "dev.tab.cases", "dev.cases"),
        ("checklist", "dev.tab.checklist", "dev.checklist"),
        ("behavior", "dev.tab.behavior", "dev.behavior"),
        ("data", "dev.tab.data", "dev.data"),
        ("stats", "dev.tab.stats", "dev.stats"),
        ("about", "dev.tab.about", "dev.about"),
    ]

    def __init__(self, parent, app) -> None:
        self.app = app
        self.section = "appearance"
        super().__init__(parent, bg=app.theme["bg"], highlightthickness=0, bd=0)
        self._chips: Dict[str, Button] = {}
        self.build()

    # ------------------------------------------------------------------
    # Frame
    # ------------------------------------------------------------------
    def build(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        theme, fonts = self.app.theme, self.app.fonts

        chip_bar = tk.Frame(self, bg=theme["bg_alt"])
        chip_bar.pack(fill="x")
        self._chips = {}
        for index, (key, label_key, _heading_key) in enumerate(self.SECTIONS):
            chip = Button(
                chip_bar, theme, fonts, text=self.app.t(label_key),
                command=lambda k=key: self.show(k),
                variant="primary" if key == self.section else "ghost",
                height=24, radius=6, bg_token="bg_alt", font_key="tiny", width=10,
            )
            chip.grid(row=index // 4, column=index % 4, sticky="ew", padx=2, pady=2)
            self._chips[key] = chip
        for column in range(4):
            chip_bar.grid_columnconfigure(column, weight=1, uniform="chips")

        self.scroller = ScrollFrame(self, theme, fonts, bg_token="bg")
        self.scroller.pack(fill="both", expand=True)
        self._render_section()

    def show(self, key: str) -> None:
        """Switch to a section and repaint the chip bar."""
        self.section = key
        for name, chip in self._chips.items():
            chip.set_variant("primary" if name == key else "ghost")
        self._render_section()

    def _render_section(self) -> None:
        for child in self.scroller.body.winfo_children():
            child.destroy()
        renderer = {
            "appearance": self._section_appearance,
            "window": self._section_window,
            "cases": self._section_cases,
            "checklist": self._section_checklist,
            "behavior": self._section_behavior,
            "data": self._section_data,
            "stats": self._section_stats,
            "about": self._section_about,
        }[self.section]
        renderer(self.scroller.body)
        self.scroller.scroll_to_top()

    def refresh(self) -> None:
        """Re-render the active section (after a settings change)."""
        self._render_section()

    def restyle(self, theme, fonts) -> None:
        self.configure(bg=theme["bg"])
        self.build()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def _card(self, parent, pady: int = 6) -> tk.Frame:
        """Rounded-looking container used to group related settings."""
        theme = self.app.theme
        outer = tk.Frame(parent, bg=theme["border"])
        outer.pack(fill="x", padx=12, pady=pady)
        inner = tk.Frame(outer, bg=theme["surface"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return inner

    def _heading(self, parent, text: str, hint: str = "") -> None:
        theme, fonts = self.app.theme, self.app.fonts
        tk.Label(parent, text=text.upper(), bg=theme["bg"], fg=theme["text_faint"],
                 font=fonts["tiny_bold"], anchor="w").pack(fill="x", padx=14, pady=(12, 2))
        if hint:
            tk.Label(parent, text=hint, bg=theme["bg"], fg=theme["text_faint"],
                     font=fonts["tiny"], anchor="w", justify="left",
                     wraplength=300).pack(fill="x", padx=14, pady=(0, 4))

    def _row(self, parent, label: str, hint: str = "") -> tk.Frame:
        """A label on the left and room for a control on the right."""
        theme, fonts = self.app.theme, self.app.fonts
        row = tk.Frame(parent, bg=theme["surface"])
        row.pack(fill="x", padx=12, pady=7)
        text = tk.Label(row, text=label, bg=theme["surface"], fg=theme["text"],
                        font=fonts["small"], anchor="w", justify="left", wraplength=190)
        text.pack(side="left", fill="x", expand=True)
        if hint:
            Tooltip(text, hint)
        return row

    def _switch_row(self, parent, label: str, key: str, hint: str = "",
                    on_change: Optional[Callable[[bool], None]] = None) -> Switch:
        """Boolean setting bound directly to a dotted config key."""
        row = self._row(parent, label, hint)

        def handler(value: bool, key=key) -> None:
            self.app.config.set(key, value)
            if on_change:
                on_change(value)

        switch = Switch(row, self.app.theme, self.app.fonts,
                        value=bool(self.app.config.get(key)), on_change=handler,
                        bg_token="surface")
        switch.pack(side="right")
        return switch

    def _slider_row(self, parent, label: str, key: str, minimum: float, maximum: float,
                    step: float, fmt: Callable[[float], str],
                    on_change: Optional[Callable[[float], None]] = None) -> None:
        """Numeric setting with a live value read-out."""
        theme, fonts = self.app.theme, self.app.fonts
        block = tk.Frame(parent, bg=theme["surface"])
        block.pack(fill="x", padx=12, pady=(7, 2))
        header = tk.Frame(block, bg=theme["surface"])
        header.pack(fill="x")
        tk.Label(header, text=label, bg=theme["surface"], fg=theme["text"],
                 font=fonts["small"], anchor="w").pack(side="left")
        value_label = tk.Label(header, text=fmt(self.app.config.get(key, minimum)),
                               bg=theme["surface"], fg=theme["text_dim"],
                               font=fonts["small_bold"])
        value_label.pack(side="right")

        def handler(value: float, key=key) -> None:
            value_label.configure(text=fmt(value))
            stored = int(round(value)) if float(step).is_integer() else round(value, 3)
            self.app.config.set(key, stored)
            if on_change:
                on_change(value)

        Slider(block, theme, fonts, minimum=minimum, maximum=maximum,
               value=float(self.app.config.get(key, minimum)), step=step,
               on_change=handler, bg_token="surface").pack(fill="x", pady=(2, 6))

    def _entry(self, parent, value: str, on_commit: Callable[[str], None],
               width: int = 10, font_key: str = "small") -> tk.Entry:
        """Flat, themed text field that commits on Return or focus loss."""
        theme, fonts = self.app.theme, self.app.fonts
        entry = tk.Entry(parent, bg=theme["bg_alt"], fg=theme["text"],
                         insertbackground=theme["text"], relief="flat",
                         font=fonts[font_key], width=width, highlightthickness=1,
                         highlightbackground=theme["border"],
                         highlightcolor=theme["accent"])
        entry.insert(0, value)
        entry.bind("<Return>", lambda _e: on_commit(entry.get()))
        entry.bind("<FocusOut>", lambda _e: on_commit(entry.get()))
        return entry

    def _action(self, parent, label: str, command: Callable[[], None],
                variant: str = "soft", hint: str = "") -> Button:
        button = Button(parent, self.app.theme, self.app.fonts, text=label,
                        command=command, variant=variant, height=32, radius=8,
                        bg_token="surface", tooltip=hint)
        button.pack(fill="x", padx=12, pady=4)
        return button

    # ==================================================================
    # Sections
    # ==================================================================
    def _section_appearance(self, parent) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts

        self._heading(parent, app.t("dev.theme"))
        card = self._card(parent)
        grid = tk.Frame(card, bg=theme["surface"])
        grid.pack(fill="x", padx=10, pady=10)
        presets = list(theme_mod.PRESETS.items())
        for index, (key, palette) in enumerate(presets):
            swatch = _ThemeSwatch(grid, app, key, palette,
                                  selected=(key == app.config.get("theme")),
                                  command=lambda k=key: app.config.set("theme", k))
            swatch.grid(row=index // 4, column=index % 4, padx=3, pady=3, sticky="ew")
        for column in range(4):
            grid.grid_columnconfigure(column, weight=1, uniform="sw")

        self._heading(parent, app.t("dev.accent"))
        card = self._card(parent)
        swatches = tk.Frame(card, bg=theme["surface"])
        swatches.pack(fill="x", padx=10, pady=10)
        current_accent = app.config.get("accent", "")
        for index, color in enumerate(theme_mod.ACCENT_SWATCHES):
            dot = _ColorDot(swatches, app, color, selected=(color.lower() == current_accent.lower()),
                            command=lambda c=color: app.config.set("accent", c))
            dot.grid(row=index // 5, column=index % 5, padx=4, pady=4)
        for column in range(5):
            swatches.grid_columnconfigure(column, weight=1)
        row = tk.Frame(card, bg=theme["surface"])
        row.pack(fill="x", padx=12, pady=(0, 10))
        Button(row, theme, fonts, text=app.t("dev.custom_color"),
               command=self._pick_accent, variant="outline", height=28, radius=7,
               bg_token="surface").pack(side="left", fill="x", expand=True)
        Button(row, theme, fonts, text="↺", command=lambda: app.config.set("accent", ""),
               variant="ghost", height=28, radius=7, bg_token="surface", width=34,
               tooltip=app.t("dev.theme")).pack(side="right", padx=(6, 0))

        self._heading(parent, app.t("dev.font"))
        card = self._card(parent)
        row = self._row(card, app.t("dev.font"))
        Button(row, theme, fonts,
               text=app.config.get("font_family") or app.t("misc.auto"),
               command=self._pick_font, variant="outline", height=26, radius=7,
               bg_token="surface", width=140, font_key="tiny").pack(side="right")
        self._slider_row(card, app.t("dev.font_scale"), "font_scale", 0.8, 1.4, 0.05,
                         lambda v: f"{v:.2f}x", on_change=lambda _v: app.schedule_restyle())
        self._slider_row(card, app.t("dev.radius"), "corner_radius", 0, 24, 1,
                         lambda v: f"{int(v)} px", on_change=lambda _v: app.schedule_restyle())
        self._slider_row(card, app.t("dev.opacity"), "opacity", 0.35, 1.0, 0.01,
                         lambda v: f"{int(v * 100)}%", on_change=lambda _v: app.apply_window_flags())

        self._heading(parent, app.t("dev.appearance"))
        card = self._card(parent)
        self._switch_row(card, app.t("dev.show_ring"), "show_ring",
                         on_change=lambda _v: app.schedule_restyle())
        self._switch_row(card, app.t("dev.show_footer"), "show_footer_stats",
                         on_change=lambda _v: app.schedule_restyle())

    def _section_window(self, parent) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        self._heading(parent, app.t("dev.window"))
        card = self._card(parent)
        self._switch_row(card, app.t("dev.always_on_top"), "always_on_top",
                         on_change=lambda _v: app.apply_window_flags())
        self._switch_row(card, app.t("dev.frameless"), "frameless",
                         on_change=lambda _v: app.rebuild_shell())
        self._switch_row(card, app.t("dev.taskbar"), "show_in_taskbar",
                         hint=app.t("dev.taskbar_hint"),
                         on_change=lambda _v: app.apply_window_flags())
        self._switch_row(card, app.t("dev.snap"), "snap_to_edges")
        self._switch_row(card, app.t("dev.remember_pos"), "remember_position")
        self._slider_row(card, app.t("dev.snap_threshold"), "snap_threshold", 0, 60, 1,
                         lambda v: f"{int(v)} px")
        self._action(card, app.t("dev.reset_pos"), app.center_window, "outline")

        self._heading(parent, app.t("tb.compact"))
        card = self._card(parent)
        self._switch_row(card, app.t("tb.compact"), "compact",
                         on_change=lambda _v: app.schedule_restyle())

        # --- shortcuts and start-up ----------------------------------
        self._heading(parent, app.t("dev.startup"))
        card = self._card(parent)
        if not shortcuts.is_supported():
            tk.Label(card, text=app.t("dev.shortcut_unsupported"), bg=theme["surface"],
                     fg=theme["text_faint"], font=fonts["tiny"], anchor="w",
                     justify="left", wraplength=290).pack(fill="x", padx=12, pady=10)
        else:
            desktop = self._row(card, app.t("dev.desktop_shortcut"),
                                str(shortcuts.desktop_shortcut_path() or ""))
            Switch(desktop, theme, fonts, value=shortcuts.has_desktop_shortcut(),
                   on_change=lambda v: self._set_shortcut(shortcuts.set_desktop_shortcut, v),
                   bg_token="surface").pack(side="right")

            startup = self._row(card, app.t("dev.startup_shortcut"),
                                str(shortcuts.startup_shortcut_path() or ""))
            Switch(startup, theme, fonts, value=shortcuts.has_startup_shortcut(),
                   on_change=lambda v: self._set_shortcut(shortcuts.set_startup_shortcut, v),
                   bg_token="surface").pack(side="right")

    # -- case types (AHT) ---------------------------------------------
    def _section_cases(self, parent) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        self._heading(parent, app.t("dev.cases"),
                      "AHT: mm:ss  ·  5 = 5 min  ·  1:30:00 = 1 h 30 min")
        cases = app.config.get("case_types", [])
        for index, case in enumerate(cases):
            self._case_card(parent, case, index, len(cases))
        Button(parent, theme, fonts, text="+  " + app.t("dev.add_case"),
               command=self._add_case, variant="outline", height=34, radius=9,
               bg_token="bg").pack(fill="x", padx=12, pady=(8, 14))

    def _case_card(self, parent, case: dict, index: int, total: int) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        card = self._card(parent, pady=5)

        top = tk.Frame(card, bg=theme["surface"])
        top.pack(fill="x", padx=10, pady=(10, 4))
        _ColorDot(top, app, case.get("color", theme["accent"]), selected=False, size=18,
                  command=lambda: self._pick_case_color(case)).pack(side="left", padx=(0, 8))
        name_entry = self._entry(top, case.get("name", ""),
                                 lambda value, c=case: self._commit_case(c, "name", value),
                                 width=14, font_key="small_bold")
        name_entry.pack(side="left", fill="x", expand=True, ipady=3)
        Switch(top, theme, fonts, value=case.get("enabled", True),
               on_change=lambda v, c=case: self._commit_case(c, "enabled", v),
               bg_token="surface").pack(side="right", padx=(8, 0))

        bottom = tk.Frame(card, bg=theme["surface"])
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(bottom, text=app.t("dev.target"), bg=theme["surface"],
                 fg=theme["text_faint"], font=fonts["tiny"]).pack(side="left")
        target_entry = self._entry(
            bottom, format_duration(case.get("target_s", 0)),
            lambda value, c=case: self._commit_target(c, value), width=7, font_key="mono")
        target_entry.pack(side="left", padx=6, ipady=3)

        Button(bottom, theme, fonts, text="×", command=lambda c=case: self._delete_case(c),
               variant="ghost", height=24, radius=6, bg_token="surface", width=28,
               font_key="tiny", tooltip=app.t("dev.delete")).pack(side="right")
        Button(bottom, theme, fonts, text="▼",
               command=lambda i=index: self._move("case_types", i, 1),
               variant="ghost", height=24, radius=6, bg_token="surface", width=26,
               font_key="tiny", tooltip=app.t("dev.move_down")).pack(side="right")
        Button(bottom, theme, fonts, text="▲",
               command=lambda i=index: self._move("case_types", i, -1),
               variant="ghost", height=24, radius=6, bg_token="surface", width=26,
               font_key="tiny", tooltip=app.t("dev.move_up")).pack(side="right")

    # -- checklist -----------------------------------------------------
    def _section_checklist(self, parent) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        self._heading(parent, app.t("dev.checklist"))
        items = app.config.get("checklist", [])
        for index, item in enumerate(items):
            self._check_card(parent, item, index, len(items))
        Button(parent, theme, fonts, text="+  " + app.t("dev.add_check"),
               command=self._add_check, variant="outline", height=34, radius=9,
               bg_token="bg").pack(fill="x", padx=12, pady=(8, 14))

    def _check_card(self, parent, item: dict, index: int, total: int) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        card = self._card(parent, pady=5)

        top = tk.Frame(card, bg=theme["surface"])
        top.pack(fill="x", padx=10, pady=(10, 4))
        label_entry = self._entry(top, item.get("label", ""),
                                  lambda value, i=item: self._commit_check(i, "label", value),
                                  width=18, font_key="small_bold")
        label_entry.pack(side="left", fill="x", expand=True, ipady=3)
        Switch(top, theme, fonts, value=item.get("enabled", True),
               on_change=lambda v, i=item: self._commit_check(i, "enabled", v),
               bg_token="surface").pack(side="right", padx=(8, 0))

        hint_entry = self._entry(card, item.get("hint", ""),
                                 lambda value, i=item: self._commit_check(i, "hint", value),
                                 width=30, font_key="tiny")
        hint_entry.pack(fill="x", padx=10, ipady=3)

        # Applicability chips: an item can be required for some case types
        # only (Evidence Adherence does not apply to a Voice or Text chat).
        applies = tk.Frame(card, bg=theme["surface"])
        applies.pack(fill="x", padx=10, pady=(8, 0))
        selected = list(item.get("applies_to") or [])
        tk.Label(applies, text=app.t("dev.applies_to"), bg=theme["surface"],
                 fg=theme["text_faint"], font=fonts["tiny"], anchor="w").pack(
            side="left", padx=(0, 6))
        chips = tk.Frame(card, bg=theme["surface"])
        chips.pack(fill="x", padx=10, pady=(2, 0))
        Button(chips, theme, fonts, text=app.t("dev.applies_all"),
               command=lambda i=item: self._commit_check(i, "applies_to", []),
               variant="primary" if not selected else "soft",
               height=22, radius=6, bg_token="surface", font_key="tiny",
               width=fonts.measure(app.t("dev.applies_all"), "tiny") + 16).pack(
            side="left", padx=(0, 4), pady=2)
        for case in app.config.get("case_types", []):
            on = case["id"] in selected
            Button(chips, theme, fonts, text=case["name"][:10],
                   command=lambda i=item, c=case["id"]: self._toggle_applies(i, c),
                   variant="primary" if on else "soft", height=22, radius=6,
                   bg_token="surface", font_key="tiny",
                   accent=case.get("color") if on else None,
                   width=fonts.measure(case["name"][:10], "tiny") + 16).pack(
                side="left", padx=2, pady=2)

        bottom = tk.Frame(card, bg=theme["surface"])
        bottom.pack(fill="x", padx=10, pady=(6, 10))
        tk.Label(bottom, text=app.t("dev.hint"), bg=theme["surface"],
                 fg=theme["text_faint"], font=fonts["tiny"]).pack(side="left")
        Button(bottom, theme, fonts, text="×", command=lambda i=item: self._delete_check(i),
               variant="ghost", height=24, radius=6, bg_token="surface", width=28,
               font_key="tiny", tooltip=app.t("dev.delete")).pack(side="right")
        Button(bottom, theme, fonts, text="▼",
               command=lambda i=index: self._move("checklist", i, 1),
               variant="ghost", height=24, radius=6, bg_token="surface", width=26,
               font_key="tiny", tooltip=app.t("dev.move_down")).pack(side="right")
        Button(bottom, theme, fonts, text="▲",
               command=lambda i=index: self._move("checklist", i, -1),
               variant="ghost", height=24, radius=6, bg_token="surface", width=26,
               font_key="tiny", tooltip=app.t("dev.move_up")).pack(side="right")

    # -- behaviour -----------------------------------------------------
    def _section_behavior(self, parent) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        self._heading(parent, app.t("dev.behavior"))
        card = self._card(parent)
        self._switch_row(card, app.t("dev.auto_start"), "auto_start_on_select")
        self._switch_row(card, app.t("dev.confirm_reset"), "confirm_reset")
        self._switch_row(card, app.t("dev.require_all"), "require_all_checks",
                         on_change=lambda _v: app.refresh_views())
        self._switch_row(card, app.t("dev.count_paused"), "count_paused_time")

        self._heading(parent, app.t("dev.alert_over"))
        card = self._card(parent)
        self._slider_row(card, app.t("dev.warn_pct"), "warn_at_pct", 10, 100, 5,
                         lambda v: f"{int(v)}%")
        self._switch_row(card, app.t("dev.prealert"), "prealert_enabled")
        self._slider_row(card, app.t("dev.prealert_seconds"), "prealert_seconds",
                         0, 60, 1,
                         lambda v: (app.t("misc.none") if v <= 0 else f"{int(v)} s"))
        self._switch_row(card, app.t("dev.alert_over"), "alert_on_over")
        self._switch_row(card, app.t("dev.sound"), "sound_enabled")
        self._slider_row(card, app.t("dev.alert_repeats"), "alert_repeats", 1, 5, 1,
                         lambda v: f"{int(v)}x")
        # Hearing the alert should not require waiting out a whole case.
        self._action(card, app.t("dev.test_prealert"),
                     lambda: app.play_alert("prealert", force=True), "outline")
        self._action(card, app.t("dev.test_over"),
                     lambda: app.play_alert("over", force=True), "outline")
        if not alerts.available():
            tk.Label(card, text=app.t("dev.no_audio"), bg=theme["surface"],
                     fg=theme["text_faint"], font=fonts["tiny"], anchor="w",
                     justify="left", wraplength=290).pack(fill="x", padx=12,
                                                          pady=(4, 10))

        self._heading(parent, app.t("dev.adaptive"),
                      "The timer target tracks this week's average for the case "
                      "type, so a slow case makes the next few ask for a little "
                      "less. Turn it off to always use the configured target.")
        card = self._card(parent)
        self._switch_row(card, app.t("dev.adaptive"), "adaptive_target",
                         on_change=lambda _v: app.apply_adaptive_target())
        self._slider_row(card, app.t("dev.adaptive_cases"), "adaptive_recovery_cases",
                         1, 50, 1,
                         lambda v: f"{int(v)} {app.t('misc.cases')}",
                         on_change=lambda _v: app.apply_adaptive_target())
        self._slider_row(card, app.t("dev.adaptive_min"), "adaptive_min_factor",
                         0.2, 1.0, 0.05, lambda v: f"{int(v * 100)}%",
                         on_change=lambda _v: app.apply_adaptive_target())
        self._slider_row(card, app.t("dev.adaptive_max"), "adaptive_max_factor",
                         1.0, 2.0, 0.05, lambda v: f"{int(v * 100)}%",
                         on_change=lambda _v: app.apply_adaptive_target())
        row = self._row(card, app.t("dev.week_start"))
        Button(row, theme, fonts,
               text="Sunday" if app.config.get("week_starts_on") == "sunday" else "Monday",
               command=self._toggle_week_start, variant="outline", height=26,
               radius=7, bg_token="surface", width=90, font_key="tiny").pack(side="right")

    # -- data & privacy ------------------------------------------------
    def _section_data(self, parent) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts

        self._heading(parent, app.t("dev.data"), app.t("dev.privacy_note"))
        card = self._card(parent)
        self._switch_row(card, app.t("dev.history_enabled"), "history_enabled",
                         on_change=app.set_history_enabled)
        self._slider_row(card, app.t("dev.retention"), "history_retention_days", 0, 365, 1,
                         lambda v: (app.t("misc.none") if v <= 0
                                    else f"{int(v)} {app.t('misc.days')}"))

        self._heading(parent, app.t("dev.storage"))
        card = self._card(parent)
        tk.Label(card, text=str(paths.data_dir()), bg=theme["surface"],
                 fg=theme["text_faint"], font=fonts["tiny"], anchor="w", justify="left",
                 wraplength=290).pack(fill="x", padx=12, pady=(10, 4))
        row = self._row(card, app.t("dev.portable"), str(paths.portable_marker_path()))
        Switch(row, theme, fonts, value=paths.is_portable(),
               on_change=self._toggle_portable, bg_token="surface").pack(side="right")
        self._action(card, app.t("dev.undo_last"), app.undo_last_case, "outline")
        self._action(card, app.t("dev.open_folder"), self._open_folder, "outline")
        self._action(card, app.t("dev.export_csv"), self._export_csv, "outline")
        self._action(card, app.t("dev.export_settings"), self._export_settings, "outline")
        self._action(card, app.t("dev.import_settings"), self._import_settings, "outline")

        self._heading(parent, app.t("dev.wipe"))
        card = self._card(parent)
        self._action(card, app.t("dev.reset_settings"), self._reset_settings, "danger")
        self._action(card, app.t("dev.wipe"), self._wipe_all, "danger")
        tk.Frame(parent, bg=theme["bg"], height=12).pack(fill="x")

    # -- statistics ----------------------------------------------------
    def _section_stats(self, parent) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        if not app.config.get("history_enabled", True):
            self._heading(parent, app.t("dev.stats"), app.t("footer.history_off"))
            return

        self._week_panel(parent)

        for window_days, label_key in ((1, "dev.stats_today"),
                                       (None, "dev.stats_all")):
            stats = app.history.stats(window_days=window_days)
            self._heading(parent, app.t(label_key))
            card = self._card(parent)
            if not stats["count"]:
                tk.Label(card, text=app.t("dev.no_history"), bg=theme["surface"],
                         fg=theme["text_faint"], font=fonts["small"], anchor="w").pack(
                    fill="x", padx=12, pady=10)
                continue
            grid = tk.Frame(card, bg=theme["surface"])
            grid.pack(fill="x", padx=10, pady=10)
            metrics = [
                (app.t("dev.stats_cases"), str(stats["count"]), theme["text"]),
                (app.t("dev.stats_avg"), format_duration(stats["avg_s"]), theme["text"]),
                (app.t("dev.stats_within"), f"{stats['within_pct']:.0f}%",
                 theme["ok"] if stats["within_pct"] >= 80 else theme["warn"]),
                (app.t("dev.stats_clean"), f"{stats['clean_pct']:.0f}%",
                 theme["ok"] if stats["clean_pct"] >= 80 else theme["warn"]),
            ]
            for index, (label, value, color) in enumerate(metrics):
                cell = tk.Frame(grid, bg=theme["surface"])
                cell.grid(row=index // 2, column=index % 2, sticky="ew", padx=4, pady=4)
                tk.Label(cell, text=value, bg=theme["surface"], fg=color,
                         font=fonts["h1"], anchor="w").pack(fill="x")
                tk.Label(cell, text=label, bg=theme["surface"], fg=theme["text_faint"],
                         font=fonts["tiny"], anchor="w").pack(fill="x")
            for column in range(2):
                grid.grid_columnconfigure(column, weight=1, uniform="stat")

            if window_days is None and stats["by_case"]:
                for name, bucket in sorted(stats["by_case"].items(),
                                           key=lambda kv: -kv[1]["count"]):
                    line = tk.Frame(card, bg=theme["surface"])
                    line.pack(fill="x", padx=12, pady=2)
                    tk.Label(line, text=name, bg=theme["surface"], fg=theme["text_dim"],
                             font=fonts["small"], anchor="w").pack(side="left")
                    tk.Label(line, text=f"{bucket['count']}  ·  {format_duration(bucket['avg_s'])}",
                             bg=theme["surface"], fg=theme["text_faint"],
                             font=fonts["tiny"]).pack(side="right")
                tk.Frame(card, bg=theme["surface"], height=8).pack(fill="x")

            if window_days is None and stats["misses"]:
                self._heading(parent, app.t("dev.stats_misses"))
                miss_card = self._card(parent)
                labels = {item["id"]: item["label"] for item in app.config.get("checklist", [])}
                worst = sorted(stats["misses"].items(), key=lambda kv: -kv[1])[:6]
                top_count = max(count for _cid, count in worst) or 1
                for check_id, count in worst:
                    line = tk.Frame(miss_card, bg=theme["surface"])
                    line.pack(fill="x", padx=12, pady=4)
                    tk.Label(line, text=labels.get(check_id, check_id), bg=theme["surface"],
                             fg=theme["text_dim"], font=fonts["small"], anchor="w").pack(side="left")
                    tk.Label(line, text=str(count), bg=theme["surface"], fg=theme["danger"],
                             font=fonts["small_bold"]).pack(side="right")
                    meter = tk.Canvas(miss_card, height=4, bg=theme["surface"],
                                      highlightthickness=0, bd=0)
                    meter.pack(fill="x", padx=12, pady=(0, 4))
                    meter.update_idletasks()
                    meter.bind("<Configure>", lambda e, c=count, m=meter, tc=top_count:
                               self._paint_meter(m, c / float(tc)))
                tk.Frame(miss_card, bg=theme["surface"], height=6).pack(fill="x")

        self._action(self._card(parent), app.t("dev.export_csv"), self._export_csv, "outline")
        tk.Frame(parent, bg=theme["bg"], height=12).pack(fill="x")

    def _week_panel(self, parent) -> None:
        """This week's AHT per case type, and what it takes to get on target.

        For each type: how many cases, the running average against target, and
        the recovery plan - how many more cases at what AHT to pull the weekly
        average back. That last part is the number an agent can actually act
        on mid-shift.
        """
        app = self.app
        theme, fonts = app.theme, app.fonts
        self._heading(parent, app.t("dev.week"))

        plan = app.weekly_plan()
        active = [c for c in app.config.get("case_types", []) if c.get("enabled", True)]
        if not any(plan.get(c["id"], {}).get("count") for c in active):
            card = self._card(parent)
            tk.Label(card, text=app.t("dev.week_no_data"), bg=theme["surface"],
                     fg=theme["text_faint"], font=fonts["small"], anchor="w").pack(
                fill="x", padx=12, pady=10)
            return

        for case in active:
            entry = plan.get(case["id"])
            if not entry:
                continue
            card = self._card(parent, pady=5)

            # Header: name, count, average vs target.
            head = tk.Frame(card, bg=theme["surface"])
            head.pack(fill="x", padx=12, pady=(10, 2))
            dot = tk.Canvas(head, width=10, height=10, bg=theme["surface"],
                            highlightthickness=0, bd=0)
            dot.pack(side="left", padx=(0, 6))
            dot.create_oval(1, 1, 9, 9, fill=case.get("color", theme["accent"]), outline="")
            tk.Label(head, text=case["name"], bg=theme["surface"], fg=theme["text"],
                     font=fonts["small_bold"], anchor="w").pack(side="left")
            tk.Label(head, text=f"{entry['count']} {app.t('misc.cases')}",
                     bg=theme["surface"], fg=theme["text_faint"],
                     font=fonts["tiny"]).pack(side="right")

            if not entry["count"]:
                tk.Label(card, text=app.t("dev.week_no_data"), bg=theme["surface"],
                         fg=theme["text_faint"], font=fonts["tiny"], anchor="w").pack(
                    fill="x", padx=12, pady=(0, 10))
                continue

            # Average against target, with the surplus/deficit spelled out.
            debt = entry["debt_s"]
            if debt > 0:
                state_text = f"{app.t('dev.over_by')} {format_duration(debt)}"
                state_color = theme["danger"]
            elif debt < 0:
                state_text = f"{app.t('dev.under_by')} {format_duration(-debt)}"
                state_color = theme["ok"]
            else:
                state_text = app.t("dev.on_track")
                state_color = theme["ok"]

            line = tk.Frame(card, bg=theme["surface"])
            line.pack(fill="x", padx=12, pady=(0, 2))
            tk.Label(line, text=format_duration(entry["avg_s"]), bg=theme["surface"],
                     fg=state_color, font=fonts["h1"], anchor="w").pack(side="left")
            tk.Label(line, text=f"  /  {format_duration(entry['target_s'])}",
                     bg=theme["surface"], fg=theme["text_faint"],
                     font=fonts["small"]).pack(side="left")
            tk.Label(line, text=state_text, bg=theme["surface"], fg=state_color,
                     font=fonts["tiny_bold"]).pack(side="right")

            # A bar showing the average against the target.
            meter = tk.Canvas(card, height=5, bg=theme["surface"],
                              highlightthickness=0, bd=0)
            meter.pack(fill="x", padx=12, pady=(2, 6))
            ratio = (entry["avg_s"] / float(entry["target_s"])) if entry["target_s"] else 0
            meter.bind("<Configure>", lambda e, m=meter, r=ratio, c=state_color:
                       self._paint_target_meter(m, r, c))

            # The recovery plan.
            if debt > 0 and entry["target_s"]:
                tk.Label(card, text=app.t("dev.week_plan"), bg=theme["surface"],
                         fg=theme["text_faint"], font=fonts["tiny_bold"],
                         anchor="w").pack(fill="x", padx=12, pady=(2, 2))
                for projection in entry["projections"]:
                    row = tk.Frame(card, bg=theme["surface"])
                    row.pack(fill="x", padx=12, pady=1)
                    tk.Label(row, text=app.t("dev.next_cases", n=projection["cases"]),
                             bg=theme["surface"], fg=theme["text_dim"],
                             font=fonts["tiny"], anchor="w").pack(side="left")
                    if projection["feasible"]:
                        text, color = format_duration(projection["required_s"]), theme["text"]
                    else:
                        text = app.t("dev.not_feasible", n=projection["cases"])
                        color = theme["text_faint"]
                    tk.Label(row, text=text, bg=theme["surface"], fg=color,
                             font=fonts["tiny_bold"]).pack(side="right")
                if entry["cases_at_floor"]:
                    floor = int(round(entry["target_s"]
                                      * float(app.config.get("adaptive_min_factor", 0.6))))
                    need = entry["cases_at_floor"]
                    key = "dev.need_cases_one" if need == 1 else "dev.need_cases"
                    tk.Label(card, text=app.t(key, n=need, aht=format_duration(floor)),
                             bg=theme["surface"], fg=theme["warn"], font=fonts["tiny"],
                             anchor="w", justify="left", wraplength=270).pack(
                        fill="x", padx=12, pady=(4, 0))

            # What the timer will actually ask for next.
            if app.config.get("adaptive_target", True):
                tk.Label(card,
                         text=(f"{app.t('user.adaptive')}: "
                               f"{format_duration(entry['adaptive_target_s'])}"),
                         bg=theme["surface"], fg=theme["accent"], font=fonts["tiny_bold"],
                         anchor="w").pack(fill="x", padx=12, pady=(6, 0))
            tk.Frame(card, bg=theme["surface"], height=8).pack(fill="x")

    def _paint_target_meter(self, canvas: tk.Canvas, ratio: float, color: str) -> None:
        """Bar of the weekly average against target; the target sits at 75%."""
        canvas.delete("all")
        width = canvas.winfo_width()
        if width <= 1:
            return
        theme = self.app.theme
        mark = width * 0.75
        draw_round_rect(canvas, 0, 0, width, 5, 2.5, fill=theme["track"])
        filled = max(2.0, min(float(width), mark * ratio))
        draw_round_rect(canvas, 0, 0, filled, 5, 2.5, fill=color)
        canvas.create_line(mark, -1, mark, 6, fill=theme["text_dim"], width=1)

    def _paint_meter(self, canvas: tk.Canvas, ratio: float) -> None:
        canvas.delete("all")
        width = canvas.winfo_width()
        if width <= 1:
            return
        theme = self.app.theme
        draw_round_rect(canvas, 0, 0, width, 4, 2, fill=theme["track"])
        draw_round_rect(canvas, 0, 0, max(2, width * ratio), 4, 2, fill=theme["danger"])

    # -- about ---------------------------------------------------------
    def _section_about(self, parent) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts
        self._heading(parent, app.t("dev.about"))
        card = self._card(parent)
        tk.Label(card, text="CheckMod", bg=theme["surface"], fg=theme["text"],
                 font=fonts["h1"], anchor="w").pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(card, text=app.t("app.tagline"), bg=theme["surface"], fg=theme["text_dim"],
                 font=fonts["small"], anchor="w").pack(fill="x", padx=12)
        tk.Label(card, text=f"{app.t('misc.version')} {__version__}", bg=theme["surface"],
                 fg=theme["text_faint"], font=fonts["tiny"], anchor="w").pack(
            fill="x", padx=12, pady=(6, 0))
        tk.Label(card, text=f"{app.t('misc.created_by')} {__author__}",
                 bg=theme["surface"], fg=theme["text_faint"], font=fonts["tiny"],
                 anchor="w").pack(fill="x", padx=12, pady=(0, 12))

        self._action(card, app.t("tb.help"), app.show_tutorial, "primary")

        self._heading(parent, app.t("misc.shortcuts"))
        card = self._card(parent)
        for keys, description in app.shortcut_help():
            line = tk.Frame(card, bg=theme["surface"])
            line.pack(fill="x", padx=12, pady=3)
            tk.Label(line, text=keys, bg=theme["surface"], fg=theme["accent"],
                     font=fonts["mono"], anchor="w", width=12).pack(side="left")
            tk.Label(line, text=description, bg=theme["surface"], fg=theme["text_dim"],
                     font=fonts["tiny"], anchor="w", justify="left",
                     wraplength=200).pack(side="left", fill="x", expand=True)
        tk.Frame(card, bg=theme["surface"], height=8).pack(fill="x")

        self._heading(parent, app.t("dev.data"))
        card = self._card(parent)
        tk.Label(card, text=app.t("dev.privacy_note"), bg=theme["surface"],
                 fg=theme["text_faint"], font=fonts["tiny"], anchor="w", justify="left",
                 wraplength=290).pack(fill="x", padx=12, pady=10)
        tk.Frame(parent, bg=theme["bg"], height=12).pack(fill="x")

    # ==================================================================
    # Actions
    # ==================================================================
    def _set_shortcut(self, setter, enabled: bool) -> None:
        """Create/remove a shortcut and report a failure rather than lying."""
        if not setter(enabled):
            dialogs.alert(self.app, self.app.t("dlg.shortcut_failed"))
        self.refresh()

    def _toggle_week_start(self) -> None:
        """Flip the week boundary between Sunday and Monday."""
        current = self.app.config.get("week_starts_on", "sunday")
        self.app.config.set("week_starts_on", "monday" if current == "sunday" else "sunday")
        self.app.apply_adaptive_target()
        self.refresh()

    def _pick_accent(self) -> None:
        color = dialogs.pick_color(self.app, self.app.theme["accent"])
        if color:
            self.app.config.set("accent", color)

    def _pick_font(self) -> None:
        families = available_families()
        preferred = [f for f in PREFERRED_FAMILIES if f in families]
        options = [("", self.app.t("misc.auto"))] + [(f, f) for f in preferred[:8]]
        choice = dialogs.pick(self.app, self.app.t("dev.font"), options,
                              self.app.config.get("font_family", ""))
        if choice is not None:
            self.app.config.set("font_family", choice)
            self.app.schedule_restyle()

    def _pick_case_color(self, case: dict) -> None:
        color = dialogs.pick_color(self.app, case.get("color", "#5B8CFF"))
        if color:
            self._commit_case(case, "color", color)

    # -- case / checklist mutation ------------------------------------
    def _commit_case(self, case: dict, field: str, value) -> None:
        """Write one field of one case type back into the settings list."""
        cases = [dict(c) for c in self.app.config.get("case_types", [])]
        for entry in cases:
            if entry["id"] == case["id"]:
                entry[field] = value
                break
        self.app.config.set("case_types", cases)
        self.app.refresh_views()

    def _commit_target(self, case: dict, text: str) -> None:
        seconds = parse_duration(text)
        if seconds is None or seconds <= 0:
            self.refresh()
            return
        self._commit_case(case, "target_s", seconds)
        self.app.sync_session_target()

    def _commit_check(self, item: dict, field: str, value) -> None:
        items = [dict(i) for i in self.app.config.get("checklist", [])]
        for entry in items:
            if entry["id"] == item["id"]:
                entry[field] = value
                break
        self.app.config.set("checklist", items)
        self.app.sync_checklist()

    def _add_case(self) -> None:
        name = dialogs.prompt(self.app, self.app.t("dev.add_case"), "", self.app.t("dev.name"))
        if not name:
            return
        cases = [dict(c) for c in self.app.config.get("case_types", [])]
        palette = theme_mod.ACCENT_SWATCHES
        cases.append({
            "id": new_id("case"), "name": name.strip()[:40], "target_s": DEFAULT_TARGET_S,
            "color": palette[len(cases) % len(palette)], "enabled": True,
        })
        self.app.config.set("case_types", cases)
        self.app.refresh_views()
        self.refresh()

    def _delete_case(self, case: dict) -> None:
        if not dialogs.confirm(self.app, self.app.t("dlg.delete_case_q", name=case.get("name", "")),
                               danger=True):
            return
        cases = [c for c in self.app.config.get("case_types", []) if c["id"] != case["id"]]
        self.app.config.set("case_types", cases)
        self.app.refresh_views()
        self.refresh()

    def _toggle_applies(self, item: dict, case_id: str) -> None:
        """Add or remove one case type from an item's applicability list."""
        current = list(item.get("applies_to") or [])
        if case_id in current:
            current.remove(case_id)
        else:
            current.append(case_id)
        self._commit_check(item, "applies_to", current)
        self.refresh()

    def _add_check(self) -> None:
        label = dialogs.prompt(self.app, self.app.t("dev.add_check"), "", self.app.t("dev.name"))
        if not label:
            return
        items = [dict(i) for i in self.app.config.get("checklist", [])]
        items.append({"id": new_id("chk"), "label": label.strip()[:60], "hint": "",
                      "enabled": True, "applies_to": []})
        self.app.config.set("checklist", items)
        self.app.sync_checklist()
        self.refresh()

    def _delete_check(self, item: dict) -> None:
        if not dialogs.confirm(self.app, self.app.t("dlg.delete_check_q", name=item.get("label", "")),
                               danger=True):
            return
        items = [i for i in self.app.config.get("checklist", []) if i["id"] != item["id"]]
        self.app.config.set("checklist", items)
        self.app.sync_checklist()
        self.refresh()

    def _move(self, key: str, index: int, delta: int) -> None:
        """Reorder a case type or checklist item."""
        items = [dict(i) for i in self.app.config.get(key, [])]
        target = index + delta
        if not (0 <= index < len(items) and 0 <= target < len(items)):
            return
        items[index], items[target] = items[target], items[index]
        self.app.config.set(key, items)
        self.app.refresh_views()
        self.refresh()

    # -- data actions ---------------------------------------------------
    def _open_folder(self) -> None:
        """Reveal the data folder in the OS file manager."""
        folder = str(paths.data_dir())
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # noqa: S606 - documented, user-initiated
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            dialogs.alert(self.app, folder)

    def _ask_save_path(self, default_name: str, extension: str):
        from tkinter import filedialog

        try:
            return filedialog.asksaveasfilename(
                parent=self.app.root, initialfile=default_name, defaultextension=extension,
                filetypes=[(extension.upper().lstrip("."), f"*{extension}"), ("All", "*.*")])
        except Exception:  # pragma: no cover - headless
            return str(paths.data_dir() / default_name)

    def _export_csv(self) -> None:
        default = f"checkmod-history-{time.strftime('%Y%m%d')}.csv"
        target = self._ask_save_path(default, ".csv")
        if not target:
            return
        labels = {item["id"]: item["label"] for item in self.app.config.get("checklist", [])}
        ok = self.app.history.export_csv(target, labels)
        dialogs.alert(self.app, self.app.t("dlg.saved", path=target) if ok
                      else self.app.t("dlg.failed"))

    def _export_settings(self) -> None:
        target = self._ask_save_path("checkmod-settings.json", ".json")
        if not target:
            return
        ok = self.app.config.export_to(target)
        dialogs.alert(self.app, self.app.t("dlg.saved", path=target) if ok
                      else self.app.t("dlg.failed"))

    def _import_settings(self) -> None:
        from tkinter import filedialog

        try:
            source = filedialog.askopenfilename(
                parent=self.app.root, filetypes=[("JSON", "*.json"), ("All", "*.*")])
        except Exception:  # pragma: no cover
            source = ""
        if not source:
            return
        if self.app.config.import_from(source):
            self.app.schedule_restyle()
        else:
            dialogs.alert(self.app, self.app.t("dlg.failed"))

    def _toggle_portable(self, enabled: bool) -> None:
        """Create/remove the portable marker and report where data now lives.

        Existing settings and history are not moved automatically: the user
        keeps both copies and decides, which is safer than silently relocating
        a folder that may sit on a network share.
        """
        if not paths.enable_portable(enabled):
            dialogs.alert(self.app, self.app.t("dlg.failed"))
        self.app.reload_storage()
        dialogs.alert(self.app, str(paths.data_dir()))
        self.refresh()

    def _reset_settings(self) -> None:
        if dialogs.confirm(self.app, self.app.t("dlg.reset_settings_q"), danger=True):
            self.app.config.reset()
            self.app.schedule_restyle()

    def _wipe_all(self) -> None:
        if not dialogs.confirm(self.app, self.app.t("dlg.wipe_q"), danger=True):
            return
        self.app.history.wipe()
        self.app.config.reset()
        self.app.schedule_restyle()


# ----------------------------------------------------------------------
# Small pickers used by the appearance section
# ----------------------------------------------------------------------
class _ThemeSwatch(tk.Canvas):
    """Miniature preview of a theme preset: background, surface and accent."""

    def __init__(self, parent, app, key: str, palette: dict, selected: bool,
                 command) -> None:
        self.app = app
        self.key = key
        self.palette = palette
        self.selected = selected
        self.command = command
        super().__init__(parent, width=62, height=44, highlightthickness=0, bd=0,
                         bg=app.theme["surface"], cursor="hand2")
        self.bind("<Button-1>", lambda _e: command())
        self.bind("<Configure>", lambda _e: self._paint())
        Tooltip(self, palette.get("label", key))

    def _paint(self) -> None:
        self.delete("all")
        width, height = widget_size(self, 62, 44)
        border = self.app.theme["accent"] if self.selected else self.app.theme["border"]
        draw_round_rect(self, 1, 1, width - 1, height - 1, 7,
                        fill=self.palette["bg"], outline=border,
                        width=2 if self.selected else 1)
        draw_round_rect(self, 7, 8, width - 8, 20, 3, fill=self.palette["surface"])
        draw_round_rect(self, 7, 24, width - 20, 30, 3, fill=self.palette["accent"])
        self.create_text(width / 2, height - 8, text=self.palette.get("label", self.key)[:9],
                         fill=self.palette["text_dim"], font=self.app.fonts["tiny"])


class _ColorDot(tk.Canvas):
    """Round colour swatch used for accents and case-type colours."""

    def __init__(self, parent, app, color: str, selected: bool, command,
                 size: int = 24) -> None:
        self.app = app
        self.color = color
        self.selected = selected
        self.size = size
        super().__init__(parent, width=size, height=size, highlightthickness=0, bd=0,
                         bg=app.theme["surface"], cursor="hand2")
        self.bind("<Button-1>", lambda _e: command())
        self.bind("<Configure>", lambda _e: self._paint())

    def _paint(self) -> None:
        self.delete("all")
        width, height = widget_size(self, self.size, self.size)
        size = min(width, height)
        pad = 2
        self.create_oval(pad, pad, size - pad, size - pad, fill=self.color,
                         outline=self.app.theme["text"] if self.selected else "",
                         width=2 if self.selected else 0)

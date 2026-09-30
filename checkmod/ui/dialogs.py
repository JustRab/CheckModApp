"""Themed modal dialogs.

``tkinter.messagebox`` opens native dialogs that ignore the app's palette and,
worse, can appear *behind* an always-on-top window on some Windows builds.
These replacements are small ``Toplevel`` windows that inherit the current
theme, stay on top, centre on the app and block until answered.
"""

from __future__ import annotations

import tkinter as tk
from typing import List, Optional, Tuple

from ..history import RANGE_KEYS, format_day, range_bounds
from ..session import format_duration
from .primitives import Button


class _Modal(tk.Toplevel):
    """Base class: frameless, top-most, centred on the parent window."""

    def __init__(self, app, width: int = 320, height: int = 170) -> None:
        self.app = app
        super().__init__(app.root)
        self.result = None
        self.withdraw()
        self.wm_overrideredirect(True)
        for attribute, value in (("-topmost", True), ("-alpha", 1.0)):
            try:
                self.wm_attributes(attribute, value)
            except tk.TclError:  # pragma: no cover - platform dependent
                pass
        self.configure(bg=app.theme["border"])
        self.body = tk.Frame(self, bg=app.theme["bg_alt"])
        self.body.pack(fill="both", expand=True, padx=1, pady=1)
        self._place(width, height)
        self.bind("<Escape>", lambda _e: self._close(None))

    def _place(self, width: int, height: int) -> None:
        root = self.app.root
        root.update_idletasks()
        x = root.winfo_x() + max(0, (root.winfo_width() - width) // 2)
        y = root.winfo_y() + max(0, (root.winfo_height() - height) // 3)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(4, min(x, screen_w - width - 4))
        y = max(4, min(y, screen_h - height - 4))
        self.wm_geometry(f"{width}x{height}+{x}+{y}")

    def _close(self, result) -> None:
        self.result = result
        try:
            self.grab_release()
        except tk.TclError:  # pragma: no cover
            pass
        self.destroy()

    def run(self):
        """Show the dialog and block until it is dismissed."""
        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except tk.TclError:  # pragma: no cover - headless
            pass
        self.focus_force()
        self.wait_window(self)
        return self.result


class Confirm(_Modal):
    """Yes/no question with an optional destructive styling."""

    def __init__(self, app, message: str, danger: bool = False,
                 ok_text: str = "", cancel_text: str = "") -> None:
        super().__init__(app, width=340, height=180)
        theme, fonts = app.theme, app.fonts
        tk.Label(self.body, text=message, bg=theme["bg_alt"], fg=theme["text"],
                 font=fonts["body"], wraplength=296, justify="left").pack(
            fill="both", expand=True, padx=22, pady=(24, 12))
        row = tk.Frame(self.body, bg=theme["bg_alt"])
        row.pack(fill="x", padx=18, pady=(0, 18))
        Button(row, theme, fonts, text=cancel_text or app.t("dlg.cancel"),
               command=lambda: self._close(False), variant="soft", height=34,
               bg_token="bg_alt", width=120).pack(side="left", expand=True, fill="x", padx=4)
        Button(row, theme, fonts, text=ok_text or app.t("dlg.confirm"),
               command=lambda: self._close(True),
               variant="danger" if danger else "primary", height=34,
               bg_token="bg_alt", width=120).pack(side="right", expand=True, fill="x", padx=4)


class Alert(_Modal):
    """Single-button notice."""

    def __init__(self, app, message: str) -> None:
        super().__init__(app, width=340, height=170)
        theme, fonts = app.theme, app.fonts
        tk.Label(self.body, text=message, bg=theme["bg_alt"], fg=theme["text"],
                 font=fonts["body"], wraplength=296, justify="left").pack(
            fill="both", expand=True, padx=22, pady=(24, 12))
        Button(self.body, theme, fonts, text=app.t("dlg.ok"),
               command=lambda: self._close(True), variant="primary", height=34,
               bg_token="bg_alt").pack(fill="x", padx=22, pady=(0, 18))


class Prompt(_Modal):
    """Single-line text input, used for names and AHT targets."""

    def __init__(self, app, title: str, initial: str = "", hint: str = "") -> None:
        super().__init__(app, width=340, height=200)
        theme, fonts = app.theme, app.fonts
        tk.Label(self.body, text=title, bg=theme["bg_alt"], fg=theme["text"],
                 font=fonts["body_bold"], anchor="w").pack(
            fill="x", padx=22, pady=(20, 2))
        if hint:
            tk.Label(self.body, text=hint, bg=theme["bg_alt"], fg=theme["text_faint"],
                     font=fonts["tiny"], anchor="w", wraplength=290,
                     justify="left").pack(fill="x", padx=22, pady=(0, 8))
        self.entry = tk.Entry(
            self.body, bg=theme["surface"], fg=theme["text"], insertbackground=theme["text"],
            relief="flat", font=fonts["body"], highlightthickness=1,
            highlightbackground=theme["border"], highlightcolor=theme["accent"],
        )
        self.entry.insert(0, initial)
        self.entry.pack(fill="x", padx=22, ipady=6)
        self.entry.select_range(0, "end")
        self.entry.bind("<Return>", lambda _e: self._accept())

        row = tk.Frame(self.body, bg=theme["bg_alt"])
        row.pack(fill="x", padx=18, pady=18)
        Button(row, theme, fonts, text=app.t("dlg.cancel"),
               command=lambda: self._close(None), variant="soft", height=32,
               bg_token="bg_alt").pack(side="left", expand=True, fill="x", padx=4)
        Button(row, theme, fonts, text=app.t("dlg.ok"), command=self._accept,
               variant="primary", height=32, bg_token="bg_alt").pack(
            side="right", expand=True, fill="x", padx=4)
        self.after(60, self.entry.focus_set)

    def _accept(self) -> None:
        self._close(self.entry.get())


class Picker(_Modal):
    """Vertical list picker used for themes, languages and swatch grids."""

    def __init__(self, app, title: str, options: List[Tuple[str, str]],
                 current: Optional[str] = None) -> None:
        rows = min(len(options), 9)
        super().__init__(app, width=280, height=64 + rows * 34 + 14)
        theme, fonts = app.theme, app.fonts
        tk.Label(self.body, text=title, bg=theme["bg_alt"], fg=theme["text_dim"],
                 font=fonts["small_bold"], anchor="w").pack(fill="x", padx=16, pady=(14, 8))
        holder = tk.Frame(self.body, bg=theme["bg_alt"])
        holder.pack(fill="both", expand=True, padx=10, pady=(0, 12))
        for value, label in options:
            Button(holder, theme, fonts, text=label,
                   command=lambda v=value: self._close(v),
                   variant="primary" if value == current else "soft",
                   height=30, bg_token="bg_alt").pack(fill="x", pady=2)


class SheetPreview(_Modal):
    """What the AHT sheet says, next to what is configured now.

    Nothing is written before this dialog is accepted. Rows that changed are
    shown in the accent colour; rows the sheet did not mention are shown as
    unchanged, and rows the sheet had that no case type matches are listed at
    the end so a renamed package is visible rather than silently ignored.
    """

    #: Rows drawn before the list is truncated, to keep the dialog on screen.
    MAX_ROWS = 9

    def __init__(self, app, rows) -> None:
        shown = list(rows)[:self.MAX_ROWS]
        super().__init__(app, width=360, height=138 + len(shown) * 26)
        theme, fonts = app.theme, app.fonts

        tk.Label(self.body, text=app.t("sheet.preview_title"), bg=theme["bg_alt"],
                 fg=theme["text"], font=fonts["body_bold"], anchor="w").pack(
            fill="x", padx=20, pady=(16, 2))
        tk.Label(self.body, text=app.t("sheet.preview_hint"), bg=theme["bg_alt"],
                 fg=theme["text_faint"], font=fonts["tiny"], anchor="w",
                 wraplength=312, justify="left").pack(fill="x", padx=20, pady=(0, 8))

        table = tk.Frame(self.body, bg=theme["bg_alt"])
        table.pack(fill="both", expand=True, padx=20)
        for row in shown:
            line = tk.Frame(table, bg=theme["bg_alt"])
            line.pack(fill="x", pady=1)
            unknown = bool(row.get("unknown"))
            changed = bool(row.get("changed"))
            name_color = theme["text_faint"] if unknown else theme["text_dim"]
            tk.Label(line, text=row.get("name") or row.get("label", ""),
                     bg=theme["bg_alt"], fg=name_color, font=fonts["small"],
                     anchor="w").pack(side="left")
            if unknown:
                value, color = app.t("sheet.unmatched"), theme["warn"]
            elif changed:
                value = (f"{format_duration(row['current_s'])}"
                         f"  \u2192  {format_duration(row['new_s'])}")
                color = theme["accent"]
            elif row.get("new_s") is None:
                value, color = app.t("sheet.no_row"), theme["text_faint"]
            else:
                value, color = format_duration(row["new_s"]), theme["text_faint"]
            tk.Label(line, text=value, bg=theme["bg_alt"], fg=color,
                     font=fonts["small_bold"] if changed else fonts["small"]).pack(
                side="right")

        if len(rows) > len(shown):
            tk.Label(self.body, text=app.t("sheet.more", n=len(rows) - len(shown)),
                     bg=theme["bg_alt"], fg=theme["text_faint"], font=fonts["tiny"],
                     anchor="w").pack(fill="x", padx=20, pady=(4, 0))

        buttons = tk.Frame(self.body, bg=theme["bg_alt"])
        buttons.pack(fill="x", padx=16, pady=16)
        Button(buttons, theme, fonts, text=app.t("dlg.cancel"),
               command=lambda: self._close(False), variant="soft", height=32,
               bg_token="bg_alt").pack(side="left", expand=True, fill="x", padx=4)
        Button(buttons, theme, fonts, text=app.t("sheet.apply"),
               command=lambda: self._close(True), variant="primary", height=32,
               bg_token="bg_alt").pack(side="right", expand=True, fill="x", padx=4)


class RangeDialog(_Modal):
    """Pick the period a CSV export should cover.

    The presets are what gets asked for in practice (a shift, a week, a
    month); the two date fields are there for "from X to Y" when a manager
    asks for an exact window. Result is ``(since, until, label)`` in epoch
    seconds, with ``None`` for an open bound.
    """

    def __init__(self, app, since_text: str = "", until_text: str = "") -> None:
        presets = [key for key in RANGE_KEYS if key != "custom"]
        rows = (len(presets) + 1) // 2
        super().__init__(app, width=340, height=210 + rows * 32)
        theme, fonts = app.theme, app.fonts

        tk.Label(self.body, text=app.t("range.title"), bg=theme["bg_alt"],
                 fg=theme["text"], font=fonts["body_bold"], anchor="w").pack(
            fill="x", padx=20, pady=(16, 8))

        grid = tk.Frame(self.body, bg=theme["bg_alt"])
        grid.pack(fill="x", padx=16)
        for index, key in enumerate(presets):
            Button(grid, theme, fonts, text=app.t(f"range.{key}"),
                   command=lambda k=key: self._pick(k), variant="soft", height=28,
                   radius=7, bg_token="bg_alt", font_key="tiny", width=10).grid(
                row=index // 2, column=index % 2, sticky="ew", padx=3, pady=3)
        for column in range(2):
            grid.grid_columnconfigure(column, weight=1, uniform="range")

        tk.Label(self.body, text=app.t("range.custom_hint"), bg=theme["bg_alt"],
                 fg=theme["text_faint"], font=fonts["tiny"], anchor="w",
                 wraplength=292, justify="left").pack(fill="x", padx=20, pady=(12, 4))
        fields = tk.Frame(self.body, bg=theme["bg_alt"])
        fields.pack(fill="x", padx=16)
        self.since = self._entry(fields, since_text)
        self.since.pack(side="left", expand=True, fill="x", padx=3)
        tk.Label(fields, text="\u2192", bg=theme["bg_alt"], fg=theme["text_faint"],
                 font=fonts["small"]).pack(side="left")
        self.until = self._entry(fields, until_text)
        self.until.pack(side="left", expand=True, fill="x", padx=3)

        buttons = tk.Frame(self.body, bg=theme["bg_alt"])
        buttons.pack(fill="x", padx=16, pady=14)
        Button(buttons, theme, fonts, text=app.t("dlg.cancel"),
               command=lambda: self._close(None), variant="soft", height=32,
               bg_token="bg_alt").pack(side="left", expand=True, fill="x", padx=4)
        Button(buttons, theme, fonts, text=app.t("range.export"),
               command=lambda: self._pick("custom"), variant="primary", height=32,
               bg_token="bg_alt").pack(side="right", expand=True, fill="x", padx=4)
        self.after(60, self.since.focus_set)

    def _entry(self, parent, initial: str) -> tk.Entry:
        theme, fonts = self.app.theme, self.app.fonts
        entry = tk.Entry(parent, bg=theme["surface"], fg=theme["text"],
                         insertbackground=theme["text"], relief="flat",
                         font=fonts["small"], highlightthickness=1, justify="center",
                         highlightbackground=theme["border"],
                         highlightcolor=theme["accent"])
        if initial:
            entry.insert(0, initial)
        entry.bind("<Return>", lambda _e: self._pick("custom"))
        return entry

    def _pick(self, key: str) -> None:
        since_text = self.since.get()
        until_text = self.until.get()
        since, until = range_bounds(key, starts_on=str(
            self.app.config.get("week_starts_on", "sunday")),
            since_text=since_text, until_text=until_text)
        if key == "custom" and since is None and until is None:
            # Both fields empty or unparsable: say so rather than quietly
            # exporting everything under a "from X to Y" label.
            alert(self.app, self.app.t("range.bad_dates"))
            return
        label = self.app.t(f"range.{key}") if key != "custom" else (
            f"{format_day(since) or '...'}_{format_day(until - 1) if until else '...'}")
        self._close((since, until, label))


# ----------------------------------------------------------------------
# Convenience wrappers
# ----------------------------------------------------------------------
def confirm(app, message: str, danger: bool = False) -> bool:
    """Ask a yes/no question; returns ``True`` when confirmed."""
    return bool(Confirm(app, message, danger=danger).run())


def alert(app, message: str) -> None:
    """Show a notice and wait for acknowledgement."""
    Alert(app, message).run()


def prompt(app, title: str, initial: str = "", hint: str = "") -> Optional[str]:
    """Ask for a line of text; returns ``None`` when cancelled."""
    return Prompt(app, title, initial, hint).run()


def pick(app, title: str, options: List[Tuple[str, str]],
         current: Optional[str] = None) -> Optional[str]:
    """Ask the user to choose one of ``options`` (``(value, label)`` pairs)."""
    return Picker(app, title, options, current).run()


def pick_color(app, initial: str = "#5B8CFF") -> Optional[str]:
    """Open the OS colour chooser, returning ``"#rrggbb"`` or ``None``."""
    try:
        from tkinter import colorchooser

        _rgb, hex_value = colorchooser.askcolor(color=initial, parent=app.root)
        return hex_value
    except Exception:  # pragma: no cover - some minimal Tk builds lack it
        return prompt(app, app.t("dev.custom_color"), initial, "#rrggbb")


def sheet_preview(app, rows) -> bool:
    """Show the sheet's numbers; ``True`` when the user accepts them."""
    return bool(SheetPreview(app, rows).run())


def export_range(app, since_text: str = "", until_text: str = ""):
    """Ask what period to export. ``(since, until, label)`` or ``None``."""
    return RangeDialog(app, since_text, until_text).run()

"""Themed modal dialogs.

``tkinter.messagebox`` opens native dialogs that ignore the app's palette and,
worse, can appear *behind* an always-on-top window on some Windows builds.
These replacements are small ``Toplevel`` windows that inherit the current
theme, stay on top, centre on the app and block until answered.
"""

from __future__ import annotations

import tkinter as tk
from typing import List, Optional, Tuple

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

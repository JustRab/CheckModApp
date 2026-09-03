"""The adherence checklist row.

One row per adherence item (Escalation, Enforcement, Evidence, Comment...).
The whole row is a click target - moderators clear these while reading a
case, so a 40x40 px hit area beats a 13 px native checkbox.

Visual language:

* unchecked - hairline box, dimmed label
* checked   - filled box with a hand-drawn tick, label in full contrast and
  a coloured left rail, so a cleared row is recognisable peripherally
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .primitives import (CanvasWidget, Tooltip, draw_round_rect, ellipsize,
                         widget_size)


class CheckRow(CanvasWidget):
    """A single, clickable checklist item."""

    HEIGHT = 42

    def __init__(self, parent, theme, fonts, item: dict, checked: bool = False,
                 on_toggle: Optional[Callable[[str, bool], None]] = None,
                 radius: int = 10, bg_token: str = "bg") -> None:
        self.item = item
        self.checked = bool(checked)
        self.on_toggle = on_toggle
        self.radius = radius
        self._hover = False
        super().__init__(parent, theme, fonts, height=self.HEIGHT, bg_token=bg_token)
        self.configure(cursor="hand2")
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._tooltip = Tooltip(self, item.get("hint", ""))

    # ------------------------------------------------------------------
    def set_item(self, item: dict) -> None:
        """Swap in a new definition (label/hint edited in Dev Mode)."""
        self.item = item
        self._tooltip.set_text(item.get("hint", ""))
        self._redraw()

    def set_checked(self, checked: bool, notify: bool = False) -> None:
        checked = bool(checked)
        changed = checked != self.checked
        self.checked = checked
        self._redraw()
        if notify and changed and self.on_toggle:
            self.on_toggle(self.item["id"], checked)

    def toggle(self) -> None:
        self.set_checked(not self.checked, notify=True)

    # ------------------------------------------------------------------
    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._redraw()

    def _on_click(self, _event=None) -> None:
        self.toggle()

    # ------------------------------------------------------------------
    def _redraw(self) -> None:
        from .. import theme as theme_mod

        self.delete("all")
        width, height = widget_size(self, 0, self.HEIGHT)
        if width <= 1:
            return
        t = self.theme
        done_color = t["ok"]

        if self.checked:
            fill = theme_mod.mix(done_color, t["surface"], 0.86)
            outline = theme_mod.mix(done_color, t["border"], 0.55)
        elif self._hover:
            fill, outline = t["surface_hi"], t["border"]
        else:
            fill, outline = t["surface"], t["border"]
        draw_round_rect(self, 0.5, 0.5, width - 0.5, height - 0.5, self.radius,
                        fill=fill, outline=outline, width=1.0)

        # Coloured left rail marks a cleared item at a glance.
        if self.checked:
            draw_round_rect(self, 1.5, 6, 4.5, height - 6, 1.5, fill=done_color)

        # Checkbox
        box = 20
        bx1, by1 = 14, (height - box) / 2
        bx2, by2 = bx1 + box, by1 + box
        if self.checked:
            draw_round_rect(self, bx1, by1, bx2, by2, 6, fill=done_color)
            # Hand-drawn tick: reliable everywhere, unlike a font glyph.
            self.create_line(bx1 + 5, by1 + 10, bx1 + 8.5, by1 + 14,
                             bx1 + 15, by1 + 6, fill=theme_mod.readable_on(done_color),
                             width=2.2, capstyle="round", joinstyle="round")
        else:
            draw_round_rect(self, bx1 + 0.5, by1 + 0.5, bx2 - 0.5, by2 - 0.5, 6,
                            fill=t["bg_alt"],
                            outline=t["accent"] if self._hover else t["border"], width=1.4)

        label = self.item.get("label", "")
        max_chars = max(8, int((width - bx2 - 24) / max(5, self.fonts.measure("n", "body"))))
        self.create_text(
            bx2 + 12, height / 2, anchor="w", text=ellipsize(label, max_chars),
            fill=t["text"] if self.checked else t["text_dim"],
            font=self.fonts["body_bold" if self.checked else "body"],
        )

        # Hint affordance on the right when a description exists.
        if self.item.get("hint"):
            self.create_text(width - 12, height / 2, anchor="e", text="i",
                             fill=t["text_faint"], font=self.fonts["tiny_bold"])


class ChecklistPanel(tk.Frame):
    """Stack of :class:`CheckRow` widgets kept in sync with the session."""

    def __init__(self, parent, app) -> None:
        self.app = app
        super().__init__(parent, bg=app.theme["bg"], highlightthickness=0, bd=0)
        self.rows = {}
        self.rebuild()

    def rebuild(self) -> None:
        """Recreate every row from the current configuration."""
        for child in self.winfo_children():
            child.destroy()
        self.rows = {}
        # Only the items that apply to the selected case type: Evidence
        # Adherence is meaningless on a Voice or Text chat.
        items = self.app.config.active_checks(self.app.session.case_id)
        if not items:
            tk.Label(self, text=self.app.t("user.no_checks"), bg=self.app.theme["bg"],
                     fg=self.app.theme["text_faint"], font=self.app.fonts["small"],
                     wraplength=260, justify="left").pack(fill="x", pady=6)
            return
        radius = int(self.app.config.get("corner_radius", 12)) - 2
        for item in items:
            row = CheckRow(
                self, self.app.theme, self.app.fonts, item,
                checked=self.app.session.checks.get(item["id"], False),
                on_toggle=self.app.on_check_toggled,
                radius=max(4, radius), bg_token="bg",
            )
            row.pack(fill="x", pady=3)
            self.rows[item["id"]] = row

    def sync(self) -> None:
        """Push session state into the rows without rebuilding them."""
        for check_id, row in self.rows.items():
            row.set_checked(self.app.session.checks.get(check_id, False))

    def restyle(self, theme, fonts) -> None:
        self.configure(bg=theme["bg"])
        for row in self.rows.values():
            row.restyle(theme, fonts)

"""In-app tutorial.

Shown automatically on first run and reachable at any time from the "?" in
the title bar or from Dev Mode > About. It is an overlay rather than a
separate window so it inherits the theme, cannot be lost behind another
application, and works the same in the compact layout.

Each step pairs a short instruction with a hand-drawn illustration of the
part of the interface being described - no screenshots to keep in sync and
no image files to ship.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .primitives import Button, draw_round_rect

#: (title key, body key, illustration name) for each step, in order.
STEPS = [
    ("tut.1.title", "tut.1.body", "window"),
    ("tut.2.title", "tut.2.body", "cases"),
    ("tut.3.title", "tut.3.body", "timer"),
    ("tut.4.title", "tut.4.body", "checks"),
    ("tut.5.title", "tut.5.body", "complete"),
    ("tut.6.title", "tut.6.body", "dev"),
    ("tut.7.title", "tut.7.body", "privacy"),
]


class Tutorial(tk.Frame):
    """Paged walkthrough overlay."""

    def __init__(self, parent, app, on_close: Optional[Callable[[], None]] = None) -> None:
        self.app = app
        self.on_close = on_close
        self.index = 0
        super().__init__(parent, bg=app.theme["bg"], highlightthickness=0, bd=0)
        self._build()

    def _build(self) -> None:
        app = self.app
        theme, fonts = app.theme, app.fonts

        header = tk.Frame(self, bg=theme["bg_alt"], height=30)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=app.t("tut.title"), bg=theme["bg_alt"], fg=theme["text_dim"],
                 font=fonts["small_bold"]).pack(side="left", padx=12)
        Button(header, theme, fonts, text="×", command=self.close, variant="icon",
               height=22, radius=6, bg_token="bg_alt", width=24,
               font_key="glyph").pack(side="right", padx=6)

        body = tk.Frame(self, bg=theme["bg"])
        body.pack(fill="both", expand=True, padx=18, pady=10)

        # Spacers above and below keep the step centred in the window,
        # whatever height the user has resized it to.
        tk.Frame(body, bg=theme["bg"]).pack(fill="both", expand=True)

        self.canvas = tk.Canvas(body, height=150, bg=theme["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="x", pady=(4, 14))
        self.canvas.bind("<Configure>", lambda _e: self._paint_illustration())

        self.title_label = tk.Label(body, text="", bg=theme["bg"], fg=theme["text"],
                                    font=fonts["h1"], anchor="w", justify="left",
                                    wraplength=280)
        self.title_label.pack(fill="x")
        self.body_label = tk.Label(body, text="", bg=theme["bg"], fg=theme["text_dim"],
                                   font=fonts["small"], anchor="w", justify="left",
                                   wraplength=280)
        self.body_label.pack(fill="x", pady=(6, 0))

        tk.Frame(body, bg=theme["bg"]).pack(fill="both", expand=True)

        self.dots = tk.Canvas(self, height=16, bg=theme["bg"], highlightthickness=0, bd=0)
        self.dots.pack(fill="x", pady=(0, 4))
        self.dots.bind("<Configure>", lambda _e: self._paint_dots())

        footer = tk.Frame(self, bg=theme["bg"])
        footer.pack(fill="x", padx=16, pady=(0, 14))
        self.btn_skip = Button(footer, theme, fonts, text=app.t("tut.skip"),
                               command=self.close, variant="ghost", height=34, radius=8,
                               bg_token="bg", width=70, font_key="small")
        self.btn_skip.pack(side="left")
        self.btn_next = Button(footer, theme, fonts, text=app.t("tut.next"),
                               command=self.next_step, variant="primary", height=34,
                               radius=8, bg_token="bg", width=110)
        self.btn_next.pack(side="right")
        self.btn_prev = Button(footer, theme, fonts, text=app.t("tut.prev"),
                               command=self.prev_step, variant="soft", height=34, radius=8,
                               bg_token="bg", width=80)
        self.btn_prev.pack(side="right", padx=8)

        self.bind_all("<Left>", lambda _e: self.prev_step(), add="+")
        self.bind_all("<Right>", lambda _e: self.next_step(), add="+")
        self._render()

    # ------------------------------------------------------------------
    def next_step(self) -> None:
        if self.index >= len(STEPS) - 1:
            self.close()
            return
        self.index += 1
        self._render()

    def prev_step(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._render()

    def close(self) -> None:
        """Dismiss the tutorial and mark first-run as done."""
        self.app.config.set("first_run", False)
        if self.on_close:
            self.on_close()
        self.destroy()

    # ------------------------------------------------------------------
    def _render(self) -> None:
        app = self.app
        title_key, body_key, _art = STEPS[self.index]
        self.title_label.configure(text=app.t(title_key))
        self.body_label.configure(text=app.t(body_key))
        self.btn_prev.set_enabled(self.index > 0)
        last = self.index == len(STEPS) - 1
        self.btn_next.set_text(app.t("tut.done") if last else app.t("tut.next"))
        self.btn_skip.set_text("" if last else app.t("tut.skip"))
        self._paint_illustration()
        self._paint_dots()

    def _paint_dots(self) -> None:
        self.dots.delete("all")
        width = self.dots.winfo_width()
        if width <= 1:
            return
        theme = self.app.theme
        gap = 14
        total = len(STEPS)
        start = (width - (total - 1) * gap) / 2
        for index in range(total):
            x = start + index * gap
            radius = 4 if index == self.index else 2.5
            color = theme["accent"] if index == self.index else theme["border"]
            self.dots.create_oval(x - radius, 8 - radius, x + radius, 8 + radius,
                                  fill=color, outline="")

    # ------------------------------------------------------------------
    # Illustrations
    # ------------------------------------------------------------------
    def _paint_illustration(self) -> None:
        """Draw the diagram for the current step."""
        canvas = self.canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height() or 150
        if width <= 1:
            return
        theme = self.app.theme
        fonts = self.app.fonts
        art = STEPS[self.index][2]

        # Shared frame: a miniature of the app window.
        half = max(80.0, min(112.0, width / 2 - 24))
        fx1, fy1 = width / 2 - half, 8
        fx2, fy2 = width / 2 + half, height - 8
        draw_round_rect(canvas, fx1, fy1, fx2, fy2, 10, fill=theme["surface"],
                        outline=theme["border"])
        draw_round_rect(canvas, fx1, fy1, fx2, fy1 + 18, 10, fill=theme["bg_alt"])
        canvas.create_oval(fx1 + 8, fy1 + 6, fx1 + 16, fy1 + 14,
                           fill=theme["accent"], outline="")

        if art == "window":
            canvas.create_text(fx1 + 24, fy1 + 10, anchor="w", text="CheckMod",
                               fill=theme["text_dim"], font=fonts["tiny_bold"])
            # Arrows suggesting the window can be dragged anywhere.
            for dx in (-1, 1):
                canvas.create_line(width / 2 + dx * 100, height / 2,
                                   width / 2 + dx * 122, height / 2,
                                   fill=theme["text_faint"], width=1.5,
                                   arrow="last", capstyle="round")
        elif art == "cases":
            names = [c.get("name", "") for c in self.app.config.active_cases()[:3]] or \
                    ["Voice", "Text", "Island"]
            colors = [c.get("color") for c in self.app.config.active_cases()[:3]] or \
                     [theme["accent"], theme["ok"], theme["warn"]]
            slot = (fx2 - fx1 - 20) / max(1, len(names))
            for index, name in enumerate(names):
                x1 = fx1 + 10 + index * slot
                selected = index == 0
                draw_round_rect(canvas, x1 + 2, fy1 + 28, x1 + slot - 2, fy1 + 48, 6,
                                fill=colors[index] if selected else theme["bg_alt"],
                                outline="" if selected else theme["border"])
                canvas.create_text((x1 + x1 + slot) / 2, fy1 + 38, text=name[:8],
                                   fill="#101418" if selected else theme["text_faint"],
                                   font=fonts["tiny"])
            canvas.create_line(fx1 + 10 + slot / 2, fy2 - 26, fx1 + 10 + slot / 2, fy1 + 54,
                               fill=theme["accent"], width=1.6, arrow="last")
        elif art == "timer":
            cx, cy, r = width / 2, (fy1 + fy2) / 2 + 6, 30
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=theme["track"], width=8)
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-250,
                              style=tk.ARC, outline=theme["warn"], width=8)
            canvas.create_text(cx, cy, text="04:12", fill=theme["text"], font=fonts["body_bold"])
            for index, (color, label) in enumerate(
                    ((theme["ok"], "OK"), (theme["warn"], "80%"), (theme["danger"], "100%"))):
                x = fx1 + 18 + index * 52
                canvas.create_oval(x, fy2 - 18, x + 8, fy2 - 10, fill=color, outline="")
                canvas.create_text(x + 13, fy2 - 14, anchor="w", text=label,
                                   fill=theme["text_faint"], font=fonts["tiny"])
        elif art == "checks":
            for index in range(3):
                y = fy1 + 26 + index * 26
                done = index < 2
                draw_round_rect(canvas, fx1 + 10, y, fx2 - 10, y + 20, 5,
                                fill=theme["bg_alt"], outline=theme["border"])
                box_color = theme["ok"] if done else theme["bg"]
                draw_round_rect(canvas, fx1 + 16, y + 4, fx1 + 28, y + 16, 3,
                                fill=box_color, outline=theme["border"])
                if done:
                    canvas.create_line(fx1 + 19, y + 10, fx1 + 21.5, y + 13, fx1 + 26, y + 7,
                                       fill="#0B1710", width=1.8, capstyle="round")
                canvas.create_text(fx1 + 36, y + 10, anchor="w",
                                   text=("Adherence " + str(index + 1)),
                                   fill=theme["text_dim"] if done else theme["text_faint"],
                                   font=fonts["tiny"])
        elif art == "complete":
            draw_round_rect(canvas, fx1 + 14, fy2 - 40, fx2 - 14, fy2 - 14, 8,
                            fill=theme["accent"])
            canvas.create_text((fx1 + fx2) / 2, fy2 - 27,
                               text=self.app.t("user.complete"),
                               fill="#0B1020", font=fonts["small_bold"])
            canvas.create_text((fx1 + fx2) / 2, fy1 + 40, text="00:00",
                               fill=theme["text_faint"], font=fonts["body_bold"])
            canvas.create_line((fx1 + fx2) / 2, fy1 + 56, (fx1 + fx2) / 2, fy2 - 46,
                               fill=theme["ok"], width=1.6, arrow="last")
        elif art == "dev":
            for index in range(4):
                x1 = fx1 + 10 + index * 42
                draw_round_rect(canvas, x1, fy1 + 26, x1 + 38, fy1 + 42, 5,
                                fill=theme["accent"] if index == 0 else theme["bg_alt"],
                                outline="" if index == 0 else theme["border"])
            for index in range(3):
                y = fy1 + 52 + index * 22
                draw_round_rect(canvas, fx1 + 10, y, fx2 - 46, y + 14, 4, fill=theme["bg_alt"])
                draw_round_rect(canvas, fx2 - 40, y, fx2 - 10, y + 14, 7,
                                fill=theme["accent"] if index == 1 else theme["track"])
        elif art == "privacy":
            cx, cy = width / 2, (fy1 + fy2) / 2 + 4
            # Shield outline
            canvas.create_polygon(
                cx, cy - 34, cx + 26, cy - 22, cx + 26, cy + 6, cx, cy + 32,
                cx - 26, cy + 6, cx - 26, cy - 22,
                fill=theme["bg_alt"], outline=theme["ok"], width=2)
            canvas.create_line(cx - 11, cy - 2, cx - 3, cy + 8, cx + 13, cy - 14,
                               fill=theme["ok"], width=3, capstyle="round",
                               joinstyle="round")
            canvas.create_text(cx, fy2 - 14, text="offline · local · no telemetry",
                               fill=theme["text_faint"], font=fonts["tiny"])

    # ------------------------------------------------------------------
    def restyle(self, theme, fonts) -> None:
        """Rebuild on theme change, keeping the current step."""
        index = self.index
        for child in self.winfo_children():
            child.destroy()
        self.configure(bg=theme["bg"])
        self._build()
        self.index = index
        self._render()

# Architecture

CheckMod is deliberately small and deliberately boring: standard library
only, no framework, no build step for the source, and a strict separation
between the logic that produces AHT numbers and the code that draws them.

This document is the map for anyone extending or reviewing it.

---

## Design constraints

Every structural decision follows from four requirements:

1. **No installation, no administrator rights.** Rules out anything that
   touches the registry, `Program Files`, services or global hooks. Also
   rules out a runtime that must be installed first — hence a frozen
   single-file binary.
2. **Privacy first.** Rules out network code, telemetry and any storage of
   identifying data. See [PRIVACY.md](PRIVACY.md).
3. **Small download, auditable source.** Rules out Electron (~150 MB) and
   heavy GUI toolkits. Tkinter ships with Python, so the frozen binary is
   ~12 MB and the dependency list is empty.
4. **Must look good enough to demo.** Tkinter's stock widgets do not, so the
   interface is drawn on canvases instead.

---

## Module map

```
checkmod/
├── paths.py       Storage resolution. The ONLY module that decides where
│                  the app may write. Audit starts here.
├── config.py      Settings: defaults, deep-merge, validation, clamping,
│                  atomic save, change notification.
├── session.py     The stopwatch and checklist state machine. No Tkinter
│                  import — pure, deterministic, fully unit-tested.
├── history.py     Append-only JSON Lines log + statistics + CSV export.
├── theme.py       Colour tokens, eight presets, colour maths, contrast.
├── i18n.py        The string table.
├── app.py         The shell: Tk root, window flags, view swapping,
│                  shortcuts, the 200 ms tick loop, session actions.
└── ui/
    ├── fonts.py       Type scale and font-family resolution.
    ├── primitives.py  Canvas widgets: Button, Segmented, Ring, Bar,
    │                  Slider, Switch, ScrollFrame, Tooltip.
    ├── titlebar.py    Custom window chrome and the resize grip.
    ├── checkrow.py    Adherence rows and the checklist panel.
    ├── dialogs.py     Themed modal Confirm / Alert / Prompt / Picker.
    ├── user_view.py   User Mode (full and compact layouts).
    ├── dev_view.py    Dev Mode (eight sections).
    └── tutorial.py    Seven-step overlay walkthrough.
```

Dependency direction is strictly downward: `ui/` imports from the package
root, never the reverse. `session.py`, `history.py`, `config.py`, `theme.py`
and `paths.py` import no UI code at all, which is why 81 of the 91 tests run
without a display.

---

## State

Three long-lived objects, all owned by `App`:

| Object | Responsibility | Lifetime |
|---|---|---|
| `Config` | Every persisted preference | Whole session |
| `Session` | The case in progress: elapsed time, checks | Reset per case |
| `History` | The on-disk log and its statistics | Whole session |

Views are **disposable**. Any change that affects layout destroys the widget
tree and rebuilds it. That sounds wasteful and is not: a rebuild is a few
dozen canvas widgets and completes in single-digit milliseconds, while the
alternative — incremental restyling — is where subtle half-updated-state bugs
live.

---

## Data flow

```
        user input
            │
            ▼
        App action  ───────────────►  Session (start/pause/check/complete)
            │                              │
            │                              ▼
            │                         History.append()   (only on complete)
            ▼
        Config.set(key, value)
            │
            ├──► settings.json                (atomic write, immediately)
            └──► subscribers ──► App._on_config_change
                                       │
                                       ├─ cosmetic  → schedule_restyle()
                                       └─ window    → apply_window_flags()
```

`Config` is the single source of truth for anything persisted, and the only
publisher of change events. Views never talk to each other; they talk to
`App`, and `App` talks to the model.

### Coalesced restyling

Dragging an opacity or text-scale slider fires dozens of changes per second.
`App.schedule_restyle()` debounces them into one rebuild 90 ms after the last
change, so dragging stays smooth.

### The tick loop

`App._tick()` runs every 200 ms and does three things: refresh the timer
display, update the title-bar status dot, and fire the over-target alert
exactly once per case. 200 ms keeps the seconds column honest at negligible
CPU cost. Elapsed time itself comes from `time.monotonic()` inside `Session`,
so the displayed value cannot drift with the tick, and cannot be corrupted by
a clock change or a daylight-saving jump mid-case.

---

## The widget toolkit

Every interactive element is drawn on a `tkinter.Canvas`. Each widget follows
one contract:

```python
class Thing(CanvasWidget):
    def __init__(self, parent, theme, fonts, ...): ...
    def restyle(self, theme, fonts): ...   # adopt new colours, repaint
    def _redraw(self): ...                 # paint current state, idempotent
```

Widgets receive their `theme` and `fonts` rather than reading global state,
which keeps them reusable and makes the views the single place where
application state meets presentation.

Colours are addressed by **token** (`"surface"`, `"text_dim"`, `"accent"`),
never as literals. A theme is a token → colour mapping, which is what makes
runtime re-skinning a one-object swap.

### Why hand-drawn geometry rather than font glyphs

Checkmarks, the pencil affordance and the resize grip are drawn with
`create_line`, not typed as `✓` or `✏`. Corporate Windows images frequently
lack the symbol and emoji fonts those characters need, and a missing glyph
renders as a hollow box in the middle of the interface. Lines always draw.

---

## Window management

With `frameless` enabled (the default) the app calls `overrideredirect(True)`
to remove the OS decorations and paints its own title bar. This gives an
identical, compact look on every machine.

The trade-off is that a decorationless window has no taskbar button and
therefore no OS minimise. That is covered by the compact layout, and users
who prefer native chrome can turn *Custom title bar* off in Dev Mode.

Dragging, edge snapping and resizing are implemented in `titlebar.py` against
`App.move_window` / `App.resize_window` / `App.snap_and_store`.

Window auto-fit: after building a view, `App._apply_layout_size()` grows the
window to `max(stored height, view.winfo_reqheight())`. A larger text scale
or an extra checklist item can therefore never push the **Complete case**
button off the bottom of the window.

---

## Extension points

| To add… | Do this |
|---|---|
| **A setting** | Add a key to `DEFAULTS` in `config.py`, add a range to `LIMITS` if numeric, add a control in the matching `dev_view.py` section. It persists and notifies automatically. |
| **A theme** | One entry in `PRESETS` (`theme.py`). It appears in the swatch grid on its own. |
| **A widget** | Subclass `CanvasWidget` in `ui/primitives.py` and implement `_redraw`. |
| **A Dev Mode section** | Add a tuple to `DevView.SECTIONS` and a `_section_<key>` method. |
| **A tutorial step** | Add a tuple to `STEPS` in `ui/tutorial.py`, its two strings to `i18n.py`, and a branch in `_paint_illustration`. |
| **A statistic** | Extend `History.stats()`; it returns a plain dict the view renders. |
| **A language** | See [CUSTOMIZATION.md](CUSTOMIZATION.md#adding-a-language). |

---

## Testing strategy

| Suite | Covers | Needs a display |
|---|---|---|
| `test_session.py` | Timer maths, pause accounting, status thresholds, checklist, record schema | No |
| `test_config.py` | Defaults, dotted access, corrupt/partial files, clamping, presets, notification | No |
| `test_history.py` | Append/read, truncated lines, retention, statistics, CSV export | No |
| `test_theme.py` | Token completeness, WCAG contrast for every preset, colour maths | No |
| `test_paths.py` | Storage resolution, portable mode, read-only fallback | No |
| `test_i18n.py` | Fallbacks, and that every key the UI references exists | No |
| `test_gui_smoke.py` | Builds the real window: every view, every theme, every Dev Mode section, a full case lifecycle | Yes — auto-skipped without one |

```bash
python -m pytest tests/ -v              # anywhere
xvfb-run -a python -m pytest tests/ -v  # headless Linux, GUI tests included
```

The GUI suite exists to catch the one failure class unit tests cannot: a view
that raises while painting. It is the reason a theme or layout change can be
made with confidence.

---

## Packaging

`packaging/CheckMod.spec` freezes the app with PyInstaller into one file:

- `console=False` — no terminal window behind the floating UI.
- `upx=False` — UPX compression is the leading cause of antivirus false
  positives on PyInstaller binaries; the few megabytes are not worth it.
- A generous `excludes` list drops standard-library modules the app never
  uses. It halves the binary **and** removes networking from the bundle
  entirely, which is a privacy property, not just a size one.
- `version_info.txt` fills in the Windows *Properties → Details* tab, which
  is the first thing IT looks at when an unsigned binary appears.

PyInstaller does not cross-compile: the Windows executable must be built on
Windows. `.github/workflows/build.yml` does that on every tag.

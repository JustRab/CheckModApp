# Changelog

All notable changes to CheckMod are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.1] — 2026-09-02

### Fixed

- **The title bar was clipped on scaled displays.** Its height was hard-coded
  to 34 px, but PyInstaller marks the frozen executable DPI-aware, so on a
  display at 150% scaling Tk renders the 11 pt title at ~27 px and the bar had
  no room for it. At 125% it landed exactly on the boundary, which is why the
  clipping looked intermittent. The bar, its buttons, the mode chip and the
  resize grip are now all sized from live font metrics, so they fit at every
  display scaling and at every *Text scale* setting.
- **The title bar only repainted by accident.** Its canvas had no `<Configure>`
  binding, so it kept whatever it had drawn before it was first laid out —
  and `winfo_height()` returns `1` (which is truthy) at that point, so the
  `or HEIGHT` fallback never fired and everything was drawn at y≈0. It only
  looked right once an unrelated repaint happened to correct it, which is why
  resizing or changing the theme "fixed" it.
- **The tutorial covered the title bar**, so the window could not be moved,
  pinned or closed while the walkthrough was open. The overlay now covers the
  body only, and its own header can also drag the window.

### Added

- **One-folder distribution** (`CheckMod-folder.zip`) alongside the single
  executable. It extracts nothing to `%TEMP%` at launch — the behaviour
  heuristic antivirus most often flags on PyInstaller binaries — and starts
  instantly. Recommended for managed corporate machines.
- **`SHA256SUMS.txt`** published with every release so IT can allow-list an
  exact build instead of granting a blanket exception.
- **Optional code signing in CI**, active when a repository provides
  `WINDOWS_CERT_PFX_BASE64` and `WINDOWS_CERT_PASSWORD`; skipped otherwise.
- **[docs/IT-APPROVAL.md](docs/IT-APPROVAL.md)** — a one-page summary for
  whoever approves software on corporate machines: what the app touches, why
  a warning may appear, and how to verify each claim.

### Changed

- Both PyInstaller specs now share `packaging/build_config.py`, so the exclude
  list — a privacy guarantee, not just a size optimisation — cannot drift
  between the two build layouts.
- The release workflow triggers on bare semver tags (`1.0.0`) as well as
  `v`-prefixed ones.

## [1.0.0] — 2026-09-02

First release.

### Added

**Core workflow**
- Floating, always-on-top window with a custom draggable title bar, edge
  snapping, corner resize grip and a remembered position.
- Case types with individual AHT targets — Voice Chat (15:00), Text Chat
  (10:00) and Island (20:00) out of the box — addable, renameable,
  recolourable, reorderable and removable.
- Circular AHT gauge with amber and over-target states, an optional alert
  sound and a blinking title-bar status dot.
- Start / pause / reset with paused time excluded from AHT by default.
- Four-item adherence checklist (Escalation, Enforcement, Evidence, Comment)
  with per-item hover descriptions; fully editable.
- **Complete case** logs a local record, resets the checklist and keeps the
  case type selected.
- Quick AHT editor reachable directly from the timer.

**Two modes**
- *User Mode* — case type, timer, checklist, one button.
- *Dev Mode* — eight sections covering appearance, window behaviour, case
  types and AHT, checklist, timer rules, data and privacy, statistics and
  about.

**Customisation**
- Eight themes (Midnight, Graphite, Nord, Aurora, Forest, Daylight, Paper,
  High contrast), all contrast-tested.
- Ten accent swatches plus a custom colour picker, and per-token palette
  overrides in the settings file.
- Font family, text scale, corner radius and window opacity.
- Compact single-strip layout.
- Settings import/export for team-wide presets.

**Data**
- Local JSON Lines history with configurable retention and one-click erase.
- Statistics for today, the last 7 days and all time, including per case type
  and most-missed adherence items.
- CSV export using the user's own checklist labels as headers.
- Portable mode storing settings and history next to the executable.

**Onboarding & documentation**
- Seven-step in-app tutorial with hand-drawn illustrations, shown on first
  run and available any time via `F1`.
- Keyboard shortcuts for every frequent action, listed in Dev Mode.
- README plus tutorial, customisation, privacy, build, architecture and FAQ
  documents.

**Engineering**
- Zero runtime dependencies — Python standard library only.
- Single-file portable executable via PyInstaller; no installer and no
  administrator rights.
- Icon generated from code, no image editor required.
- 91 tests: timer maths, settings validation and self-healing, history and
  statistics, theme contrast, storage resolution, and a headless interface
  smoke pass over every view, theme and Dev Mode section.
- GitHub Actions for tests (Python 3.9 / 3.11 / 3.12 under Xvfb) and for
  building and releasing the Windows executable.

### Privacy
- No network code of any kind; networking modules are excluded from the
  frozen binary.
- No telemetry, analytics, crash reporting or auto-update.
- No personal data or case identifiers are recorded — the record schema has
  no field for them, and a test enforces it.

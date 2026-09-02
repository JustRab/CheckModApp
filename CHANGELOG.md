# Changelog

All notable changes to CheckMod are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

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

# Customisation reference

Everything in CheckMod is configurable, live, from **Dev Mode** — the **DEV**
button in the title bar, or `Ctrl+D`. Every change is written to
`settings.json` immediately; there is no "Save" button and no restart.

This document is the complete reference: what each control does, what the
settings file looks like, and how to roll a configuration out to a team.

---

## Contents

- [Style](#style)
- [Window](#window)
- [Case types and AHT targets](#case-types-and-aht-targets)
- [Checklist items](#checklist-items)
- [Rules](#rules)
- [Data](#data)
- [Team-wide presets](#team-wide-presets)
- [settings.json reference](#settingsjson-reference)
- [Adding a theme in code](#adding-a-theme-in-code)
- [Adding a language](#adding-a-language)

---

## Style

| Control | Effect |
|---|---|
| **Theme** | One of eight presets. Click a swatch to apply it instantly. |
| **Accent colour** | Ten one-click swatches, plus **Custom colour** for the OS colour picker. The **↺** button clears the override and returns to the theme's own accent. |
| **Font** | Pick from the sans-serif families actually installed on the machine, or leave it on `auto`, which prefers Segoe UI on Windows and falls back sensibly elsewhere. |
| **Text scale** | 0.80× – 1.40×. The window grows to fit, so nothing is ever clipped. |
| **Corner radius** | 0 – 24 px. `0` gives a squared-off, utilitarian look. |
| **Opacity** | 35% – 100% window transparency. |
| **Show progress ring** | Off swaps the ring for a large time read-out plus a slim progress bar. |
| **Show stats bar** | Toggles the one-line "today" summary at the bottom of User Mode. |

### The themes

| Preset | Character |
|---|---|
| **Midnight** | Deep navy, blue accent. The default. |
| **Graphite** | Neutral greys, no colour cast. |
| **Nord** | The familiar cool-blue palette. |
| **Aurora** | Dark violet with a purple accent. |
| **Forest** | Dark green, calm and low-glare. |
| **Daylight** | Clean light theme for bright offices. |
| **Paper** | Warm light theme, easier on the eyes than pure white. |
| **High contrast** | Black background, yellow accent, maximum legibility. |

Every preset is checked by the test suite for WCAG contrast: body text scores
at least 7:1 against its background and secondary text at least 4.5:1. If you
add a theme, that test will hold you to the same bar.

---

## Window

| Control | Effect |
|---|---|
| **Always on top** | Keeps CheckMod above every other window. Also the pin button in the title bar and `Ctrl+T`. |
| **Custom title bar** | On (default) removes the OS decorations and uses CheckMod's own compact bar. Turning it **off** restores the native title bar — and therefore a taskbar button and normal minimise. |
| **Snap to screen edges** | Releasing a drag near an edge clicks the window flush against it. |
| **Snap distance** | 0 – 60 px. How close counts as "near". |
| **Remember position** | Restores the last position and size at launch. |
| **Centre window** | Recovery button for a window that ended up off-screen after a monitor change. |
| **Compact mode** | The collapsed single-strip layout. Also `Ctrl+M` or a double-click on the title bar. |
| **Show in the taskbar and Alt+Tab** | On. A borderless window is a *tool window* to Windows and is hidden from both by default; this forces it back so the window cannot get lost. |
| **Desktop shortcut** | Creates/removes a shortcut in your own Desktop folder. |
| **Start when I sign in** | Creates/removes an entry in your per-user Start-up folder. No registry key, no service, no admin rights. |

> **Why is there no minimise button?** A window without OS decorations has no
> taskbar entry to minimise into. That is the trade-off for the compact,
> identical-everywhere chrome. Use the compact layout instead — or turn
> *Custom title bar* off if you would rather have the native one.

---

## Case types and AHT targets

*Dev Mode → AHT.* Each case type is one card:

| Field | Notes |
|---|---|
| **Colour dot** | Click for a colour picker. This colour tints the pill in User Mode and the status dot in the title bar. |
| **Name** | Up to 40 characters. Press Enter or click away to commit. |
| **Enable switch** | Off hides the type from User Mode without deleting it or its history. |
| **AHT target** | The time budget. See the formats below. |
| **▲ / ▼** | Reorder. The order here is the order of the pills — and of the `Alt+1…9` shortcuts. |
| **×** | Delete, with confirmation. |

**+ Add case type** creates a new one with a 10:00 target and the next unused
accent colour.

### AHT target formats

| You type | Stored as |
|---|---|
| `15` | 15 minutes |
| `12.5` | 12 min 30 s |
| `15:30` | 15 min 30 s |
| `1:30:00` | 1 h 30 min |

A bare number means **minutes**, because that is how AHT is discussed day to
day. Anything unparseable is rejected and the field reverts — a typo can
never silently set a target to zero.

You can also edit the target for the selected type straight from User Mode by
clicking the `Target 15:00 ✎` pill under the timer.

---

## Checklist items

*Dev Mode → Checks.* Same card layout, with one extra field:

| Field | Notes |
|---|---|
| **Label** | Up to 60 characters. What appears on the row. |
| **Description** | Up to 240 characters. Shown as a tooltip when the moderator hovers the row in User Mode — the natural place for your team's exact policy wording. |
| **Enable switch** | Off removes the item from User Mode but keeps it in history. |
| **Applies to** | Chips for each case type. *All case types* is the default; selecting specific types makes the item appear only for those. Evidence Adherence ships set to Island only, because Voice and Text chats have no evidence to attach. |
| **▲ / ▼ / ×** | Reorder and delete. Row order matches the `1…9` shortcuts. |

Editing the checklist while a case is open never clears ticks that have
already been made: existing items keep their state, new items start unticked.

The four defaults (Escalation, Enforcement, Evidence and Comment Adherence)
are ordinary items — rename them, reorder them, or replace them entirely.

---

## Rules

| Control | Default | Effect |
|---|---|---|
| **Start timer when a type is picked** | On | Off makes case selection and starting the clock two separate actions. |
| **Confirm before resetting** | On | Asks before discarding elapsed time or ticked items. |
| **Require a full checklist to complete** | Off | On disables **Complete case** until every item is ticked. |
| **Count paused time** | Off | On includes paused time in the logged duration. |
| **Amber warning at** | 80% | Where the ring turns amber, as a percentage of the target. |
| **Alert when the AHT target is passed** | On | Red ring plus a slowly blinking status dot in the title bar. |
| **Warn before the target is reached** | On | A heads-up while there is still time to act. |
| **Warn this many seconds early** | 10 s | 0 disables it. |
| **Alert sound** | Off | One high tone for the heads-up, two lower tones when the target is passed, so they are distinguishable by ear. Uses only what the OS already provides — no audio files, no libraries. |

### Adaptive AHT

| Control | Default | Effect |
|---|---|---|
| **Adaptive target** | On | The timer target tracks this week's average for the case type instead of the static configured number. |
| **Spread corrections over** | 10 cases | A larger number corrects more gently. |
| **Never ask for less than** | 60% | Floor, as a fraction of the configured target. |
| **Never hand back more than** | 125% | Ceiling, for when you are ahead of budget. |
| **Week starts on** | Sunday | Sunday–Saturday, or Monday for ISO weeks. |

The arithmetic, for `n` cases this week totalling `total` against target `T`:

```
debt          = total - n * T            (> 0 means over budget)
adaptive      = clamp(T - debt / spread, T * min, T * max)
required(m)   = T - debt / m             (AHT for the next m cases)
cases_at(d)   = ceil(debt / (T - d))     (cases needed at a fixed pace d)
```

`required` and `cases_at` are what *Dev Mode → Stats* reports; `adaptive` is
what the timer asks for. History records keep both the configured target and
the adaptive one in force at the time, so past cases stay interpretable.

---

## Data

| Control | Effect |
|---|---|
| **Keep local history** | Off stops all writing. The timer and checklist still work. |
| **Keep history for** | 1 – 365 days, or *Unlimited*. Older records are pruned at start-up. |
| **Storage path** | Shown on screen. **Open data folder** reveals it in the file manager. |
| **Portable mode** | Stores settings and history in `CheckModData\` next to the executable instead of your user profile. Existing files are not moved automatically — you keep both copies and decide. |
| **Export history (CSV)** | Spreadsheet-friendly export using your own checklist labels as column headers. |
| **Export / Import settings** | Share a configuration as a JSON file. |
| **Restore factory settings** | Resets every preference; history is untouched. |
| **Erase all data** | Deletes the history **and** resets settings. |

---

## Team-wide presets

To give a whole team the same case types, AHT targets and checklist:

1. Configure one machine exactly the way you want it.
2. *Dev Mode → Data → **Export settings*** → save `checkmod-settings.json`.
3. Share that file.
4. On each machine: *Dev Mode → Data → **Import settings***.

Import **merges** onto the existing settings, so personal preferences that
are not part of the preset survive. The `first_run` flag is deliberately
ignored on import, so nobody gets the tutorial replayed at them.

For an unattended rollout, drop the file at the storage path from
[PRIVACY.md §4](PRIVACY.md#4-where-data-is-stored) — or set
`CHECKMOD_DATA_DIR` to a shared, writable folder.

---

## settings.json reference

Full file, with the factory values:

```jsonc
{
  "schema": 2,                      // migration marker, do not edit

  "language": "en",
  "mode": "user",                   // "user" | "dev" - the mode on launch
  "first_run": true,                // shows the tutorial once, then false

  // ---- appearance ----
  "theme": "midnight",              // midnight|graphite|nord|aurora|forest|
                                    // daylight|paper|contrast
  "accent": "",                     // "" = the theme's own accent, else "#rrggbb"
  "palette_overrides": {},          // token -> "#rrggbb", applied last
  "font_family": "",                // "" = auto-detect
  "font_scale": 1.0,                // 0.8 .. 1.4
  "corner_radius": 12,              // 0 .. 24
  "opacity": 0.97,                  // 0.35 .. 1.0
  "show_ring": true,
  "show_footer_stats": true,
  "compact": false,

  // ---- window ----
  "always_on_top": true,
  "frameless": true,                // false = native OS title bar
  "show_in_taskbar": true,          // force taskbar/Alt+Tab presence
  "snap_to_edges": true,
  "snap_threshold": 18,             // 0 .. 60 px
  "remember_position": true,
  "window": { "x": null, "y": null, "w": 360, "h": 600 },

  // ---- timer rules ----
  "auto_start_on_select": true,
  "warn_at_pct": 80,                // 10 .. 100
  "alert_on_over": true,
  "sound_enabled": true,
  "confirm_reset": true,
  "require_all_checks": false,
  "count_paused_time": false,
  "prealert_enabled": true,
  "prealert_seconds": 10,           // 0 = off

  // ---- adaptive AHT ----
  "adaptive_target": true,
  "adaptive_recovery_cases": 10,    // spread corrections over this many cases
  "adaptive_min_factor": 0.6,       // floor, as a fraction of the target
  "adaptive_max_factor": 1.25,      // ceiling
  "week_starts_on": "sunday",       // "sunday" | "monday"

  // ---- data ----
  "history_enabled": true,
  "history_retention_days": 30,     // 0 = unlimited

  // ---- domain ----
  "case_types": [
    { "id": "voice",  "name": "Voice Chat", "target_s": 900,  "color": "#7C5CFF", "enabled": true },
    { "id": "text",   "name": "Text Chat",  "target_s": 600,  "color": "#2BB3A3", "enabled": true },
    { "id": "island", "name": "Island",     "target_s": 1200, "color": "#F2A03D", "enabled": true }
  ],

  "checklist": [
    // "applies_to": [] means every case type.
    { "id": "escalation",  "label": "Escalation Adherence",  "hint": "...", "enabled": true, "applies_to": [] },
    { "id": "enforcement", "label": "Enforcement Adherence", "hint": "...", "enabled": true, "applies_to": [] },
    { "id": "evidence",    "label": "Evidence Adherence",    "hint": "...", "enabled": true, "applies_to": ["island"] },
    { "id": "comment",     "label": "Comment Adherence",     "hint": "...", "enabled": true, "applies_to": [] }
  ]
}
```

The file is safe to hand-edit. On load it is merged onto the defaults and
validated: unknown keys are kept, missing keys are filled in, out-of-range
numbers are clamped, and malformed case types or checklist items are dropped.
A file that cannot be parsed at all is renamed to `settings.json.broken-<time>`
rather than overwritten, so nothing is ever silently destroyed.

### Palette overrides

`palette_overrides` re-colours individual design tokens on top of the chosen
theme. Valid tokens:

`bg`, `bg_alt`, `surface`, `surface_hi`, `border`, `text`, `text_dim`,
`text_faint`, `accent`, `accent_text`, `ok`, `warn`, `danger`, `track`

```json
"palette_overrides": { "ok": "#00C853", "danger": "#FF1744" }
```

Invalid tokens and malformed colours are ignored, so a typo cannot produce an
unreadable interface.

---

## Adding a theme in code

Add one entry to `PRESETS` in `checkmod/theme.py`:

```python
"ocean": _palette(
    label="Ocean", dark="1",
    bg="#08131C", bg_alt="#0C1B27", surface="#102432", surface_hi="#16303F",
    border="#1E4054", text="#E6F3FA", text_dim="#9BB8C9", text_faint="#67849A",
    accent="#35C4E8", accent_text="#04141C",
    ok="#3DD68C", warn="#F5B942", danger="#FF6B6B", track="#16303F",
),
```

It appears in the Dev Mode swatch grid automatically. Run
`python -m pytest tests/test_theme.py` — the contrast tests apply to your
theme too.

---

## Adding a language

All user-visible copy lives in `checkmod/i18n.py`. To add a language:

1. Copy the `"en"` dictionary under a new language code.
2. Translate the values; leave the keys alone.
3. Add `("code", "Display name")` to `LANGUAGES`.
4. Select it by setting `"language": "<code>"` in `settings.json`. (Only
   English ships today, so Dev Mode has no language selector; add one to the
   Style section if you package more than one.)

Missing keys fall back to English, so a partial translation never breaks a
view. `tests/test_i18n.py` verifies that every key referenced by the UI
actually exists.

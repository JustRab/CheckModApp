# CheckMod — usage guide

This is the long-form version of the walkthrough that opens the first time
you run the app. You can re-open the in-app version at any time with the
**?** button in the title bar, with `F1`, or from *Dev Mode → Info →
Tutorial*.

---

## 1. Getting the window where you want it

CheckMod draws its own title bar so it can stay small and look the same on
every machine.

- **Move it** — drag the title bar.
- **Snap it** — release it near a screen edge and it clicks flush against it.
  (Turn this off, or change the snap distance, in *Dev Mode → Window*.)
- **Resize it** — drag the grip in the bottom-right corner.
- **Keep it on top** — the round pin button. Filled means "always on top" is
  on; hollow means the window behaves like any other. `Ctrl+T` toggles it.
- **Shrink it** — the **—** button, `Ctrl+M`, or a double-click on the title
  bar collapses the window to the compact strip. Everything still works; it
  just takes a fraction of the space.
- **Make it see-through** — *Dev Mode → Style → Opacity*, handy when you want
  to read what is underneath.

The position and size are remembered between runs.

---

## 2. Picking the case type

The coloured pills at the top are your case types. Out of the box:

| Case type | Default AHT target |
|---|---|
| Voice Chat | 15:00 |
| Text Chat | 10:00 |
| Island | 20:00 |

Clicking one binds it to the current case **and starts the timer** (you can
turn that off in *Dev Mode → Rules → Start timer when a type is picked*).
`Alt+1`, `Alt+2`, `Alt+3` do the same from the keyboard.

Picking a different type part-way through a case keeps the elapsed time and
just swaps the target — moderators reclassify cases all the time, and losing
the clock for it would be worse than useless.

---

## 3. Reading the timer

The ring shows elapsed time against the AHT target for the selected type.

- The number in the middle is **elapsed time**.
- The number underneath is **time remaining**, or **`+mm:ss` over** once you
  pass the target.
- **Green/case colour** — comfortably inside the target.
- **Amber** — you have reached the warning threshold (80% by default;
  change it in *Dev Mode → Rules*).
- **Red** — the target has been passed. The status dot in the title bar
  blinks slowly so you notice even if the window is behind something, and an
  optional sound can fire once.

Controls:

- **Start / Pause** — `Space`. Paused time is excluded from the AHT by
  default; *Dev Mode → Rules → Count paused time* changes that.
- **Locking your PC does not stop the clock.** A running case keeps counting
  through a lock, a screen blank or a full suspend, so stepping away without
  pausing shows up in the AHT rather than quietly vanishing from it.
- **Reset** — `Ctrl+R`. Clears the clock and the checklist for this case.
  Asks for confirmation if anything would be lost.

If you prefer a slimmer look, *Dev Mode → Style → Show progress ring* swaps
the ring for a large time read-out with a progress bar.

---

## 4. Changing an AHT target

Two ways, both instant:

**From the timer** — click the **`Target 15:00 ✎`** pill under the ring, type
a new value, press Enter.

**From Dev Mode** — *Dev Mode → AHT*, then edit the target field on any case
type.

Accepted formats:

| You type | It means |
|---|---|
| `5` | 5 minutes |
| `4.5` | 4 minutes 30 seconds |
| `05:30` | 5 minutes 30 seconds |
| `1:30:00` | 1 hour 30 minutes |

A bare number is read as **minutes**, because that is how AHT is discussed.

---

## 5. Working the checklist

The adherence items are the ones your QA is scored on. **Which ones appear
depends on the case type** — Evidence Adherence only shows for Island, because
Voice and Text chats have no evidence to attach, so those show three items
instead of four. Dev Mode → Checks controls this per item.

| Item | What you are confirming |
|---|---|
| **Escalation Adherence** | The case was escalated to the right queue or tier when it needed to be. |
| **Enforcement Adherence** | The action applied matches the policy and the severity tier. |
| **Evidence Adherence** | Evidence is attached, legible and sufficient to justify the action. |
| **Comment Adherence** | The internal comment explains the reasoning clearly and completely. |

- **Click anywhere on a row** to tick it — the whole row is the target, not a
  tiny box.
- **`1` to `4`** toggle them from the keyboard.
- **Check all** in the section header ticks everything; press it again to
  clear everything.
- **Hover a row** to see its description. You can rewrite those descriptions
  to match your own policy wording — see below.

A ticked row turns green with a coloured rail down the left edge, so a
cleared checklist is recognisable out of the corner of your eye. The line
underneath tells you how many items are still open.

---

## 5b. Adaptive targets

By default the target shown under the ring is **adaptive**: it tracks this
week's average for the case type rather than sitting on the configured number.

- Run long on a few cases and the next ones ask for slightly less, so the
  weekly average is pulled back towards target.
- Run fast and a little slack comes back.
- The correction is spread over the next 10 cases (configurable) and clamped
  between 60% and 125% of the configured target, so it never becomes absurd.

When the adaptive target differs from the configured one the pill shows the
difference — `Target 14:30 (-00:30)` — in the accent colour, and hovering it
names the base target. Turn the whole thing off in *Dev Mode → Rules →
Adaptive target* to always use the configured number.

A **heads-up alert** fires 10 seconds before the target (configurable): a
rising two-note chime plus a blink of the status dot. Passing the target gives
an urgent high/low warble, repeated — clearly different, so you can tell them
apart without looking away from the case. *Dev Mode → Rules* has a button to
play each one on demand, and controls how many times the over-target alert
repeats.

## 6. Completing the case

**Complete case** (`Ctrl+Enter`):

1. writes one record to the local history — case type, duration, target and
   which items were cleared;
2. resets the timer and the checklist;
3. leaves the same case type selected, ready for the next case.

If you want the app to *stop* you from completing a case with an unfinished
checklist, turn on *Dev Mode → Rules → Require a full checklist to complete*.

The line at the bottom summarises today's count and this week's position for
the selected case type — the average the adaptive target is steering, with an
arrow showing whether you are over or under budget.

**Completed the wrong case?** The **↶** button next to that line (or `Ctrl+Z`,
or *Dev Mode → Data → Undo last logged case*) removes the most recent record.
If nothing is in progress the case is put straight back on the clock, paused,
with its ticks intact, so you can fix it and complete it again. Worth knowing,
because a wrong record now skews the weekly average that drives your targets.

---

## 7. Making it yours

Everything below lives in **Dev Mode** (the **DEV** button, or `Ctrl+D`).

### Adding or editing case types

*Dev Mode → AHT*. Each card gives you a colour dot (click for a colour
picker), the name, the AHT target, an enable switch, reorder arrows and a
delete button. **+ Add case type** creates a new one.

Disabling a type hides it from User Mode without deleting its history.

### Adding or editing checklist items

*Dev Mode → Checks*. Same controls, plus a description field — that text is
what appears when you hover the row in User Mode. Use it for your team's
exact policy wording.

Editing the checklist mid-case never clears the ticks you have already made.

### Appearance

*Dev Mode → Style*: eight themes (five dark, two light, one high-contrast),
ten accent swatches plus any custom colour, font family, text scale, corner
radius and opacity. Everything applies live.

See **[CUSTOMIZATION.md](CUSTOMIZATION.md)** for the full reference.

---

## 8. Statistics

*Dev Mode → Stats* opens with **this week, Sunday to Saturday**, broken down
per case type:

- how many cases, and the running average against target,
- how far over or under budget you are, in minutes,
- and, when you are over, **the recovery plan**: the AHT the next 5, 10 or 20
  cases would each need to run at to bring the weekly average back to target.
  A pace that is not realistically reachable is marked as such rather than
  printed as an impossible number, and you also get the minimum number of
  cases needed at the fastest pace you are willing to ask for.
- The adaptive target currently in force is shown at the bottom of each card.

Worked example: four Voice Chat cases totalling 65:00 against a 60:00 budget
puts you 5:00 over, so the next 10 cases need to average 14:30 instead of
15:00 — which is exactly the number the timer will ask for.

Below that, Today and All time show:

- number of cases handled,
- average AHT,
- percentage finished within target,
- percentage finished with a clean checklist,
- a per-case-type breakdown,
- and a ranked list of the adherence items you miss most often.

That last one is the useful one: it tells you which part of the process to
tighten up before QA does it for you.

**Export history (CSV)** writes the whole log to a spreadsheet-friendly file,
with your own checklist labels as column headers.

---

## 9. Your data

*Dev Mode → Data* shows exactly where your files live and lets you:

- turn the local history **off** entirely (the app still times cases, it just
  stops writing records),
- set how long history is kept (default 30 days, older records are pruned on
  start-up),
- switch to **portable mode**, which keeps settings and history in a
  `CheckModData` folder next to the executable instead of in your user
  profile — ideal for a USB stick,
- **export/import settings** to share a team-wide preset,
- open the data folder,
- and **erase all data** with one button.

Full details in **[PRIVACY.md](PRIVACY.md)**.

---

## Keyboard shortcuts

| Keys | Action |
|---|---|
| `Space` | Start / pause |
| `1` … `9` | Toggle checklist item *n* |
| `Alt+1` … `Alt+9` | Select case type *n* |
| `Ctrl+Enter` | Complete case |
| `Ctrl+R` | Reset case |
| `Ctrl+Z` | Undo the last logged case |
| `Ctrl+D` | Dev Mode on/off |
| `Ctrl+T` | Always on top on/off |
| `Ctrl+M` | Compact layout on/off |
| `F1` | Tutorial |
| `Ctrl+Q` | Quit |

Shortcuts only fire while the CheckMod window has focus, and they are
ignored while you are typing in a text field.

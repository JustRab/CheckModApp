# FAQ & troubleshooting

## Using it

**Do I need to install anything?**
No. Copy `CheckMod.exe` wherever you like and double-click it. There is no
installer, no setup wizard and nothing added to Add/Remove Programs.

**Does it need administrator rights?**
No — not to run, not to update, not even to build. It writes only to folders
you already own.

**Where does it keep my settings?**
`%APPDATA%\CheckMod` on Windows by default, or a `CheckModData` folder next
to the executable in portable mode. *Dev Mode → Data* shows the exact path
and can open it.

**Can I run it from a USB stick?**
Yes. Turn on *Dev Mode → Data → Portable mode* and everything travels with
the executable.

**How do I make it start with Windows, or put it on my Desktop?**
*Dev Mode → Window → Shortcuts & start-up* has a switch for each. Both write
only into your own profile folders, so neither needs admin rights and neither
touches the registry.

**How do I share the app with a teammate without making the repo public?**
Hand them `CheckMod-folder.zip` from the release — it is the whole app and
needs no repository access. See [DISTRIBUTION.md](DISTRIBUTION.md).

**Why is there no minimise button?**
The window has no OS decorations — that is what lets it be a small, identical
floating panel on every machine — so there is no taskbar entry to minimise
into. Use the compact layout instead (`Ctrl+M`, the **—** button, or a
double-click on the title bar), or turn *Dev Mode → Window → Custom title
bar* off to get the native chrome back.

**It disappeared behind another window / I cannot find it.**
Check the pin button in the title bar: filled means always-on-top is on,
hollow means off (`Ctrl+T` toggles it). Since 1.2.0 the window also appears in
the taskbar and Alt+Tab, so it can be recovered that way; if it somehow does
not, turn off *Dev Mode → Window → Custom title bar* to get native chrome.

**I switched between compact and normal and lost my case.**
Layout switching preserves the timer, the ticks and the case type — there are
tests pinning that. The likely culprit was the compact layout's **OK** button,
which actually filed the case and cleared everything. It is a tick styled as
the primary action from 1.2.0. If it happens again, `Ctrl+Z` (or the **↶**
button) undoes the last completed case and puts it back on the clock.

**I dragged it off-screen / changed monitors and cannot find it.**
It clamps itself back on screen at launch. If it is still awkward, use *Dev
Mode → Window → Centre window*.

**Can I change the AHT targets?**
Yes, in two places: click the `Target 15:00 ✎` pill under the timer, or use
*Dev Mode → AHT*. Type `15` for fifteen minutes, or `15:30` for fifteen and a
half.

**Can I add my own case types or checklist items?**
Yes — *Dev Mode → AHT* and *Dev Mode → Checks*. Add, rename, recolour,
describe, reorder, disable or delete anything, including the four defaults.

**Why does Voice Chat show three checklist items and Island four?**
Evidence Adherence only applies to Island — a voice or text chat has no
evidence to attach. Change it in *Dev Mode → Checks*: every item has an
*Applies to* row where you pick the case types it is required for.

**Why is the target different from what I set?**
Adaptive targeting is on by default: the timer tracks this week's average for
that case type, so running long on a few cases makes the next ones ask for
slightly less. The pill shows the difference, e.g. `Target 14:30 (-00:30)`,
and hovering it names your configured target. *Dev Mode → Rules → Adaptive
target* turns it off.

**I completed a case by mistake.**
Press `Ctrl+Z`, or the **↶** button at the bottom of User Mode, or *Dev Mode →
Data → Undo last logged case*. The record is removed and — if nothing else is
in progress — the case comes back on the clock, paused, with its ticks intact.

**How do I know how much AHT I need to catch up?**
*Dev Mode → Stats* opens with this week per case type: how far over or under
budget you are, and the AHT the next 5, 10 or 20 cases would need to average
to bring the weekly number back to target.

**Does the timer keep running if I switch case type mid-case?**
Yes. Elapsed time is kept and only the target changes, because reclassifying
a case part-way through is normal.

**Does the timer keep running when I lock my PC?**
Yes, since 1.3.0 — including through a full suspend. Before that the timer
used only the monotonic clock, which Windows freezes while the machine is
asleep, so a break taken without pausing was silently dropped from the AHT.

**What happens to paused time?**
It is excluded from the logged AHT by default. *Dev Mode → Rules → Count
paused time* includes it.

**Does it track me?**
No. See [PRIVACY.md](PRIVACY.md). No telemetry, nothing is ever uploaded, and
the record schema has no field for anything that identifies a person or a
case.

**Does it use the internet?**
Only when you press **Sync targets from the sheet**, and only to read the
team's AHT sheet. That is one read-only HTTPS `GET` of a Google Sheet shared
for viewing. The link ships already filled in, so the button works without any
setup — but a configured link does not make the app fetch anything on its own:
there is no polling and nothing on start-up, and the networking module is not
imported until the button is pressed. Clearing the link in *Dev Mode → Data*
switches the feature off. There is no upload path anywhere in the code, so
nothing about you or your cases can leave the machine.
[PRIVACY.md §1](PRIVACY.md#1-network-access-one-user-initiated-read)
has the full list of guarantees and how to verify each one.

**The sheet sync says the sheet is not shared. Why?**
Google is serving a sign-in page instead of the document. The sheet has to be
shared as *anyone with the link can view* — CheckMod sends no credentials, so
a sheet restricted to named people cannot be read. Ask the sheet's owner to
change the link sharing, or type the targets in Dev Mode instead.

**Can the sheet sync overwrite my targets by surprise?**
No. It shows what it found next to what you have and writes nothing until you
press **Apply**. Rows the sheet does not mention are left alone, and a row
whose name matches no case type is reported rather than applied.

**Does the No Content countdown pause when I lock my PC?**
No, deliberately. It runs on the same suspend-aware clock as the case timer,
so stepping away does not stop the alarm you asked for. Press **Content** to
end the wait.

**Can I delete everything?**
*Dev Mode → Data → Erase all data*, or just delete the data folder.

---

## Problems

**Windows SmartScreen says "unrecognised app".**
Expected for any newly built, unsigned executable. SmartScreen is a
*reputation* check — how many people have downloaded this exact file and
whether it is signed — not a malware verdict. Click *More info → Run anyway*.
It goes away for good only with a code-signing certificate; see
[IT-APPROVAL.md](IT-APPROVAL.md).

**Antivirus flagged it, and IT thinks it is a virus.**
A known false-positive class for unsigned PyInstaller binaries. Three things
help, in order:

1. **Use `CheckMod-folder.zip` instead of the single exe.** The one-file build
   unpacks itself into `%TEMP%` at launch and runs from there — behaviour that
   resembles a dropper. The folder build extracts nothing, which removes the
   trigger. It also starts instantly.
2. **Give IT the hash.** Every release ships `SHA256SUMS.txt` so the exact
   build can be allow-listed rather than granted a blanket exception.
3. **Build it in-house**, or skip the binary and run from source — nothing to
   approve beyond Python itself.

[IT-APPROVAL.md](IT-APPROVAL.md) is a one-page summary written for whoever
approves software on your machines: what it does, what it touches, why the
warning appears, and how to verify every claim.

**Which download should my team use?**
`CheckMod-folder.zip` — it is the only one. Unzip anywhere and run the exe
inside. Releases used to also carry a single-file build; it was the same
application and only made people ask which to pick, so it is no longer
published. `packaging/CheckMod.spec` still builds one locally if you want it.

**Nothing happens when I double-click the exe.**
Wait a couple of seconds: a one-file build unpacks itself before starting.
If it still does not appear, run it from a terminal to see the error, or run
from source with `python -m checkmod`.

**`ModuleNotFoundError: No module named 'tkinter'` when running from source.**
Tk is a separate package on Linux: `sudo apt install python3-tk`. On Windows,
re-run the Python installer and tick *tcl/tk and IDLE*.

**I made the window small and now I cannot resize it.**
Fixed in 1.1.0 — the footer holding the resize grip was being squeezed to zero
height. If you are on an older build, drag the window bigger from *Dev Mode →
Window → Centre window*, or delete `settings.json` from the data folder to
reset its geometry.

**The top bar looks cut off / the title is squashed against the top edge.**
Fixed in 1.0.1. The bar was a hard-coded 34 px, which is too short once
Windows display scaling is above 125% — and the frozen exe is DPI-aware, so it
sees the real scaling. The bar now sizes itself from the font metrics. If you
are on 1.0.0, updating fixes it; raising or lowering *Dev Mode → Style → Text
scale* is the workaround.

**The text is too small / too large.**
*Dev Mode → Style → Text scale* (0.8× – 1.4×). The window resizes itself to
fit, so nothing gets clipped.

**My settings vanished.**
If the file could not be parsed it is renamed to
`settings.json.broken-<timestamp>` in the data folder rather than deleted,
and defaults are loaded. The original is still there to inspect.

**I chose a custom alarm and it was rejected.**
Only WAV files are accepted, up to 30 seconds. Windows plays WAV with no extra
software; an MP3 or M4A would be accepted at the file picker and then fail
silently at the moment the alarm was due, which is worse than a refusal.
Convert it (any audio tool, or Windows Sound Recorder) and pick it again.

**My custom alarm stopped working after I tidied my Downloads folder.**
It should not have: the file is copied into the CheckMod data folder when you
choose it, precisely so the original can move. If the copy itself was deleted,
the app falls back to the default alert rather than going silent — re-pick the
file to restore it.

**The sheet sync button does nothing.**
It is disabled until a sheet link is saved. Type the link into *Dev Mode →
Data → AHT sheet → Sheet link* and press Enter first; the button enables and
the label under it shows when the last sync happened.

**The statistics are empty.**
Either no case has been completed yet, or *Dev Mode → Data → Keep local
history* is off.

**Can several people share one settings file?**
Yes — export it from one machine and import it on the others (*Dev Mode →
Data*), or point everyone at a shared folder with the `CHECKMOD_DATA_DIR`
environment variable. Import merges, so personal preferences survive.

---

## Development

**How do I run the tests?**

```bash
python -m pip install pytest
python -m pytest tests/ -v              # add xvfb-run -a on headless Linux
```

**How do I add a theme, a setting or a tutorial step?**
See the extension-points table in [ARCHITECTURE.md](ARCHITECTURE.md#extension-points).

**Why Tkinter and not Electron or Qt?**
Electron would be a ~150 MB download for a checklist. Qt adds a large
dependency and licensing questions. Tkinter ships with Python, keeps the
frozen binary around 12 MB and the runtime dependency list empty — which is
what makes the app easy to approve. The stock widgets are ugly, so every
control here is drawn on a canvas instead; see
[ARCHITECTURE.md](ARCHITECTURE.md#the-widget-toolkit).

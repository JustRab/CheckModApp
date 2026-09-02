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

**Why is there no minimise button?**
The window has no OS decorations — that is what lets it be a small, identical
floating panel on every machine — so there is no taskbar entry to minimise
into. Use the compact layout instead (`Ctrl+M`, the **—** button, or a
double-click on the title bar), or turn *Dev Mode → Window → Custom title
bar* off to get the native chrome back.

**It disappeared behind another window.**
Check the pin button in the title bar: filled means always-on-top is on,
hollow means off. `Ctrl+T` toggles it.

**I dragged it off-screen / changed monitors and cannot find it.**
It clamps itself back on screen at launch. If it is still awkward, use *Dev
Mode → Window → Centre window*.

**Can I change the AHT targets?**
Yes, in two places: click the `Target 05:00 ✎` pill under the timer, or use
*Dev Mode → AHT*. Type `5` for five minutes, or `05:30` for five and a half.

**Can I add my own case types or checklist items?**
Yes — *Dev Mode → AHT* and *Dev Mode → Checks*. Add, rename, recolour,
describe, reorder, disable or delete anything, including the four defaults.

**Does the timer keep running if I switch case type mid-case?**
Yes. Elapsed time is kept and only the target changes, because reclassifying
a case part-way through is normal.

**What happens to paused time?**
It is excluded from the logged AHT by default. *Dev Mode → Rules → Count
paused time* includes it.

**Does it track me?**
No. See [PRIVACY.md](PRIVACY.md). No network code, no telemetry, and the
record schema has no field for anything that identifies a person or a case.

**Can I delete everything?**
*Dev Mode → Data → Erase all data*, or just delete the data folder.

---

## Problems

**Windows SmartScreen says "unrecognised app".**
Expected for an unsigned executable. Click *More info → Run anyway*, or see
[BUILD.md](BUILD.md#antivirus-and-smartscreen) for signing, hash
allow-listing, and running from source instead.

**Antivirus flagged it.**
A known false-positive class for unsigned PyInstaller binaries. The build
avoids UPX compression, which is the usual trigger. The most reliable answer
in a corporate setting is to build it in-house from this repository — see
[BUILD.md](BUILD.md).

**Nothing happens when I double-click the exe.**
Wait a couple of seconds: a one-file build unpacks itself before starting.
If it still does not appear, run it from a terminal to see the error, or run
from source with `python -m checkmod`.

**`ModuleNotFoundError: No module named 'tkinter'` when running from source.**
Tk is a separate package on Linux: `sudo apt install python3-tk`. On Windows,
re-run the Python installer and tick *tcl/tk and IDLE*.

**The text is too small / too large.**
*Dev Mode → Style → Text scale* (0.8× – 1.4×). The window resizes itself to
fit, so nothing gets clipped.

**My settings vanished.**
If the file could not be parsed it is renamed to
`settings.json.broken-<timestamp>` in the data folder rather than deleted,
and defaults are loaded. The original is still there to inspect.

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

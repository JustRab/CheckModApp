# CheckMod — summary for IT / security review

One page to hand to whoever approves software on your machines. Every claim
links to the file that proves it; nothing here has to be taken on trust.

---

## What it is

A desktop checklist and stopwatch for Trust & Safety moderators. It floats on
top of the moderation tools, times each case against an Average Handle Time
target, and tracks four adherence checks. Roughly 5 000 lines of Python with
**no third-party runtime dependencies**.

Source: <https://github.com/JustRab/CheckModApp>

---

## The short answers

| Question | Answer |
|---|---|
| Installer? | **None.** Copy a file or a folder; run it. |
| Administrator rights? | **Never** — not to install, run, update or build. |
| Registry changes? | **None.** |
| Services, drivers, scheduled tasks, start-up entries? | **None.** |
| Network connections? | **None.** No networking module is imported, and networking is excluded from the build. |
| Telemetry / analytics / crash reporting? | **None.** |
| Auto-update? | **None.** The binary never modifies itself. |
| Keyboard hooks or screen capture? | **None.** Shortcuts bind to its own window only. |
| Personal data stored? | **None.** No names, user IDs, case references or free text. |
| Where does it write? | Two plain-text files in `%APPDATA%\CheckMod`, or a folder beside the executable in portable mode. |
| Uninstall | Delete the file and the data folder. That is all. |
| Licence | MIT |

---

## Why it may trigger a warning anyway

CheckMod is an **unsigned** executable produced by PyInstaller. Two
consequences, both expected and neither an indicator of malware:

**1. Windows SmartScreen — "Windows protected your PC / unrecognised app".**
SmartScreen is a *reputation* check, not a malware verdict. Any newly built,
unsigned binary that few people have downloaded produces it. It disappears
when the file is signed with a certificate from a trusted CA, or once the
build accumulates download reputation.

**2. Heuristic antivirus flags.**
The one-file build unpacks itself into `%TEMP%` at launch and executes from
there. That behaviour resembles a dropper, so some engines flag it
generically (`Wacatac`, `Occamy`, `Generic.Trojan` and similar names).

The build deliberately avoids the things that make this worse: it does **not**
use UPX compression, does **not** bundle an updater, and ships full Windows
version metadata.

---

## What to do about it — in order of preference

### 1. Use the one-folder distribution

`CheckMod-folder.zip` on the [Releases](https://github.com/JustRab/CheckModApp/releases)
page is a plain folder holding `CheckMod.exe` next to its libraries. It
**does not extract anything at runtime**, which removes the behaviour most
heuristics react to. It also starts instantly. Unzip anywhere and run the exe
inside — still portable, still no admin rights.

*This is the recommended distribution for a managed machine.*

### 2. Allow-list by hash

Every release ships `SHA256SUMS.txt`. Verify before allow-listing:

```powershell
Get-FileHash .\CheckMod.exe -Algorithm SHA256
```

### 3. Build it in-house

The most convincing option, and it needs no admin rights. Any machine with
Python 3.9+:

```powershell
git clone https://github.com/JustRab/CheckModApp.git
cd CheckModApp
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

The binary you distribute is then one your own team compiled from source you
can read.

### 4. Sign it

With an organisational code-signing certificate:

```powershell
signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 /a CheckMod.exe
```

The release workflow signs automatically when the repository provides
`WINDOWS_CERT_PFX_BASE64` and `WINDOWS_CERT_PASSWORD` secrets. An EV
certificate clears SmartScreen immediately; an OV certificate clears it as
reputation accrues.

### 5. Skip the binary entirely

CheckMod runs from source with no build step:

```
python -m checkmod
```

or double-click `CheckMod.pyw`. Nothing to approve beyond Python itself,
which is usually already sanctioned.

---

## Verifying the claims

```bash
# No networking anywhere in the application
grep -rnE "import (socket|ssl|http|urllib|requests|smtplib|ftplib)" checkmod/
# -> no matches

# Every subprocess call (there is exactly one: "open the data folder")
grep -rn "subprocess\|os.system\|startfile" checkmod/

# What is deliberately kept out of the binary
grep -A20 "^EXCLUDES" packaging/build_config.py
```

Suggested reading order for a code review:

1. `checkmod/paths.py` — every location the app may write to
2. `checkmod/history.py` — every write of case data
3. `checkmod/session.py` — the record schema (`Session.snapshot`)
4. `checkmod/config.py` — settings persistence
5. `packaging/build_config.py` — what is and is not packaged

The record schema is enforced by a test
(`test_snapshot_captures_aggregates_and_no_identifying_data`), so a future
change that added a personal-data field would fail CI.

Full detail: [PRIVACY.md](PRIVACY.md).

---

## Data handling summary

One record per completed case, appended to a local JSON Lines file:

```json
{"ts": 1767225600, "case_id": "voice", "case_name": "Voice Chat",
 "duration_s": 884, "target_s": 900, "paused_s": 0,
 "checks": {"escalation": true, "enforcement": true,
            "evidence": true, "comment": false},
 "cleared": 3, "total_checks": 4, "within_target": true}
```

No field identifies a person, a case, a subject or a reporter, and the
application offers no way to enter one. History can be switched off entirely,
is pruned after 30 days by default, and is erased by a single button in the
app.

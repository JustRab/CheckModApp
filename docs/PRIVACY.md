# Privacy & security statement

CheckMod is intended to run on managed corporate workstations belonging to
Trust & Safety agents. This document is written for the person who has to
approve that — an IT administrator, a security reviewer, or a team lead who
needs to answer "what does this thing actually do?".

Every claim below is verifiable from the source in this repository, and each
one names the file to check.

---

## Summary

| Question | Answer |
|---|---|
| Does it connect to the internet? | **No.** No networking module is imported, and networking modules are excluded from the build. |
| Does it send telemetry, analytics or crash reports? | **No.** None exists. |
| Does it auto-update? | **No.** The binary never changes itself. |
| Does it store personal data? | **No.** No names, IDs, case references or free text — the record schema has no field for them. |
| Does it require administrator rights? | **No.** Ever. |
| Does it install anything? | **No.** No installer, no registry keys, no services, no scheduled tasks, no start-up entries. |
| Does it hook the keyboard or read other windows? | **No.** Shortcuts are bound to its own window only. |
| Where does data live? | Two plain-text files in a folder you choose. |
| Can the user delete everything? | **Yes**, with one button, or by deleting one folder. |
| Third-party dependencies at runtime? | **None.** Python standard library only. |

---

## 1. No network access

The application performs no network I/O of any kind. There is no HTTP client,
no socket, no DNS lookup, no update check, no analytics beacon.

**How to verify**

```bash
# No networking imports anywhere in the application.
grep -rnE "import (socket|ssl|http|urllib|requests|smtplib|ftplib)" checkmod/
# -> no matches
```

The build goes one step further. `packaging/CheckMod.spec` lists
`socket`, `ssl`, `http`, `urllib.request`, `smtplib`, `ftplib`, `telnetlib`
and `asyncio` in its `excludes`, so those modules are **not packaged into the
executable at all**. The capability is absent, not merely unused.

---

## 2. No installation, no elevation

- Distributed as a single portable executable. There is no MSI, no setup
  program, no elevation prompt.
- Nothing is written to `HKEY_LOCAL_MACHINE`, `C:\Program Files`,
  `C:\Windows`, the Start-up folder or the Task Scheduler.
- No service, driver or scheduled task is registered.
- The app writes only to the folder described in section 4 — a location the
  user already has write access to.

A one-file PyInstaller build unpacks itself into the user's temporary folder
at launch and cleans up on exit. That is the only other path it touches.

**How to verify** — `checkmod/paths.py` is the single module that resolves
writable locations; every write in the codebase goes through it.

---

## 3. What is recorded

One record is appended per completed case. This is the complete schema
(`Session.snapshot` in `checkmod/session.py`):

```json
{
  "ts": 1767225600,
  "case_id": "voice",
  "case_name": "Voice Chat",
  "duration_s": 284,
  "target_s": 300,
  "paused_s": 0,
  "checks": {"escalation": true, "enforcement": true,
             "evidence": true, "comment": false},
  "cleared": 3,
  "total_checks": 4,
  "within_target": true
}
```

There is **no field** for a case identifier, ticket number, user name, agent
ID, subject, reported user, policy reference or free-text note — and the app
provides no way to enter one. It cannot leak what it never collects.

The unit test `test_snapshot_captures_aggregates_and_no_identifying_data` in
`tests/test_session.py` asserts the exact key set, so a future change that
added a personal-data field would fail CI.

**History can also be switched off entirely** in *Dev Mode → Data → Keep local
history*. The timer and checklist keep working; nothing is written.

---

## 4. Where data is stored

Two files, both plain text, both readable in Notepad:

| File | Contents |
|---|---|
| `settings.json` | Your preferences, case types and checklist items |
| `history.jsonl` | One JSON object per completed case (see above) |

Location, resolved in this order (`checkmod/paths.py`):

1. `%CHECKMOD_DATA_DIR%` if that environment variable is set — lets an
   administrator place the data on a specific drive or profile path.
2. **Portable mode** — `CheckModData\` next to the executable, active only
   while a marker file named `checkmod.portable` sits beside it. Toggle it
   from *Dev Mode → Data*.
3. Otherwise the per-user application-data folder:
   - Windows: `%APPDATA%\CheckMod`
   - macOS: `~/Library/Application Support/CheckMod`
   - Linux: `~/.config/CheckMod`

If the preferred location turns out to be read-only, the app silently falls
back to the per-user folder rather than failing or asking for elevation.

Dev Mode shows the resolved path on screen and can open it in the file
manager.

---

## 5. Retention and deletion

- History older than the retention window (30 days by default, configurable
  from 1 day to unlimited) is pruned automatically on start-up.
- The log is hard-capped at 20 000 records regardless of settings.
- **Dev Mode → Data → Erase all data** deletes the history and restores
  factory settings immediately.
- Deleting the data folder by hand achieves the same thing. The app recreates
  defaults on next launch.

---

## 6. No keyboard hooks, no screen reading

All keyboard shortcuts are Tk bindings on CheckMod's own window
(`App._bind_shortcuts` in `checkmod/app.py`). The app:

- installs **no** global/low-level keyboard hook,
- reads **no** other application's window contents,
- takes **no** screenshots,
- captures **no** clipboard data.

This is a deliberate design constraint, not an omission: a global hook is
exactly the kind of behaviour that requires elevated privileges and triggers
endpoint-security alerts.

---

## 7. Supply chain

The application imports **only the Python standard library**. There is no
`pip install` step for end users and no third-party package inside the
executable.

The only build-time dependency is PyInstaller, which contributes a bootloader
to the binary. `requirements-dev.txt` lists it and pytest; neither is a
runtime dependency.

The icon is generated from source code (`tools/make_icon.py`, standard
library only) rather than shipped as an opaque binary blob you have to trust.

---

## 8. Auditing this repository

The whole application is roughly 5 000 lines of commented Python. A reviewer
can read all of it. Suggested order:

1. `checkmod/paths.py` — every writable location the app can resolve.
2. `checkmod/history.py` — every write to disk of case data.
3. `checkmod/session.py` — the record schema.
4. `checkmod/config.py` — settings persistence.
5. `packaging/CheckMod.spec` — what is and is not packaged.

Useful checks:

```bash
# Networking
grep -rnE "socket|urllib|requests|http\.client" checkmod/

# Subprocess use (there is exactly one: "open the data folder" in Dev Mode)
grep -rn "subprocess\|os.system\|startfile" checkmod/

# Every file write
grep -rn "open(" checkmod/ | grep -v '"r"'
```

---

## 9. Notes for endpoint protection

An unsigned, freshly built executable that unpacks itself at launch can trip
heuristic antivirus rules. This is a well-known PyInstaller behaviour, not a
property of this application. `docs/BUILD.md` covers the options: building
in-house, code signing, or shipping the one-folder layout instead. The build
deliberately does **not** use UPX compression, which is the single biggest
cause of these false positives.

---

## 10. Contact

Issues and questions belong in this repository's issue tracker. There is no
telemetry channel, no support server and no phone-home path through which the
app could report anything back.

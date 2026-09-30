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
| Does it connect to the internet? | **Only if you ask it to, and only to one place.** With no AHT sheet configured — the shipped default — nothing on the network is touched. Configure a Google Sheets link and the Sync button performs one HTTPS `GET` of that sheet. See section 1. |
| Does anything leave the machine? | **No.** There is no upload path anywhere in the code: no `POST`, no file upload, no request body. Settings, history and case data never leave the computer. |
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

## 1. Network access: one optional, user-initiated read

CheckMod has exactly one feature that uses a network, and it is off until
somebody configures it.

**What it is.** Weekly AHT targets are published by a team lead in a Google
Sheet. Rather than retyping them, a moderator can paste that sheet's link into
*Dev Mode → Data → AHT sheet* and press **Sync targets from the sheet**.

**What it does, precisely** — all of this is in `checkmod/sheets.py`, which is
under 300 lines and is the only module involved:

| Property | Guarantee | Where |
|---|---|---|
| Off by default | Shipped with `aht_sheet_url` empty. With no link configured, the networking module is never even imported — the `import urllib.request` lives *inside* the fetch function. | `checkmod/config.py`, `sheets.fetch` |
| User-initiated | No polling, no timer, no background thread waiting to fire. One button press, one request. | `App.sync_aht_from_sheet` |
| Read-only | One HTTPS `GET`. No request body, no `POST`, no upload of any kind. | `sheets.fetch` |
| Nothing identifying is sent | No cookies, no credentials, no `Authorization` header, no machine or user name. The only header is `User-Agent: CheckMod`. | `sheets.fetch`, `tests/test_sheets.py` |
| Google only | The link must be an HTTPS `docs.google.com` spreadsheet URL, and a redirect is followed only to Google's own file host. A configured URL cannot be turned into a request anywhere else. | `sheets.ALLOWED_HOSTS`, `sheets.csv_url` |
| Bounded | Ten-second timeout, 512 KiB read cap. | `sheets.TIMEOUT`, `sheets.MAX_BYTES` |
| Nothing is written blindly | The numbers read from the sheet are shown next to the current ones, and applied only when the user accepts them. | `App._offer_sheet_rows` |

**What it is not.** No telemetry, no analytics, no crash reporting, no
auto-update, no licence check, no account, no sign-in. None of those exist in
the codebase, and no code path sends anything outward.

**How to verify**

```bash
# Every network-capable import in the application - there are four, all in
# one module, and all inside the function that performs the fetch:
grep -rnE "import (socket|ssl|http|urllib|requests|smtplib|ftplib)" checkmod/
# -> checkmod/sheets.py only

# Nothing uploads: no POST, no request body, no upload helper anywhere.
grep -rniE "urlopen\(|\bPOST\b|data=|files=|upload" checkmod/sheets.py
# -> only `seen["data"] is None`-style assertions live in the tests
```

The build bounds this too. `packaging/build_config.py` still excludes
`smtplib`, `ftplib`, `poplib`, `imaplib`, `telnetlib`, `nntplib`, `xmlrpc`,
`http.server`, `socketserver`, `wsgiref` and `asyncio`, so the executable
cannot send mail, serve anything, or speak any protocol other than the HTTPS
`GET` above. `urllib.request` and `ssl` ship from 1.4.0 onward because the
sheet sync needs them; before 1.4.0 no networking module was packaged at all.

**If your policy does not allow it.** Leave the sheet link empty and the
feature never runs. Nothing else in the app depends on it: targets can be
typed in Dev Mode exactly as before. A deployment can also be verified from
the settings file — `aht_sheet_url` empty means the feature is inert.

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
  "duration_s": 884,
  "target_s": 900,
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
5. `checkmod/sheets.py` — the only module that can open a socket.
6. `packaging/build_config.py` — what is and is not packaged.

Useful checks:

```bash
# Networking - expect matches in checkmod/sheets.py and nowhere else
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
app could report anything back. The only outbound request it can make is the
sheet read in section 1, which asks Google for a document and tells it nothing
about you or your work.

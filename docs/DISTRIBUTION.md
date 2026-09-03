# Sharing CheckMod without making the repository public

A private repository is the right default for anything built inside a Trust &
Safety org. This document covers how to get the app to colleagues anyway.

**The short answer:** hand them `CheckMod-folder.zip` from the release. It is
the whole app, and nobody needs repository access to use it.

---

## Why a private repo complicates it

GitHub release assets on a **private** repository are not public downloads —
anyone fetching one still has to authenticate and still needs read access to
the repo. So "just send them the release link" does not work: they will get a
404. The repository itself never needs to be shared, though; only the built
artifact does.

---

## Recommended: send the release zip

Every release publishes **`CheckMod-folder.zip`**. Inside:

```
CheckMod/
├── CheckMod.exe      double-click this
└── _internal/        its libraries
```

Download it once from the release page, then distribute it by whatever channel
your organisation already trusts:

| Channel | Notes |
|---|---|
| **OneDrive / SharePoint / Teams** | Usually the best fit: already sanctioned, already access-controlled, and keeps an audit trail. |
| **Network share** | Drop the unzipped folder on a team share; people copy it locally and run it. |
| **Email** | Works, but many gateways strip or quarantine archives containing an `.exe`. Prefer a link. |
| **USB stick** | Fine — turn on portable mode so settings travel with it (*Dev Mode → Data → Portable mode*). |

Ask recipients to unzip it and run `CheckMod\CheckMod.exe`. Nothing is
installed and no administrator rights are required; a short tutorial opens on
first run.

Worth sending alongside it, once: **[IT-APPROVAL.md](IT-APPROVAL.md)** — one
page for whoever approves software, covering what the app touches, why Windows
may warn about an unsigned binary, and how to verify every claim.

## Verifying what you sent

Each build also publishes `SHA256SUMS.txt`. Recipients — or IT — can confirm
the file matches what CI produced:

```powershell
Get-FileHash .\CheckMod-folder.zip -Algorithm SHA256
```

This matters more when the file travels by email or USB than when it comes
straight from the pipeline.

---

## Other options

### Give collaborators read access to the private repo

The simplest path if the people involved are already inside your org: add them
as repository collaborators, and they can download release assets normally.
Sharing the *repo* is not the same as making it *public*.

### Build it on the recipient's machine

Anyone with Python 3.9+ can produce their own binary — no admin rights
needed. See [BUILD.md](BUILD.md). Some IT departments prefer this because the
binary is then one they compiled from source they can read.

### Run from source, no binary at all

```
python -m checkmod
```

or double-click `CheckMod.pyw`. Nothing to approve beyond Python itself, which
is often already sanctioned on a developer or analyst machine.

### If you ever do make the repo public

Nothing in this repository contains credentials, internal hostnames, policy
text or case data — the app has no network code and records no personal
data (see [PRIVACY.md](PRIVACY.md)). The data-leak risk of publishing would
come from anything *you* add later: real case examples in the checklist hints,
internal queue names in the case types, or an exported `history.jsonl`. Note
that `.gitignore` already excludes `settings.json`, `history.jsonl` and the
`CheckModData/` folder, so local data cannot be committed by accident.

Keeping it private is still the safer default; the release zip exists so that
costs you nothing.

---

## Rolling out a team-wide configuration

Shipping the app is separate from shipping *your* case types, AHT targets and
checklist wording. To standardise those:

1. Configure one machine exactly as you want it.
2. *Dev Mode → Data → **Export settings*** → `checkmod-settings.json`.
3. Put that file alongside the zip you distribute.
4. Each person: *Dev Mode → Data → **Import settings***.

Import merges onto existing settings, so personal preferences such as theme
and window position survive. See
[CUSTOMIZATION.md](CUSTOMIZATION.md#team-wide-presets).

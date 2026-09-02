# Building CheckMod

The application runs straight from source; building is only needed to
produce the portable executable you hand to other people.

**No administrator rights are required to build.** The scripts create a
virtual environment inside the repository folder and install PyInstaller
there — nothing goes into the system Python or `Program Files`.

---

## Requirements

| | |
|---|---|
| Python | 3.9 or newer, on `PATH` |
| Tk | Included with the official Windows and macOS installers. On Debian/Ubuntu: `sudo apt install python3-tk` |
| PyInstaller | Installed automatically by the build scripts |

---

## Windows

```powershell
git clone https://github.com/JustRab/CheckModApp.git
cd CheckModApp
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Or double-click **`packaging\build_windows.bat`**, which is the same thing
wrapped for people who would rather not open a terminal.

Two distributions are produced:

| Output | What it is | When to use it |
|---|---|---|
| `dist\CheckMod.exe` | One file, ~12 MB | Convenience. Copy it anywhere and double-click. |
| `dist-folder\CheckMod\` | One folder: the exe beside its libraries | **Managed corporate machines.** Nothing is extracted to `%TEMP%` at launch, so heuristic antivirus has much less to object to, and start-up is instant. |

Both are portable and neither needs administrator rights.

Options:

```powershell
# Use a specific interpreter
powershell -File packaging\build_windows.ps1 -Python "C:\Python311\python.exe"

# Skip regenerating the icon, or skip the one-folder build
powershell -File packaging\build_windows.ps1 -SkipIcon -SkipFolder
```

The script prints the SHA-256 of the executable so it can be allow-listed.

## Linux / macOS

```bash
./packaging/build_linux.sh          # -> dist/CheckMod
PYTHON=python3.12 ./packaging/build_linux.sh
```

This is mainly useful for validating the build recipe on CI. PyInstaller
**cannot cross-compile**: a Windows `.exe` must be produced on Windows.

## By hand

```bash
python -m pip install "pyinstaller>=6.3"
python tools/make_icon.py
python -m PyInstaller packaging/CheckMod.spec --noconfirm --clean
python -m PyInstaller packaging/CheckModFolder.spec --noconfirm --clean --distpath dist-folder
```

Both specs share `packaging/build_config.py`, so the exclude list — which is a
privacy guarantee, not just a size optimisation — cannot drift between them.

---

## Continuous integration

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/tests.yml` | every push and pull request | Runs the full suite on Python 3.9, 3.11 and 3.12, under `xvfb` so the interface tests run too; byte-compiles every module; re-runs the icon generator |
| `.github/workflows/build.yml` | tags matching `v*` or `[0-9]*`, or manually | Builds both distributions on a Windows runner, signs them if a certificate is configured, writes `SHA256SUMS.txt`, uploads everything as an artifact and attaches it to the GitHub release |

### Optional code signing

If your organisation has a code-signing certificate, add two repository
secrets and the workflow signs both executables automatically:

| Secret | Value |
|---|---|
| `WINDOWS_CERT_PFX_BASE64` | The `.pfx` file, base64-encoded (`certutil -encode cert.pfx cert.txt`) |
| `WINDOWS_CERT_PASSWORD` | Its password |

Without them the step is skipped and the build proceeds unsigned, so forks
keep working.

To cut a release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The executable appears on the Releases page a few minutes later.

---

## What is inside the executable

`packaging/CheckMod.spec` is commented in full. The decisions that matter:

| Setting | Why |
|---|---|
| one-file **and** one-folder builds | The single file is the convenient default; the folder is what a locked-down machine should get, because it never extracts itself to `%TEMP%` |
| `console=False` | No terminal window flashing behind the floating UI |
| `upx=False` | UPX packing is the single biggest cause of antivirus false positives on PyInstaller output. A few megabytes are not worth the support tickets. |
| `excludes=[...]` | Drops standard-library modules the app never imports — including `socket`, `ssl`, `http` and `urllib.request`. This halves the binary and makes "it cannot reach the network" a structural fact rather than a promise. |
| `version_info.txt` | Fills in the Windows *Properties → Details* tab. IT looks there first when an unsigned binary shows up on a workstation. |
| generated icon | `tools/make_icon.py` builds the `.ico` from code, so the mark can be recoloured without an image editor |

---

## Antivirus and SmartScreen

A freshly built, unsigned PyInstaller executable that unpacks itself into the
temporary folder at launch can trigger heuristic detections and a Windows
SmartScreen "unrecognised app" prompt. This is a property of unsigned frozen
Python binaries in general, not of this application.

**The short version: hand out `CheckMod-folder.zip` rather than the single
exe.** It does not extract itself at runtime, which removes the behaviour most
heuristics react to. It does not, however, remove the SmartScreen prompt —
that is a reputation check on the file's signature and download history, not
on its behaviour.

[docs/IT-APPROVAL.md](IT-APPROVAL.md) is a one-page summary written for
whoever approves software on your machines.

Options, in increasing order of effort:

0. **Ship the one-folder distribution** (`CheckMod-folder.zip`). Cheapest
   meaningful improvement, and it also starts faster.
1. **Build it in-house.** Clone the repository, run the build script, and
   distribute the executable you produced yourself. Reviewing ~5 000 lines of
   dependency-free Python is entirely feasible — [PRIVACY.md §8](PRIVACY.md#8-auditing-this-repository)
   suggests a reading order.
2. **Run from source.** No binary at all: `python -m checkmod`, or
   double-click `CheckMod.pyw`. Some teams find this the easiest approval.
3. **Sign it.** With an organisational code-signing certificate:
   ```powershell
   signtool sign /tr http://timestamp.digicert.com /td sha256 `
                 /fd sha256 /a dist\CheckMod.exe
   ```
   Signing removes both the SmartScreen prompt and most heuristic flags.
4. **Ask IT to allow-list the hash.** Publish the SHA-256 alongside the
   binary:
   ```powershell
   Get-FileHash dist\CheckMod.exe -Algorithm SHA256
   ```

The build deliberately avoids the two things that make this worse: UPX
compression and a bundled updater.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'tkinter'`**
Tk is not installed for that interpreter. Debian/Ubuntu:
`sudo apt install python3-tk`. On Windows, re-run the Python installer and
tick *tcl/tk and IDLE*.

**The build succeeds but the executable does nothing**
Build a console variant to see the traceback: set `console=True` in
`packaging/CheckMod.spec`, rebuild, and run it from a terminal.

**"Failed to execute script launcher"**
Usually an over-aggressive `excludes` entry. Comment out the `excludes` list
in the spec, rebuild, and re-add entries until you find the culprit.

**The build produced only `dist/CheckMod.exe` and no folder**
The one-folder spec writes to `dist-folder/` so the two layouts cannot
overwrite each other. Pass `--distpath dist-folder` if invoking PyInstaller
by hand.

**The executable is much larger than 12 MB**
Something extra was picked up from the build environment. Build inside a
clean virtual environment — which is what the supplied scripts do.

**First launch is slow**
Expected for a one-file build: it unpacks itself into `%TEMP%` before
starting. Use the one-folder distribution instead — it starts immediately.

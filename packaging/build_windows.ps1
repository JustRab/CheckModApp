<#
.SYNOPSIS
    Build the portable CheckMod.exe on Windows.

.DESCRIPTION
    Creates a throw-away virtual environment, installs PyInstaller into it and
    produces dist\CheckMod.exe - a single, self-contained, portable binary.

    Nothing here needs administrator rights: the venv lives in the repository
    folder and pip installs only into that venv.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipIcon
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> CheckMod build" -ForegroundColor Cyan
Write-Host "    root: $Root"

# 1. Isolated build environment ------------------------------------------------
$Venv = Join-Path $Root ".buildenv"
if (-not (Test-Path $Venv)) {
    Write-Host "==> creating build virtualenv" -ForegroundColor Cyan
    & $Python -m venv $Venv
}
$VenvPython = Join-Path $Venv "Scripts\python.exe"

Write-Host "==> installing PyInstaller" -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install "pyinstaller>=6.3" --quiet

# 2. Icon ----------------------------------------------------------------------
if (-not $SkipIcon) {
    Write-Host "==> generating icon" -ForegroundColor Cyan
    & $VenvPython (Join-Path $Root "tools\make_icon.py")
}

# 3. Freeze --------------------------------------------------------------------
Write-Host "==> running PyInstaller" -ForegroundColor Cyan
& $VenvPython -m PyInstaller (Join-Path $Root "packaging\CheckMod.spec") --noconfirm --clean

$Exe = Join-Path $Root "dist\CheckMod.exe"
if (Test-Path $Exe) {
    $SizeMb = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
    Write-Host ""
    Write-Host "==> done: $Exe ($SizeMb MB)" -ForegroundColor Green
    Write-Host "    Copy it anywhere and double-click. No installation required."
} else {
    Write-Error "Build finished but $Exe was not produced."
    exit 1
}

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
    [switch]$SkipIcon,
    [switch]$SkipFolder
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
Write-Host "==> running PyInstaller (one file)" -ForegroundColor Cyan
& $VenvPython -m PyInstaller (Join-Path $Root "packaging\CheckMod.spec") --noconfirm --clean

if (-not $SkipFolder) {
    Write-Host "==> running PyInstaller (one folder)" -ForegroundColor Cyan
    & $VenvPython -m PyInstaller (Join-Path $Root "packaging\CheckModFolder.spec") `
        --noconfirm --clean --distpath (Join-Path $Root "dist-folder")
}

$Exe = Join-Path $Root "dist\CheckMod.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "Build finished but $Exe was not produced."
    exit 1
}

$SizeMb = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
$Hash = (Get-FileHash $Exe -Algorithm SHA256).Hash.ToLower()
Write-Host ""
Write-Host "==> one file:   $Exe ($SizeMb MB)" -ForegroundColor Green
Write-Host "    SHA256: $Hash"

$Folder = Join-Path $Root "dist-folder\CheckMod"
if (Test-Path $Folder) {
    Write-Host "==> one folder: $Folder" -ForegroundColor Green
    Write-Host "    Preferred on managed machines: it does not extract itself to %TEMP%."
}
Write-Host ""
Write-Host "    Neither layout needs installation or administrator rights."

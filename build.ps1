param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    python -m venv (Join-Path $root ".venv")
}

& $python -m pip install --upgrade pip
& $python -m pip install -e "${root}[dev]"

if ($Clean) {
    Remove-Item -Recurse -Force (Join-Path $root "build") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $root "dist") -ErrorAction SilentlyContinue
}

Push-Location $root
try {
    & $python -m PyInstaller .\LongYinModInstaller.spec --noconfirm --clean
}
finally {
    Pop-Location
}

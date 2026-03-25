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

    $distDir = Join-Path $root "dist"
    Copy-Item (Join-Path $root "catalog_sources.example.json") (Join-Path $distDir "catalog_sources.example.json") -Force
    Copy-Item (Join-Path $root "catalog_sources.example.json") (Join-Path $distDir "catalog_sources.json") -Force

    $targetRepoDir = Join-Path $distDir "mod_repository"
    if (Test-Path $targetRepoDir) {
        Remove-Item -Recurse -Force $targetRepoDir
    }
    Copy-Item (Join-Path $root "mod_repository") $targetRepoDir -Recurse -Force
}
finally {
    Pop-Location
}

param(
    [switch]$Clean,
    [string]$GameDirectory = "E:\SteamLibrary\steamapps\common\LongYinLiZhiZhuan",
    [switch]$SkipDependencyArchive
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"

function New-DependencyArchive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDirectory,
        [Parameter(Mandatory = $true)]
        [string]$DestinationArchive
    )

    if (-not (Test-Path -LiteralPath $SourceDirectory -PathType Container)) {
        throw "Dependency source directory not found: $SourceDirectory"
    }

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $sourceItem = Get-Item -LiteralPath $SourceDirectory
    $tempArchive = "$DestinationArchive.tmp"
    if (Test-Path -LiteralPath $tempArchive) {
        Remove-Item -LiteralPath $tempArchive -Force
    }

    $archive = [System.IO.Compression.ZipFile]::Open($tempArchive, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $rootPrefix = "$($sourceItem.Name)/"
        $null = $archive.CreateEntry($rootPrefix)

        Get-ChildItem -LiteralPath $sourceItem.FullName -Recurse -Force |
            Sort-Object FullName |
            ForEach-Object {
                $relativePath = $_.FullName.Substring($sourceItem.FullName.Length).TrimStart([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
                $entryName = $rootPrefix + ($relativePath -replace "\\", "/")

                if ($_.PSIsContainer) {
                    if (-not $entryName.EndsWith("/")) {
                        $entryName += "/"
                    }
                    $null = $archive.CreateEntry($entryName)
                }
                else {
                    $null = [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $entryName, [System.IO.Compression.CompressionLevel]::Optimal)
                }
            }
    }
    finally {
        $archive.Dispose()
    }

    Move-Item -LiteralPath $tempArchive -Destination $DestinationArchive -Force
}

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
    if (-not $SkipDependencyArchive) {
        $dependencySource = Join-Path $GameDirectory "MelonLoader\Dependencies"
        $dependencyArchive = Join-Path $root "Dependencies.zip"
        Write-Host "Packaging MelonLoader dependencies from: $dependencySource"
        New-DependencyArchive -SourceDirectory $dependencySource -DestinationArchive $dependencyArchive
    }

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

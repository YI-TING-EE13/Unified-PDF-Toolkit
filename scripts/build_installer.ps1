param(
    [string]$AppBundlePath = "dist\Unified PDF Toolkit",
    [string]$OutputDir = "dist\installer",
    [string]$ScriptPath = "installer\UnifiedPDFToolkit.iss"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $root
try {
    $candidatePaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )

    $iscc = $candidatePaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $iscc) {
        throw "ISCC.exe was not found. Install Inno Setup 6 first."
    }

    $resolvedBundle = Resolve-Path $AppBundlePath
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $resolvedOutput = Resolve-Path $OutputDir
    $resolvedScript = Resolve-Path $ScriptPath

    & $iscc `
        "/DAppBundleDir=$resolvedBundle" `
        "/DInstallerOutputDir=$resolvedOutput" `
        $resolvedScript

    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compiler failed with exit code $LASTEXITCODE."
    }

    Get-ChildItem $resolvedOutput -Filter "Unified-PDF-Toolkit-Setup-*.exe" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}
finally {
    Pop-Location
}

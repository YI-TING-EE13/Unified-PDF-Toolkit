param(
    [string]$SpecPath = "pdf-toolkit.spec",
    [string]$DistPath = "",
    [string]$WorkPath = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $root
try {
    $pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"
    if (-not (Test-Path $pyinstaller)) {
        throw "PyInstaller was not found at $pyinstaller. Run uv sync --dev first."
    }

    $arguments = @($SpecPath, "--noconfirm")
    if ($DistPath) {
        $arguments += @("--distpath", $DistPath)
    }
    if ($WorkPath) {
        $arguments += @("--workpath", $WorkPath)
    }

    $logRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { "build" }
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $logPath = Join-Path $logRoot "pyinstaller.log"

    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
        $previousNativePreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    $output = & $pyinstaller @arguments 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    if (Get-Variable -Name previousNativePreference -ErrorAction SilentlyContinue) {
        $PSNativeCommandUseErrorActionPreference = $previousNativePreference
    }
    $output | Tee-Object -FilePath $logPath

    if ($exitCode -ne 0) {
        $tail = ($output | Select-Object -Last 40) -join "`n"
        $escaped = $tail.Replace("%", "%25").Replace("`r", "%0D").Replace("`n", "%0A")
        Write-Output "::error title=PyInstaller failed::$escaped"
        throw "PyInstaller failed with exit code $exitCode. Log: $logPath"
    }
}
finally {
    Pop-Location
}

param(
    [string]$AppPath = "dist\Unified PDF Toolkit\Unified PDF Toolkit.exe",
    [int]$StartupSeconds = 5,
    [int]$CloseTimeoutSeconds = 5
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$candidate = if ([System.IO.Path]::IsPathRooted($AppPath)) {
    $AppPath
} else {
    Join-Path $root $AppPath
}
$resolvedApp = (Resolve-Path -LiteralPath $candidate).Path
$process = $null

try {
    $process = Start-Process -FilePath $resolvedApp -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds $StartupSeconds
    $process.Refresh()

    if ($process.HasExited) {
        throw "Packaged app exited during startup with code $($process.ExitCode)."
    }

    if (-not $process.CloseMainWindow()) {
        throw "Packaged app started without a closable main window."
    }
    if (-not $process.WaitForExit($CloseTimeoutSeconds * 1000)) {
        throw "Packaged app did not close within $CloseTimeoutSeconds seconds."
    }
    if ($process.ExitCode -ne 0) {
        throw "Packaged app closed with exit code $($process.ExitCode)."
    }

    Write-Output "[OK] Packaged app startup and graceful shutdown smoke test passed."
}
finally {
    if ($null -ne $process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}

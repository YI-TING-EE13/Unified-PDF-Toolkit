param(
    [string]$SpecPath = "pdf-toolkit.spec",
    [string]$DistPath = "",
    [string]$WorkPath = ""
)

$ErrorActionPreference = "Stop"

function Remove-PreviousBuildTree {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$AllowedParent
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $parentPath = [System.IO.Path]::GetFullPath($AllowedParent).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $parentPrefix = $parentPath + [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($parentPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean build path outside its expected parent: $fullPath"
    }
    if (-not (Test-Path -LiteralPath $fullPath)) {
        return
    }

    $running = Get-Process | ForEach-Object {
        try {
            if ($_.Path -and $_.Path.StartsWith($fullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
                $_
            }
        }
        catch {
            # Some system processes do not allow reading Path; they cannot be this user build.
        }
    }
    if ($running) {
        $processList = ($running | ForEach-Object { "$($_.ProcessName) (PID $($_.Id))" }) -join ", "
        throw "The previous packaged app is still running: $processList. Close it and retry."
    }

    $items = @((Get-Item -LiteralPath $fullPath -Force)) + @(
        Get-ChildItem -LiteralPath $fullPath -Recurse -Force -ErrorAction SilentlyContinue
    )
    foreach ($item in $items) {
        if (($item.Attributes -band [System.IO.FileAttributes]::ReadOnly) -ne 0) {
            $item.Attributes = $item.Attributes -band (-bnot [System.IO.FileAttributes]::ReadOnly)
        }
    }

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Remove-Item -LiteralPath $fullPath -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq 3) {
                throw "Could not clean the previous build at $fullPath. Close the packaged app, Explorer previews, or antivirus scans and retry. $($_.Exception.Message)"
            }
            Start-Sleep -Milliseconds 250
        }
    }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
    $pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"
    if (-not (Test-Path $pyinstaller)) {
        throw "PyInstaller was not found at $pyinstaller. Run uv sync --dev first."
    }

    $specCandidate = if ([System.IO.Path]::IsPathRooted($SpecPath)) {
        $SpecPath
    } else {
        Join-Path $root $SpecPath
    }
    $resolvedSpec = (Resolve-Path $specCandidate).Path
    $resolvedDistPath = if ($DistPath) {
        [System.IO.Path]::GetFullPath($DistPath)
    } else {
        Join-Path $root "dist"
    }
    $resolvedWorkPath = if ($WorkPath) {
        [System.IO.Path]::GetFullPath($WorkPath)
    } else {
        Join-Path $root "build"
    }
    Remove-PreviousBuildTree `
        -Path (Join-Path $resolvedDistPath "Unified PDF Toolkit") `
        -AllowedParent $resolvedDistPath
    Remove-PreviousBuildTree `
        -Path (Join-Path $resolvedWorkPath "pdf-toolkit") `
        -AllowedParent $resolvedWorkPath

    $arguments = @($resolvedSpec, "--noconfirm")
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
catch {
    $message = $_.Exception.Message.Replace("%", "%25").Replace("`r", "%0D").Replace("`n", "%0A")
    Write-Output "::error title=PyInstaller wrapper failed::$message"
    throw
}
finally {
    Pop-Location
}

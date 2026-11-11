param([string]$Iscc = "", [switch]$BundleOnly)
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Push-Location $repoRoot
try {
    # Keep builds independent of packages in the developer's main environment.
    if (-not (Test-Path -LiteralPath ".venv-windows/Scripts/python.exe")) {
        python -m venv .venv-windows
        if ($LASTEXITCODE -ne 0) { throw "Could not create the build environment." }
    }
    $buildPython = Join-Path $repoRoot ".venv-windows/Scripts/python.exe"
    & $buildPython -m pip install -e ".[windows-build]"
    if ($LASTEXITCODE -ne 0) { throw "Could not install build dependencies." }
    $buildArguments = @("packaging/windows/build.py")
    if ($Iscc) { $buildArguments += @("--iscc", $Iscc) }
    if ($BundleOnly) { $buildArguments += "--bundle-only" }
    & $buildPython @buildArguments
    if ($LASTEXITCODE -ne 0) { throw "Windows build failed." }
} finally {
    Pop-Location
}

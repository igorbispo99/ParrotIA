param([Parameter(Mandatory = $true)][string]$Installer)
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$testRoot = Join-Path $repoRoot "build/windows/installer-test"
$installPath = Join-Path $testRoot "ParrotIA"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{3C24D663-19B6-4987-88D3-D8045741D871}_is1"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "ParrotIA.lnk"
$startShortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "ParrotIA.lnk"
$extensions = & python -c "from parrotia import SUPPORTED_EXTENSIONS; print(' '.join(SUPPORTED_EXTENSIONS))"
if ($LASTEXITCODE -ne 0) { throw "Install ParrotIA in the test Python environment first." }
$extensions = $extensions.Trim().Split(" ")
$verbKeys = @($extensions | ForEach-Object { "HKCU:\Software\Classes\SystemFileAssociations\$_\shell\ParrotIA.Transcribe" })

# This integration check briefly creates real shortcuts and shell entries. Never
# replace an existing installation or user-owned shortcut when testing locally.
foreach ($existing in (@($uninstallKey, $desktopShortcut, $startShortcut, $installPath) + $verbKeys)) {
    if (Test-Path -LiteralPath $existing) {
        throw "Installer test refused to replace an existing item: $existing"
    }
}
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
$verificationFailure = $null
$cleanupFailure = $null
try {
    $setup = Start-Process -FilePath $installerPath -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
        ('/DIR="' + $installPath + '"'), "/TASKS=desktopicon,explorer",
        ('/LOG="' + (Join-Path $testRoot "setup.log") + '"')
    ) -WindowStyle Hidden -Wait -PassThru
    if ($setup.ExitCode -ne 0) { throw "Installer failed: $($setup.ExitCode)" }
    $installedExe = Join-Path $installPath "parrotia-gui.exe"
    $shortcutReader = New-Object -ComObject WScript.Shell
    foreach ($shortcut in @($desktopShortcut, $startShortcut)) {
        if (-not (Test-Path -LiteralPath $shortcut)) { throw "Missing shortcut: $shortcut" }
        if ($shortcutReader.CreateShortcut($shortcut).TargetPath -ne $installedExe) {
            throw "Incorrect shortcut target: $shortcut"
        }
    }
    foreach ($verbKey in $verbKeys) {
        $verb = Get-Item -LiteralPath $verbKey
        if ($verb.GetValue("") -ne "Transcribe on Parrot") { throw "Incorrect menu title" }
        if ($verb.GetValue("MultiSelectModel") -ne "Player") { throw "Multi-selection is disabled" }
        $command = (Get-Item -LiteralPath "$verbKey\command").GetValue("")
        if ($command -ne ('"' + $installedExe + '" --shell "%1"')) { throw "Incorrect Explorer command: $command" }
    }
    $report = Join-Path $testRoot "installed-smoke.json"
    $smoke = Start-Process -FilePath $installedExe -ArgumentList @(
        "--smoke-test", ('"' + $report + '"')
    ) -WindowStyle Hidden -Wait -PassThru
    if ($smoke.ExitCode -ne 0) { throw "Installed app failed its smoke test" }
    $data = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($data.samples -ne 1600) { throw "Installed app did not decode audio correctly" }
} catch {
    $verificationFailure = $_
} finally {
    $uninstaller = Join-Path $installPath "unins000.exe"
    if (Test-Path -LiteralPath $uninstaller) {
        $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @(
            "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            ('/LOG="' + (Join-Path $testRoot "uninstall.log") + '"')
        ) -WindowStyle Hidden -Wait -PassThru
        if ($uninstall.ExitCode -ne 0) {
            $cleanupFailure = "Test uninstallation failed: $($uninstall.ExitCode). Test files remain at $installPath"
            Write-Warning $cleanupFailure
        }
    }
}
if ($verificationFailure) { throw $verificationFailure }
if ($cleanupFailure) { throw $cleanupFailure }
foreach ($leftover in (@($uninstallKey, $desktopShortcut, $startShortcut) + $verbKeys)) {
    if (Test-Path -LiteralPath $leftover) { throw "Uninstaller left an integration entry: $leftover" }
}
Write-Output "Installer verified: shortcuts, all media verbs, installed runtime, and clean uninstall."

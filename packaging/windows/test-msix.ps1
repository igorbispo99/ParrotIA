# Install the MSIX with a throwaway test signature, check its integration, then remove it.
#
# Must run elevated: Windows only installs a sideloaded package whose certificate
# is trusted machine-wide (LocalMachine\TrustedPeople). The Store signs real
# releases itself; this signature exists only for the duration of the test.
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [switch]$Wack
)
$ErrorActionPreference = "Stop"
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this test from an elevated PowerShell (it trusts a test certificate machine-wide)."
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$packagePath = (Resolve-Path -LiteralPath $Package).Path
$testRoot = Join-Path $repoRoot "build/windows/msix-test"
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

function Find-SdkTool([string]$Name) {
    $tool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.*\x64\$Name" -ErrorAction SilentlyContinue |
        Sort-Object { [version]$_.Directory.Parent.Name } | Select-Object -Last 1
    if (-not $tool) { throw "$Name not found. Install the Windows SDK." }
    $tool.FullName
}

# Read the identity from the package itself, so the test matches what was built.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($packagePath)
try {
    $reader = New-Object IO.StreamReader($archive.GetEntry("AppxManifest.xml").Open())
    [xml]$manifest = $reader.ReadToEnd()
    $reader.Close()
} finally { $archive.Dispose() }
$name = $manifest.Package.Identity.Name
$publisher = $manifest.Package.Identity.Publisher
$extensions = @($manifest.Package.Applications.Application.Extensions.Extension.FileTypeAssociation.SupportedFileTypes.FileType)
$verbId = $manifest.Package.Applications.Application.Extensions.Extension.FileTypeAssociation.SupportedVerbs.Verb.Id
$alias = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\parrotia-app.exe"

if (Get-AppxPackage -Name $name) {
    throw "MSIX test refused to replace an installed $name package."
}

$signed = Join-Path $testRoot "ParrotIA-test-signed.msix"
Copy-Item -LiteralPath $packagePath -Destination $signed -Force
$cert = New-SelfSignedCertificate -Type Custom -Subject $publisher -KeyUsage DigitalSignature `
    -FriendlyName "ParrotIA MSIX test (temporary)" -CertStoreLocation Cert:\CurrentUser\My `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
$verificationFailure = $null
$cleanupFailure = $null
$reportDir = $null
try {
    $cer = Join-Path $testRoot "test-signing.cer"
    Export-Certificate -Cert $cert -FilePath $cer | Out-Null
    Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople | Out-Null
    & (Find-SdkTool "signtool.exe") sign /q /fd SHA256 /sha1 $cert.Thumbprint $signed
    if ($LASTEXITCODE -ne 0) { throw "Test signing failed" }

    Add-AppxPackage -Path $signed
    $installed = Get-AppxPackage -Name $name
    if (-not $installed) { throw "Package did not install" }
    if (-not (Test-Path -LiteralPath (Join-Path $installed.InstallLocation "parrotia-gui.exe"))) {
        throw "Installed package lacks parrotia-gui.exe"
    }
    if (-not (Test-Path -LiteralPath $alias)) { throw "Missing app execution alias: $alias" }

    # The frozen smoke test, run inside the package through its alias. Its
    # report goes to a fresh folder outside AppData (whose writes MSIX may
    # redirect) and outside the folders Controlled folder access guards
    # (Documents, Desktop...), where it blocks this test-signed build.
    $reportDir = Join-Path $env:SystemDrive "ParrotIA-msix-test-$([guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $reportDir | Out-Null
    $report = Join-Path $reportDir "packaged-smoke.json"
    $smoke = Start-Process -FilePath $alias -ArgumentList @("--smoke-test", ('"' + $report + '"')) `
        -WindowStyle Hidden -PassThru
    $null = $smoke.Handle  # Keeps ExitCode readable after WaitForExit.
    if (-not $smoke.WaitForExit(180000)) {
        Stop-Process -Id $smoke.Id -Force -ErrorAction SilentlyContinue
        throw "Packaged smoke test did not finish within 3 minutes"
    }
    if (-not (Test-Path -LiteralPath $report)) { throw "Packaged smoke test wrote no report (exit $($smoke.ExitCode))" }
    if ($smoke.ExitCode -ne 0) { throw "Packaged smoke test failed:`n$(Get-Content -LiteralPath $report -Raw)" }
    Copy-Item -LiteralPath $report -Destination (Join-Path $testRoot "packaged-smoke.json") -Force
    $data = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($data.samples -ne 1600) { throw "Packaged app did not decode audio correctly" }
    if (-not $data.packaged) { throw "App did not detect its package identity" }
    # Models go to the package's LocalCache, which Windows deletes on uninstall.
    $packageData = Join-Path $env:LOCALAPPDATA "Packages\$($installed.PackageFamilyName)"
    $expectedCache = Join-Path $packageData "LocalCache\huggingface"
    if ($data.hf_home -ne $expectedCache) { throw "Unexpected packaged model cache: $($data.hf_home) (expected $expectedCache)" }
    if (-not (Test-Path -LiteralPath $expectedCache)) { throw "Model cache folder was not created: $expectedCache" }

    # Explorer integration: every media type offers ParrotIA and the verb.
    foreach ($extension in $extensions) {
        $openWith = Get-Item -LiteralPath "HKCU:\Software\Classes\$extension\OpenWithProgids" -ErrorAction SilentlyContinue
        $progIds = @($openWith.Property | Where-Object { $_ -like "AppX*" })
        $verbFound = $false
        foreach ($progId in $progIds) {
            if (Test-Path -LiteralPath "HKCU:\Software\Classes\$progId\Shell\$verbId") { $verbFound = $true }
        }
        if (-not $verbFound) {
            $shells = ($progIds | ForEach-Object {
                (Get-ChildItem -LiteralPath "HKCU:\Software\Classes\$_\Shell" -ErrorAction SilentlyContinue).PSChildName
            }) -join ", "
            throw "No '$verbId' verb registered for $extension (AppX ProgIDs: $($progIds -join ', '); verbs: $shells)"
        }
    }

    if ($Wack) {
        $appcert = "${env:ProgramFiles(x86)}\Windows Kits\10\App Certification Kit\appcert.exe"
        if (-not (Test-Path -LiteralPath $appcert)) { throw "Windows App Certification Kit not found: $appcert" }
        $wackReport = Join-Path $testRoot "wack-report.xml"
        Remove-Item -LiteralPath $wackReport -ErrorAction SilentlyContinue
        & $appcert reset | Out-Null
        & $appcert test -appxpackagepath $signed -reportoutputpath $wackReport | Out-Null
        if (-not (Test-Path -LiteralPath $wackReport)) { throw "WACK produced no report" }
        [xml]$wackXml = Get-Content -LiteralPath $wackReport -Raw
        $overall = $wackXml.REPORT.OVERALL_RESULT
        Write-Output "WACK overall result: $overall (report: $wackReport)"
        if ($overall -eq "FAIL") { throw "Windows App Certification Kit failed; see $wackReport" }
    }
} catch {
    $verificationFailure = $_
} finally {
    if ($reportDir) { Remove-Item -LiteralPath $reportDir -Recurse -Force -ErrorAction SilentlyContinue }
    $leftover = Get-AppxPackage -Name $name
    if ($leftover) {
        try { Remove-AppxPackage -Package $leftover.PackageFullName } catch {
            $cleanupFailure = "Could not remove test package: $_"
        }
    }
    foreach ($store in @("Cert:\LocalMachine\TrustedPeople", "Cert:\CurrentUser\My")) {
        Remove-Item -LiteralPath (Join-Path $store $cert.Thumbprint) -ErrorAction SilentlyContinue
    }
}
if ($verificationFailure) { throw $verificationFailure }
if ($cleanupFailure) { throw $cleanupFailure }
if (Get-AppxPackage -Name $name) { throw "Package still installed after removal" }
if ($installed -and (Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA "Packages\$($installed.PackageFamilyName)"))) {
    throw "Uninstall left package data behind"
}
if (Test-Path -LiteralPath $alias) { throw "Uninstall left the app execution alias behind" }
Write-Output "MSIX verified: install, packaged smoke test, cache redirection, Explorer verbs, clean removal."

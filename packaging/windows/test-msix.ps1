# Install the MSIX with a throwaway test signature, check its integration, then remove it.
#
# Must run elevated: Windows only installs a sideloaded package whose certificate
# is trusted machine-wide (LocalMachine\TrustedPeople). The Store signs real
# releases itself; this signature exists only for the duration of the test.
#
# -KeepInstalled leaves a passing package (and its test certificate) in place
# for manual checks, such as the Explorer context menu, and prints the
# commands that remove both afterwards.
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [switch]$Wack,
    [switch]$KeepInstalled
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
$application = $manifest.Package.Applications.Application
$extensions = @($application.Extensions.Extension.FileTypeAssociation.SupportedFileTypes.FileType)
$alias = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\parrotia-app.exe"
# Built next to the DLL by msix.py; exercises the installed Explorer command.
$shellTest = Join-Path $repoRoot "build\windows\msix\shell\shell_test.exe"
if (-not (Test-Path -LiteralPath $shellTest)) { throw "Build the MSIX first (missing $shellTest)" }

# The Explorer command launches the app through IApplicationActivationManager,
# so the test activates it the same way.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class ParrotIAActivation {
    [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IApplicationActivationManager {
        [PreserveSig] int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments, int options, out uint processId);
    }
    [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    class ApplicationActivationManager { }
    public static uint Activate(string appUserModelId, string arguments) {
        var manager = (IApplicationActivationManager)new ApplicationActivationManager();
        uint processId;
        Marshal.ThrowExceptionForHR(manager.ActivateApplication(appUserModelId, arguments, 0, out processId));
        return processId;
    }
}
"@

function Invoke-PackagedSmokeTest([scriptblock]$Start, [string]$Report, [string]$How) {
    $process = & $Start
    $null = $process.Handle  # Keeps ExitCode readable after WaitForExit.
    if (-not $process.WaitForExit(180000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "Packaged smoke test ($How) did not finish within 3 minutes"
    }
    if (-not (Test-Path -LiteralPath $Report)) { throw "Packaged smoke test ($How) wrote no report" }
    if ($process.ExitCode -ne 0) { throw "Packaged smoke test ($How) failed:`n$(Get-Content -LiteralPath $Report -Raw)" }
    $data = Get-Content -LiteralPath $Report -Raw | ConvertFrom-Json
    if ($data.samples -ne 1600) { throw "Packaged app ($How) did not decode audio correctly" }
    if (-not $data.packaged) { throw "App ($How) did not detect its package identity" }
    $data
}

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
    $data = Invoke-PackagedSmokeTest -How "alias" -Report $report -Start {
        Start-Process -FilePath $alias -ArgumentList @("--smoke-test", ('"' + $report + '"')) `
            -WindowStyle Hidden -PassThru
    }
    Copy-Item -LiteralPath $report -Destination (Join-Path $testRoot "packaged-smoke.json") -Force
    # Models go to the package's LocalCache, which Windows deletes on uninstall.
    $packageData = Join-Path $env:LOCALAPPDATA "Packages\$($installed.PackageFamilyName)"
    $expectedCache = Join-Path $packageData "LocalCache\huggingface"
    if ($data.hf_home -ne $expectedCache) { throw "Unexpected packaged model cache: $($data.hf_home) (expected $expectedCache)" }
    if (-not (Test-Path -LiteralPath $expectedCache)) { throw "Model cache folder was not created: $expectedCache" }

    # "Open with": every media type lists the package.
    foreach ($extension in $extensions) {
        $openWith = Get-Item -LiteralPath "HKCU:\Software\Classes\$extension\OpenWithProgids" -ErrorAction SilentlyContinue
        if (-not @($openWith.Property | Where-Object { $_ -like "AppX*" })) {
            throw "ParrotIA is not offered under Open with for $extension"
        }
    }

    # Explorer command: the installed DLL must target this package's app.
    $installedDll = Join-Path $installed.InstallLocation "parrotia_shell.dll"
    if (-not (Test-Path -LiteralPath $installedDll)) { throw "Installed package lacks parrotia_shell.dll" }
    # Package files only execute inside their own package (a WIN://SYSAPPID
    # condition in the folder's ACL); other processes, even elevated, may only
    # read them. Explorer gets in through packaged COM, so test a byte-identical
    # copy in a folder named like the install folder (the package full name).
    $dllCopy = Join-Path $reportDir "$($installed.PackageFullName)\parrotia_shell.dll"
    New-Item -ItemType Directory -Path (Split-Path $dllCopy) | Out-Null
    Copy-Item -LiteralPath $installedDll -Destination $dllCopy
    $shellScratch = Join-Path $reportDir "shell"
    New-Item -ItemType Directory -Path $shellScratch | Out-Null
    $shellOutput = & $shellTest $dllCopy $shellScratch
    $shellOutput | ForEach-Object { Write-Output "  $_" }
    if ($LASTEXITCODE -ne 0) { throw "Explorer command checks failed against the installed DLL" }
    $appId = "$($installed.PackageFamilyName)!$($application.Id)"
    if (-not ($shellOutput -match [regex]::Escape("activates $appId"))) {
        throw "Explorer command does not target $appId"
    }
    # ...and activating that app with arguments, as the DLL does, must reach it.
    $activationReport = Join-Path $reportDir "activated-smoke.json"
    $null = Invoke-PackagedSmokeTest -How "activation" -Report $activationReport -Start {
        Get-Process -Id ([ParrotIAActivation]::Activate($appId, "--smoke-test `"$activationReport`""))
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
    $keep = $KeepInstalled -and -not $verificationFailure
    $leftover = Get-AppxPackage -Name $name
    if ($keep) {
        Write-Output "Kept $($leftover.PackageFullName) installed. Remove it and its test certificate with (elevated):"
        Write-Output "  Remove-AppxPackage -Package $($leftover.PackageFullName)"
        Write-Output "  Remove-Item Cert:\LocalMachine\TrustedPeople\$($cert.Thumbprint), Cert:\CurrentUser\My\$($cert.Thumbprint)"
    } elseif ($leftover) {
        try { Remove-AppxPackage -Package $leftover.PackageFullName } catch {
            $cleanupFailure = "Could not remove test package: $_"
        }
    }
    if (-not $keep) {
        foreach ($store in @("Cert:\LocalMachine\TrustedPeople", "Cert:\CurrentUser\My")) {
            Remove-Item -LiteralPath (Join-Path $store $cert.Thumbprint) -ErrorAction SilentlyContinue
        }
    }
}
if ($verificationFailure) { throw $verificationFailure }
if ($cleanupFailure) { throw $cleanupFailure }
if ($keep) {
    Write-Output "MSIX verified (removal not tested: -KeepInstalled)."
    return
}
if (Get-AppxPackage -Name $name) { throw "Package still installed after removal" }
if ($installed -and (Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA "Packages\$($installed.PackageFamilyName)"))) {
    throw "Uninstall left package data behind"
}
if (Test-Path -LiteralPath $alias) { throw "Uninstall left the app execution alias behind" }
Write-Output "MSIX verified: install, packaged smoke tests (alias and app activation), model cache, Open with, Explorer command, clean removal."

# Sideload a --test-package MSIX and run the app's smoke test inside it.
# Needs Windows PowerShell 5.1 (the Appx cmdlets) and an elevated session.
# The test signs with a throwaway certificate that it trusts only for the
# duration of the run; never point it at a package meant for the Store.
param([Parameter(Mandatory = $true)][string]$Package)
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$packagePath = (Resolve-Path -LiteralPath $Package).Path
$packageName = "IgorBispo.ParrotIA.Test"
$subject = "CN=ParrotIA Test"
$testRoot = Join-Path $repoRoot "build/msix/test"
if (Get-AppxPackage -Name $packageName) {
    throw "MSIX test refused to replace an installed package: $packageName"
}
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
$cert = $null
$trusted = $null
$verificationFailure = $null
try {
    $cert = New-SelfSignedCertificate -Type Custom -Subject $subject `
        -KeyUsage DigitalSignature -CertStoreLocation "Cert:\CurrentUser\My" `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}") `
        -NotAfter (Get-Date).AddDays(2)
    $signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $signtool) { throw "signtool.exe not found; install the Windows SDK." }
    & $signtool.FullName sign /fd SHA256 /sha1 $cert.Thumbprint /s My $packagePath
    if ($LASTEXITCODE) { throw "signtool failed: $LASTEXITCODE" }
    $cerFile = Join-Path $testRoot "test.cer"
    Export-Certificate -Cert $cert -FilePath $cerFile | Out-Null
    $trusted = Import-Certificate -FilePath $cerFile -CertStoreLocation "Cert:\LocalMachine\TrustedPeople"

    Add-AppxPackage -Path $packagePath
    $installed = Get-AppxPackage -Name $packageName
    if (-not $installed) { throw "Package did not register" }
    Write-Host "Installed $($installed.PackageFullName) at $($installed.InstallLocation)"

    # Run the frozen app inside the package so it sees its package identity
    # and the read-only install folder, as it will when installed from the Store.
    $report = Join-Path $testRoot "packaged-smoke.json"
    Remove-Item -LiteralPath $report -ErrorAction SilentlyContinue
    Invoke-CommandInDesktopPackage -PackageFamilyName $installed.PackageFamilyName `
        -AppId "ParrotIA" -PreventBreakaway `
        -Command (Join-Path $installed.InstallLocation "parrotia-gui.exe") `
        -Args ('--smoke-test "' + $report + '"')
    $deadline = (Get-Date).AddSeconds(120)
    while (-not (Test-Path -LiteralPath $report) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
    }
    if (-not (Test-Path -LiteralPath $report)) { throw "Packaged app wrote no smoke-test report" }
    $data = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($data.samples -ne 1600) { throw "Packaged app did not decode audio correctly" }
    Write-Host "Packaged smoke test passed: $($data | ConvertTo-Json -Compress)"
} catch {
    $verificationFailure = $_
} finally {
    Get-AppxPackage -Name $packageName | Remove-AppxPackage -ErrorAction Continue
    if ($trusted) { Remove-Item -LiteralPath "Cert:\LocalMachine\TrustedPeople\$($trusted.Thumbprint)" -ErrorAction Continue }
    if ($cert) { Remove-Item -LiteralPath "Cert:\CurrentUser\My\$($cert.Thumbprint)" -ErrorAction Continue }
}
if ($verificationFailure) { throw $verificationFailure }

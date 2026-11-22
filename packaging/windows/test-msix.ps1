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

    # docs/privacy.md says models stay in the Hugging Face cache in the user's
    # profile folder, which is not redirected into package storage. Verify it: a
    # process inside the package writes a file there, and it must be visible outside.
    # LocalAppData is probed too, for information only (the Explorer queue uses it).
    $cmd = Join-Path $env:SystemRoot "System32\cmd.exe"
    $packaged = @{ PackageFamilyName = $installed.PackageFamilyName; AppId = "ParrotIA"; PreventBreakaway = $true; Command = $cmd }
    function Test-PackagedWrite([string]$Variable, [string]$Folder) {
        $realDir = Join-Path (Get-Item "Env:$Variable").Value $Folder
        $realFile = Join-Path $realDir "storage-probe.txt"
        $seen = Join-Path $testRoot "probe-$Variable.txt"
        Remove-Item -LiteralPath $realFile, $seen -ErrorAction SilentlyContinue
        $inner = '%' + $Variable + '%\' + $Folder
        Invoke-CommandInDesktopPackage @packaged -Args ('/c mkdir "' + $inner + '" 2>nul & echo probe> "' + $inner + '\storage-probe.txt"') | Out-Null
        Start-Sleep -Seconds 3
        Invoke-CommandInDesktopPackage @packaged -Args ('/c if exist "' + $inner + '\storage-probe.txt" (echo yes> "' + $seen + '") else (echo no> "' + $seen + '")') | Out-Null
        $deadline = (Get-Date).AddSeconds(30)
        while (-not (Test-Path -LiteralPath $seen) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
        if (-not (Test-Path -LiteralPath $seen)) { throw "Storage probe for $Variable did not run inside the package" }
        $inside = (Get-Content -LiteralPath $seen -Raw).Trim()
        $outside = Test-Path -LiteralPath $realFile
        Write-Host "STORAGE_PROBE $Variable\$Folder inside_package=$inside outside_package=$outside"
        Remove-Item -LiteralPath $realFile -ErrorAction SilentlyContinue
        return @{ Inside = $inside; Outside = $outside }
    }
    $profileProbe = Test-PackagedWrite "USERPROFILE" ".cache\parrotia-probe"
    if ($profileProbe.Inside -ne "yes") { throw "Packaged app could not read back a file it wrote to the profile folder" }
    if (-not $profileProbe.Outside) { throw "Profile-folder writes are redirected into package storage; correct docs/privacy.md" }
    Test-PackagedWrite "LOCALAPPDATA" "ParrotIA\parrotia-probe" | Out-Null
} catch {
    $verificationFailure = $_
} finally {
    Get-AppxPackage -Name $packageName | Remove-AppxPackage -ErrorAction Continue
    if ($trusted) { Remove-Item -LiteralPath "Cert:\LocalMachine\TrustedPeople\$($trusted.Thumbprint)" -ErrorAction Continue }
    if ($cert) { Remove-Item -LiteralPath "Cert:\CurrentUser\My\$($cert.Thumbprint)" -ErrorAction Continue }
}
if ($verificationFailure) { throw $verificationFailure }

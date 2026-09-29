<#
.SYNOPSIS
  Sign the patched KeyMagic driver and point the KeyMagic service at it (original file untouched).

.DESCRIPTION
  Works in Windows PowerShell 5.1 and PowerShell 7.

  * Relaunches itself elevated (one UAC prompt) if it is not already Administrator. The elevated copy
    never relaunches again: if it is still not admin it stops with a message.
  * Needs Windows test-signing mode (bcdedit /set testsigning on).
  * Finds a usable code-signing certificate automatically (LocalMachine\My, private key, in date, trusted
    chain). If several, asks which. If none, a wizard explains what it would create and changes nothing
    until you type 'yes'.
  * Copies the signed driver next to the original as KeyMagicFnSwap.sys. Original KeyMagic.sys untouched.
  * Points HKLM\SYSTEM\CurrentControlSet\Services\KeyMagic\ImagePath at the copy and saves the old value
    as ImagePath.orig (Uninstall-FnCtrlSwap.ps1 restores it). Takes effect after a reboot.
  * Everything it prints is also written to install.log next to this script.

.EXAMPLE
  python patch_keymagic.py            # no elevation needed
  .\Install-FnCtrlSwap.ps1 -Driver ..\KeyMagicFnSwap.sys
#>
[CmdletBinding()]
param(
    [string] $CertThumbprint,
    [string] $Driver = (Join-Path $PSScriptRoot 'KeyMagicFnSwap.sys'),
    [switch] $Elevated    # internal: set on the relaunched, elevated copy
)

function Test-IsAdmin {
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $p  = New-Object Security.Principal.WindowsPrincipal($id)
        return [bool]$p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

$log = Join-Path $PSScriptRoot 'install.log'
function Write-Log([string] $msg, [string] $color = 'Gray') {
    Write-Host $msg -ForegroundColor $color
    try { Add-Content -Path $log -Value ("{0:HH:mm:ss} {1}" -f (Get-Date), $msg) } catch { }
}

# ---- elevation: relaunch at most once --------------------------------------------------------
if (-not (Test-IsAdmin)) {
    if ($Elevated -or $env:FNCTRL_RELAUNCHED -eq '1') {
        Write-Log 'Already relaunched but still not Administrator. Not relaunching again. Open an elevated prompt and run this script there.' 'Red'
        [void](Read-Host 'Press Enter to close')
        exit 1
    }
    $env:FNCTRL_RELAUNCHED = '1'
    $argList = @('-NoProfile', '-File', ('"{0}"' -f $PSCommandPath), '-Elevated')
    if ($Driver)         { $argList += @('-Driver', ('"{0}"' -f $Driver)) }
    if ($CertThumbprint) { $argList += @('-CertThumbprint', $CertThumbprint) }
    try {
        Start-Process -FilePath (Get-Process -Id $PID).Path -Verb RunAs -ArgumentList $argList -Wait
    } catch {
        Write-Log ("Elevation was cancelled or failed: " + $_.Exception.Message) 'Red'
        exit 1
    }
    exit 0
}

# ---- certificate helpers ---------------------------------------------------------------------
function Test-CertUsable($c) {
    if (-not $c.HasPrivateKey) { return $false }
    if ($c.NotAfter -lt (Get-Date) -or $c.NotBefore -gt (Get-Date)) { return $false }
    $codeSigning = $c.EnhancedKeyUsageList | Where-Object { $_.ObjectId -eq '1.3.6.1.5.5.7.3.3' }
    if (-not $codeSigning) { return $false }
    $chain = New-Object Security.Cryptography.X509Certificates.X509Chain
    $chain.ChainPolicy.RevocationMode = 'NoCheck'
    return [bool]$chain.Build($c)
}

function Select-SigningCert {
    $found = @(Get-ChildItem Cert:\LocalMachine\My | Where-Object { Test-CertUsable $_ })
    if ($found.Count -eq 1) {
        Write-Log ("Using code-signing certificate: {0}  [{1}]" -f $found[0].Subject, $found[0].Thumbprint)
        return $found[0].Thumbprint
    }
    if ($found.Count -gt 1) {
        Write-Log 'Several usable code-signing certificates found:'
        for ($i = 0; $i -lt $found.Count; $i++) {
            Write-Log ("  [{0}] {1}  expires {2:yyyy-MM-dd}  {3}" -f $i, $found[$i].Subject, $found[$i].NotAfter, $found[$i].Thumbprint)
        }
        $n = Read-Host 'Which one? (number)'
        if ($n -match '^\d+$' -and [int]$n -lt $found.Count) { return $found[[int]$n].Thumbprint }
        throw 'No valid selection.'
    }
    Write-Log ''
    Write-Log 'No usable code-signing certificate was found on this machine.' 'Yellow'
    Write-Log 'A modified kernel driver must be signed by a certificate Windows trusts. I can create one:'
    Write-Log '  - a self-signed code-signing certificate "CN=FnCtrlSwap Test", valid 5 years, in LocalMachine\My'
    Write-Log '  - added to LocalMachine\Root and LocalMachine\TrustedPublisher'
    Write-Log 'Trusting it in Root means anything signed with its key is trusted machine-wide; only do this on a'
    Write-Log 'machine you control. Remove it later with:'
    Write-Log '  Get-ChildItem Cert:\LocalMachine\My,Cert:\LocalMachine\Root,Cert:\LocalMachine\TrustedPublisher | Where-Object Subject -eq "CN=FnCtrlSwap Test" | Remove-Item'
    Write-Log ''
    if ((Read-Host "Type 'yes' to create and trust it, anything else to cancel") -ne 'yes') { throw 'Cancelled; nothing was changed.' }
    $c = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=FnCtrlSwap Test' `
         -CertStoreLocation Cert:\LocalMachine\My -NotAfter (Get-Date).AddYears(5)
    $cer = Join-Path $env:TEMP 'FnCtrlSwap.cer'
    [void](Export-Certificate -Cert $c -FilePath $cer)
    [void](Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\Root)
    [void](Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPublisher)
    Remove-Item $cer -ErrorAction SilentlyContinue
    Write-Log ("Created and trusted certificate [{0}]" -f $c.Thumbprint)
    return $c.Thumbprint
}

# ---- main ------------------------------------------------------------------------------------
try {
    $ErrorActionPreference = 'Stop'
    Write-Log ("=== Install-FnCtrlSwap (PowerShell {0}) ===" -f $PSVersionTable.PSVersion)
    if (-not (Test-Path -LiteralPath $Driver)) { throw "Patched driver not found: $Driver (run patch_keymagic.py first)" }
    $Driver = (Resolve-Path -LiteralPath $Driver).Path

    $bcd = (bcdedit /enum '{current}') -join "`n"
    if ($bcd -notmatch 'testsigning\s+Yes') { throw "Test-signing is off ('bcdedit /set testsigning on', then reboot)." }

    if (-not $CertThumbprint) { $CertThumbprint = Select-SigningCert }
    if (-not (Test-Path "Cert:\LocalMachine\My\$CertThumbprint")) { throw "Certificate $CertThumbprint not found in LocalMachine\My." }

    $signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending |
                Select-Object -First 1 -ExpandProperty FullName
    if (-not $signtool) { throw 'signtool.exe not found (install the Windows SDK signing tools).' }

    Write-Log "Signing $Driver"
    $out = & $signtool sign /sm /s My /sha1 $CertThumbprint /fd sha256 $Driver 2>&1
    $out | ForEach-Object { Write-Log ([string]$_) }
    if ($LASTEXITCODE -ne 0) { throw 'signtool sign failed' }
    $sig = Get-AuthenticodeSignature -FilePath $Driver
    if ($sig.Status -ne 'Valid') { throw ("Signature is {0}: {1}. Not installing." -f $sig.Status, $sig.StatusMessage) }
    Write-Log 'Signature is Valid.'

    $dest = Join-Path $env:WINDIR 'System32\drivers\KeyMagicFnSwap.sys'
    Copy-Item -LiteralPath $Driver -Destination $dest -Force
    $svc = 'HKLM:\SYSTEM\CurrentControlSet\Services\KeyMagic'
    $cur = (Get-Item $svc).GetValue('ImagePath', $null, 'DoNotExpandEnvironmentNames')
    if ($null -eq (Get-ItemProperty $svc).'ImagePath.orig') {
        New-ItemProperty $svc -Name 'ImagePath.orig' -Value $cur -PropertyType ExpandString | Out-Null
    }
    Set-ItemProperty $svc -Name ImagePath -Value '\SystemRoot\System32\drivers\KeyMagicFnSwap.sys'
    Write-Log ("ImagePath: {0} -> \SystemRoot\System32\drivers\KeyMagicFnSwap.sys" -f $cur) 'Green'
    Write-Log 'Reboot to load it. Undo: .\Uninstall-FnCtrlSwap.ps1' 'Green'
} catch {
    Write-Log ("FAILED: " + $_.Exception.Message) 'Red'
    Write-Log ($_.ScriptStackTrace) 'DarkGray'
} finally {
    if ($Elevated) { [void](Read-Host 'Press Enter to close') }
}

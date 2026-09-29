<#
.SYNOPSIS
  Put the original Apple KeyMagic driver back (undo Install-FnCtrlSwap.ps1). Reboot afterwards.
  Works in Windows PowerShell 5.1 and PowerShell 7. Relaunches itself elevated at most once.
#>
[CmdletBinding()]
param([switch] $Elevated)   # internal: set on the relaunched, elevated copy

function Test-IsAdmin {
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $p  = New-Object Security.Principal.WindowsPrincipal($id)
        return [bool]$p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

if (-not (Test-IsAdmin)) {
    if ($Elevated -or $env:FNCTRL_RELAUNCHED -eq '1') {
        Write-Host 'Already relaunched but still not Administrator. Not relaunching again.' -ForegroundColor Red
        [void](Read-Host 'Press Enter to close')
        exit 1
    }
    $env:FNCTRL_RELAUNCHED = '1'
    try {
        Start-Process -FilePath (Get-Process -Id $PID).Path -Verb RunAs -Wait `
            -ArgumentList @('-NoProfile', '-File', ('"{0}"' -f $PSCommandPath), '-Elevated')
    } catch {
        Write-Host ("Elevation was cancelled or failed: " + $_.Exception.Message) -ForegroundColor Red
        exit 1
    }
    exit 0
}

try {
    $ErrorActionPreference = 'Stop'
    $svc  = 'HKLM:\SYSTEM\CurrentControlSet\Services\KeyMagic'
    $orig = (Get-Item $svc).GetValue('ImagePath.orig', $null, 'DoNotExpandEnvironmentNames')
    if (-not $orig) { $orig = '\SystemRoot\System32\drivers\KeyMagic.sys' }
    Set-ItemProperty $svc -Name ImagePath -Value $orig
    Remove-ItemProperty $svc -Name 'ImagePath.orig' -ErrorAction SilentlyContinue
    Write-Host "ImagePath restored to $orig. Reboot to load the original driver." -ForegroundColor Green
    Write-Host "(The copy $env:WINDIR\System32\drivers\KeyMagicFnSwap.sys can be deleted after the reboot.)"
} catch {
    Write-Host ("FAILED: " + $_.Exception.Message) -ForegroundColor Red
} finally {
    if ($Elevated) { [void](Read-Host 'Press Enter to close') }
}

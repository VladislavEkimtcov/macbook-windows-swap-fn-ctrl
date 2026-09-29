<#
.SYNOPSIS
  Put the original Apple KeyMagic driver back (undo Install-FnCtrlSwap.ps1). Reboot afterwards.
#>
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrator')) {
    throw 'Run this from an elevated (Administrator) prompt.'
}
$svc  = 'HKLM:\SYSTEM\CurrentControlSet\Services\KeyMagic'
$orig = (Get-Item $svc).GetValue('ImagePath.orig', $null, 'DoNotExpandEnvironmentNames')
if (-not $orig) { $orig = '\SystemRoot\System32\drivers\KeyMagic.sys' }
Set-ItemProperty $svc -Name ImagePath -Value $orig
Remove-ItemProperty $svc -Name 'ImagePath.orig' -ErrorAction SilentlyContinue
Write-Host "ImagePath restored to $orig. Reboot to load the original driver."
Write-Host "(The copy $env:WINDIR\System32\drivers\KeyMagicFnSwap.sys can be deleted after the reboot.)"

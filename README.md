# Swap Fn and Control on a MacBook's built-in keyboard in Windows (Boot Camp)

Can you swap the `fn` and `control` keys on a MacBook keyboard while running Windows 10 or 11 under
Boot Camp? Not with AutoHotkey, SharpKeys, PowerToys Keyboard Manager, KeyTweak or the `Scancode Map`
registry value. This repo shows why, with measurements from a real **MacBook Air A1465 (MacBookAir6,1)**,
and a working fix: a small patch to Apple's Boot Camp keyboard filter driver, **`KeyMagic.sys`**.

> **Status: works.** Tested on a MacBook Air A1465, Windows 10 IoT Enterprise LTSC 2021, Boot Camp 6.1.8086.2:
> after installing the patched driver and rebooting, the physical Fn key acts as Control and the physical
> Control key acts as Fn. Other models are untested. Read *Risks* before installing.

## Why no remapper can swap Fn and Ctrl

On the built-in Apple keyboard, Fn is not a key as far as Windows is concerned. It is one bit
(report ID 1, byte 9, bit 1; HID vendor usage `0xFF:0x03`) inside the keyboard's USB input report.
Apple's `KeyMagic.sys` is a lower filter under `HidUsb`. It reads that bit to decide which translations
to apply, then throws it away before Windows parses the report.

Captured with a low-level keyboard hook on the built-in keyboard, before the patch:

| pressed | Windows saw |
|---|---|
| Fn alone | nothing |
| Left Control | VK 0xA2, scan 0x1D |
| Fn + Backspace | Delete |
| Fn + Left arrow | Home |
| Fn + Return | Insert |
| Fn + F1 | nothing (brightness is handled below the key layer) |

So Fn has no scan code, no virtual key and no Raw Input event; tools that remap scan codes or hook keys have
nothing to grab. The alternatives were checked too: the keyboard collection cannot be opened for reading from user
mode, `HidD_GetInputReport` on it fails, `KeyMagic`'s control device (`\\.\AppleKeyboard`) has no IOCTL for Fn state
or keymaps, and the registry `Keymap` / `KeymapFn` / `KeymapNumlock` tables only rewrite the six key slots and never
touch the modifier byte. Details: [docs/KeyMagic-internals.md](docs/KeyMagic-internals.md).

## The patch

`patcher/patch_keymagic.py` reads the `KeyMagic.sys` already installed on your machine and writes a patched
copy. It ships no Apple binary. At the point where the driver has located the modifier byte and the Fn flag,
40 bytes of added code swap them:

```
Ctrl bit := Fn flag was set
Fn flag  := Left Ctrl bit was set
```

The physical Fn key then produces a real Left Ctrl, and the physical Control key drives the driver's own
Fn logic (arrows to Home/End/PgUp/PgDn, Backspace to Delete, the F-row mode).

```
python patcher/patch_keymagic.py --check      # verify your driver build is patchable, writes nothing
python patcher/patch_keymagic.py              # writes KeyMagicFnSwap.sys (unsigned)
```

The patch site is found by byte signature. It was developed against `KeyMagic.sys` 6.1.8086.1,
SHA-256 `a92d0bff926f23cd28191a0ff77b9a60b2a92d44b62db27f1610d4e3aefac8d8`.

### Install (Windows PowerShell 5.1 or PowerShell 7)

Loading a modified kernel driver on 64-bit Windows needs a signature your machine trusts. The simplest setup is
test-signing mode (`bcdedit /set testsigning on`, reboot; requires Secure Boot off, which is the case for
Boot Camp on Intel Macs) plus the Windows SDK's `signtool`.

```
powershell -File patcher\Install-FnCtrlSwap.ps1 -Driver KeyMagicFnSwap.sys
```

The script asks for elevation once (UAC), finds a usable code-signing certificate in `LocalMachine\My`
automatically (or asks which, or offers a confirm-first wizard to create and trust a self-signed one), signs the
copy, installs it as `System32\drivers\KeyMagicFnSwap.sys`, and points the `KeyMagic` service `ImagePath` at it.
The original `KeyMagic.sys` is never modified and the old path is saved as `ImagePath.orig`. Everything is logged
to `patcher\install.log`. Reboot to load it.

```
powershell -File patcher\Uninstall-FnCtrlSwap.ps1     # restore the original driver path, then reboot
```

Recovery without the script (for example from WinRE, or if the keyboard is dead):
`reg add HKLM\SYSTEM\CurrentControlSet\Services\KeyMagic /v ImagePath /t REG_EXPAND_SZ /d \SystemRoot\System32\drivers\KeyMagic.sys /f`

## Risks

`KeyMagic` is a lower filter for the keyboard. A broken replacement can leave the built-in keyboard dead until
you restore the original, so keep an external USB keyboard (KeyMagic only filters Apple keyboards) or remote
access available the first time. Test-signing mode lowers Windows' driver-signing protection and shows a desktop
watermark. A Boot Camp reinstall or update may restore the stock `ImagePath`; run the installer again.

## User-mode only? (honourable mention)

Without touching the driver you can get part of the way, but not all of it:

* **Control acting as Fn** works in user mode: a low-level keyboard hook can watch for Left Ctrl and translate
  arrows, Backspace and Return into Home/End/PgUp/PgDn, Delete and Insert.
* **Fn acting as Ctrl** cannot be done cleanly: Fn is invisible until another key is pressed. Remapping keys through
  `KeymapFn` to spare usages would give Ctrl+key combos, but never Ctrl+click or Ctrl+scroll.

Neither is implemented here; the driver patch does both properly.

## Repo layout

| path | what it is |
|---|---|
| `patcher/patch_keymagic.py` | builds the patched copy of your local `KeyMagic.sys` |
| `patcher/Install-FnCtrlSwap.ps1`, `Uninstall-FnCtrlSwap.ps1` | sign + install / roll back (PowerShell 5.1 and 7) |
| `tools/FnWatch.cs` | key-event logger (low-level hook); build with the in-box `csc.exe` |
| `tools/hidcaps.py` | dumps HID collections and usages; shows the Fn bit in the keyboard report |
| `docs/KeyMagic-internals.md` | report layout, code paths, tables, IOCTLs, how the analysis was done |

## Compatibility

Confirmed on: MacBook Air A1465 (MacBookAir6,1), keyboard `USB\VID_05AC&PID_0290`. `KeyMagic`'s `KeyboardTable`
lists about 70 Apple keyboard product IDs, so other Boot Camp MacBooks likely share the code path, but that is
untested; reports welcome.

## Legal

Independent interoperability research on hardware the author owns. Not affiliated with or endorsed by Apple.
"Apple", "MacBook" and "Boot Camp" are trademarks of Apple Inc. No Apple binaries are distributed here.

## License

MIT, see [LICENSE](LICENSE).

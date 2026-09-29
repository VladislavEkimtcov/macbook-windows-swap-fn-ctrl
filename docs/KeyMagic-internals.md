# How Apple's `KeyMagic.sys` handles the Fn key (Boot Camp 6.1.8086)

Reverse-engineered by static disassembly of `KeyMagic.sys` 6.1.8086.1 (SHA-256
`a92d0bff926f23cd28191a0ff77b9a60b2a92d44b62db27f1610d4e3aefac8d8`), plus live capture on a
MacBook Air A1465 (`MacBookAir6,1`, USB `VID_05AC&PID_0290`). Addresses are RVAs in that build.
Method: parse the PE by hand, take exact function boundaries from `.pdata`, disassemble one function at a
time with Python + `capstone` (a linear sweep of the whole section with detail on can exhaust memory), and
follow rip-relative references to strings and data tables. `tools/hidcaps.py` produced the report layout.

## Where it sits

`USB\VID_05AC&PID_0290&MI_01` (the keyboard interface) has service `HidUsb` with
`LowerFilters = KeyMagic`. KeyMagic sees each raw USB input report *before* the HID class driver
parses it, and rewrites the report in place. `kbdhid` then turns the rewritten report into key events.
The collection `HID\...&MI_01&COL01` is owned by `kbdhid`, so user mode cannot open it for reading
(`ERROR_ACCESS_DENIED`), and `HidD_GetInputReport` on it fails.

## The report

Report ID 1, 10 bytes (from `HidP_GetCaps` on the collection, plus the driver's byte offsets):

| byte | meaning |
|---|---|
| 0 | report ID (1) |
| 1 | modifiers (bit0 LCtrl, bit1 LShift, bit2 LAlt, bit3 LGui, bit4 RCtrl, ...) |
| 2 | reserved |
| 3-8 | six key slots (HID keyboard usages) |
| 9 | bit0: Eject (consumer 0xB8), **bit1: Fn** (vendor usage page 0xFF, usage 0x03) |

(An 8-byte report variant, used by other Apple keyboards, keeps the Fn flag in bit0 of byte 7.)

## What the driver does with Fn

`3b88` is the per-report routine (context in `rcx`, report in `rdx`, length in `r8`). For a
10-byte report it computes `r12 = &report[1]` (modifiers) and `r13b = report[9] & 2` (Fn) at `3d63`.
`r13b` is then used **only** to choose a code path:

* Fn set: `1740` applies the fixed translations (Backspace→Delete, arrows→Home/End/PgUp/PgDn,
  Return→Insert, and Ctrl+Alt+Backspace→Ctrl+Alt+Delete), `1220` handles the F-row, then the
  **`KeymapFn`** table is applied to the key slots.
* Fn clear: `1220` (if the F-row mode flag is set), then the **`Keymap`** table, then
  **`KeymapNumlock`** if NumLock is active.

The Fn flag is not copied anywhere that reaches Windows. That is why Fn produces no scan code, no
virtual key and no Raw Input event: it does not exist above this filter.

### Live capture (low-level keyboard hook, built-in keyboard)

| pressed | Windows saw |
|---|---|
| `a` | VK 0x41 |
| Fn alone | nothing |
| Left Control | VK 0xA2, scan 0x1D |
| Fn + Backspace | VK_DELETE (0x2E) |
| Fn + Left | VK_HOME (0x24) |
| Fn + Return | VK_INSERT (0x2D) |
| F1 / F5 | VK_F1 / VK_F5 (standard function keys) |
| Fn + F1 | nothing (brightness is handled below the key layer) |

## The three tables

Registry values on `HKLM\SYSTEM\CurrentControlSet\Services\KeyMagic`, type `REG_BINARY`, written by the
Boot Camp INF (`[HIDKbFlt_Service_AddReg]`). Each is a list of `(source usage, target usage)` byte
pairs, at most 256 pairs, loaded into the device context by `35c0`:

| value | context offset | applied when |
|---|---|---|
| `Keymap` | `+0xa4` (count `+0x2a4`) | Fn not held |
| `KeymapFn` | `+0x2a8` (count `+0x4a8`) | Fn held |
| `KeymapNumlock` | `+0x4ac` (count `+0x6ac`) | NumLock overlay active |

Default `Keymap` = `69 46  6a 47  6b 48  91 8b  90 88` (F18→PrintScreen, F19→ScrollLock, F20→Pause, ...).
Default `KeymapFn` is the embedded-numpad overlay (`0d 1e`: J→1, `0e 1f`: K→2, ...).

**The tables only rewrite the six key slots. They never read or write the modifier byte**, so no
value in them can turn Fn into Ctrl. Other registry values read at start-up: `enable`, `NoSetEvent`,
`OSXFnBehavior` (functions `10d8`, `1118`, `1158`).

## The control device

`\\.\AppleKeyboard` (`\Device\AppleKeyboard`) takes these IOCTLs (dispatcher `2810`):

| code | effect |
|---|---|
| `0xB4032018` | get F-row mode (`ctx+0x84`) |
| `0xB403201C` | `IOCTL_KEYBOARD_SET_OSX_FN_BEHAVIOR`: set F-row mode |
| `0xB4032020` / `24` | enable / disable the keyboard-activity ping (`ctx+0x89`) |
| `0xB4032048` | brightness available |

No IOCTL reads the Fn state or sets a keymap. `\\.\KeyManager` (the notification device) is
`Degraded` on the test machine.

## Consequence

Nothing above `KeyMagic.sys` can observe Fn, and nothing in its configuration can change the
modifier byte. Swapping Fn and Ctrl therefore needs a change *inside* the report handler.
`patcher/patch_keymagic.py` makes one: at `3d63` it swaps `Ctrl := Fn` and `Fn := Ctrl` before
`r13b` is consulted.

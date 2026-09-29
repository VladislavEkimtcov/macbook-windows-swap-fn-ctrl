#!/usr/bin/env python3
"""
hidcaps.py - list the HID collections of Apple (VID 05AC) devices with their input/output/feature usages.

This is how the Fn key was found: on the built-in keyboard, collection MI_01&COL01 (Generic Desktop /
Keyboard) has report ID 1 with the normal keyboard usages *plus* a vendor value, usage page 0xFF usage 0x03
- the Fn bit - which Windows' keyboard stack ignores.

    python hidcaps.py [vid_substring]        # default: vid_05ac
"""
import ctypes as C
import sys

from hidlib import hid, k32, paths, INV


class CAPS(C.Structure):
    _fields_ = [('Usage', C.c_ushort), ('UsagePage', C.c_ushort), ('InLen', C.c_ushort), ('OutLen', C.c_ushort),
                ('FeatLen', C.c_ushort), ('res', C.c_ushort * 17), ('NumLinkColl', C.c_ushort),
                ('NumInBtn', C.c_ushort), ('NumOutBtn', C.c_ushort), ('NumFeatBtn', C.c_ushort),
                ('NumInVal', C.c_ushort), ('NumOutVal', C.c_ushort), ('NumFeatVal', C.c_ushort),
                ('NumInData', C.c_ushort), ('NumOutData', C.c_ushort), ('NumFeatData', C.c_ushort)]


class RANGE(C.Structure):
    _fields_ = [('UsageMin', C.c_ushort), ('UsageMax', C.c_ushort), ('StrMin', C.c_ushort), ('StrMax', C.c_ushort),
                ('DesMin', C.c_ushort), ('DesMax', C.c_ushort), ('DataMin', C.c_ushort), ('DataMax', C.c_ushort)]


class NOTRANGE(C.Structure):
    _fields_ = [('Usage', C.c_ushort), ('r1', C.c_ushort), ('StrIdx', C.c_ushort), ('r2', C.c_ushort),
                ('DesIdx', C.c_ushort), ('r3', C.c_ushort), ('DataIdx', C.c_ushort), ('r4', C.c_ushort)]


class U(C.Union):
    _fields_ = [('R', RANGE), ('N', NOTRANGE)]


class BCAPS(C.Structure):      # HIDP_BUTTON_CAPS (72 bytes)
    _fields_ = [('UsagePage', C.c_ushort), ('ReportID', C.c_ubyte), ('IsAlias', C.c_ubyte), ('BitField', C.c_ushort),
                ('LinkColl', C.c_ushort), ('LinkUsage', C.c_ushort), ('LinkUsagePage', C.c_ushort),
                ('IsRange', C.c_ubyte), ('IsStrRange', C.c_ubyte), ('IsDesRange', C.c_ubyte), ('IsAbs', C.c_ubyte),
                ('res', C.c_ulong * 10), ('u', U)]


class VCAPS(C.Structure):      # HIDP_VALUE_CAPS (72 bytes)
    _fields_ = [('UsagePage', C.c_ushort), ('ReportID', C.c_ubyte), ('IsAlias', C.c_ubyte), ('BitField', C.c_ushort),
                ('LinkColl', C.c_ushort), ('LinkUsage', C.c_ushort), ('LinkUsagePage', C.c_ushort),
                ('IsRange', C.c_ubyte), ('IsStrRange', C.c_ubyte), ('IsDesRange', C.c_ubyte), ('IsAbs', C.c_ubyte),
                ('HasNull', C.c_ubyte), ('r', C.c_ubyte), ('BitSize', C.c_ushort), ('ReportCount', C.c_ushort),
                ('r2', C.c_ushort * 5), ('UnitsExp', C.c_ulong), ('Units', C.c_ulong),
                ('LogMin', C.c_long), ('LogMax', C.c_long), ('PhysMin', C.c_long), ('PhysMax', C.c_long), ('u', U)]


def usage_str(x):
    return ('0x%02X-0x%02X' % (x.u.R.UsageMin, x.u.R.UsageMax)) if x.IsRange else '0x%02X' % x.u.N.Usage


def main():
    match = sys.argv[1].lower() if len(sys.argv) > 1 else 'vid_05ac'
    for path in paths(match):
        h = k32.CreateFileW(path, 0, 3, None, 3, 0, None)     # access 0: query only, works on system keyboards
        print('\n==', path)
        if h in (None, INV):
            print('  open failed, error', C.get_last_error())
            continue
        pp = C.c_void_p()
        if not hid.HidD_GetPreparsedData(C.c_void_p(h), C.byref(pp)):
            print('  no preparsed data')
            k32.CloseHandle(C.c_void_p(h))
            continue
        c = CAPS()
        hid.HidP_GetCaps(pp, C.byref(c))
        print('  UsagePage=0x%04X Usage=0x%02X  in=%d out=%d feature=%d bytes' % (c.UsagePage, c.Usage, c.InLen, c.OutLen, c.FeatLen))
        for kind, name, nb, nv in ((0, 'Input', c.NumInBtn, c.NumInVal), (1, 'Output', c.NumOutBtn, c.NumOutVal),
                                   (2, 'Feature', c.NumFeatBtn, c.NumFeatVal)):
            if nb:
                a = (BCAPS * nb)(); m = C.c_ushort(nb)
                hid.HidP_GetButtonCaps(kind, a, C.byref(m), pp)
                for x in a[:m.value]:
                    print('  %-7s button: page=0x%04X id=%d usage=%s' % (name, x.UsagePage, x.ReportID, usage_str(x)))
            if nv:
                a = (VCAPS * nv)(); m = C.c_ushort(nv)
                hid.HidP_GetValueCaps(kind, a, C.byref(m), pp)
                for x in a[:m.value]:
                    print('  %-7s value : page=0x%04X id=%d usage=%s log=%d..%d' % (name, x.UsagePage, x.ReportID, usage_str(x), x.LogMin, x.LogMax))
        hid.HidD_FreePreparsedData(pp)
        k32.CloseHandle(C.c_void_p(h))


if __name__ == '__main__':
    main()

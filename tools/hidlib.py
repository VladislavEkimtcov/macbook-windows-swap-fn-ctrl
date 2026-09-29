import ctypes as C, ctypes.wintypes as W
hid = C.WinDLL('hid'); sa = C.WinDLL('setupapi'); k32 = C.WinDLL('kernel32', use_last_error=True)
class GUID(C.Structure):
    _fields_ = [('a', C.c_ulong), ('b', C.c_ushort), ('c', C.c_ushort), ('d', C.c_ubyte * 8)]
class SPDID(C.Structure):
    _fields_ = [('cb', W.DWORD), ('g', GUID), ('flags', W.DWORD), ('res', C.c_void_p)]
k32.CreateFileW.restype = C.c_void_p
k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, C.c_void_p]
k32.CloseHandle.argtypes = [C.c_void_p]
sa.SetupDiGetClassDevsW.restype = C.c_void_p
INV = C.c_void_p(-1).value
def paths(match='vid_05ac'):
    g = GUID(); hid.HidD_GetHidGuid(C.byref(g))
    h = sa.SetupDiGetClassDevsW(C.byref(g), None, None, 0x12); i = 0; out = []
    while True:
        d = SPDID(); d.cb = C.sizeof(d)
        if not sa.SetupDiEnumDeviceInterfaces(C.c_void_p(h), None, C.byref(g), i, C.byref(d)): break
        i += 1
        n = W.DWORD(); sa.SetupDiGetDeviceInterfaceDetailW(C.c_void_p(h), C.byref(d), None, 0, C.byref(n), None)
        buf = C.create_string_buffer(n.value); C.cast(buf, C.POINTER(W.DWORD))[0] = 8
        sa.SetupDiGetDeviceInterfaceDetailW(C.c_void_p(h), C.byref(d), buf, n, None, None)
        p = C.wstring_at(C.addressof(buf) + 4)
        if match in p.lower(): out.append(p)
    return out

// FnWatch: logs every key event Windows delivers (WH_KEYBOARD_LL): virtual key, scan code, flags.
// Use it to see what the built-in Apple keyboard really sends. Before the KeyMagic patch, pressing Fn
// alone logs nothing; after it, the physical Fn key logs as Left Ctrl (vk 0xA2).
//
// Build (in-box compiler, no SDK needed):
//   %WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /out:FnWatch.exe FnWatch.cs
// Run:  FnWatch.exe [seconds]      (default 30)
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

static class FnWatch
{
    const int WH_KEYBOARD_LL = 13;
    delegate IntPtr HookProc(int code, IntPtr w, IntPtr l);

    [StructLayout(LayoutKind.Sequential)]
    struct KBDLL { public uint vk, scan, flags, time; public IntPtr extra; }

    [StructLayout(LayoutKind.Sequential)]
    struct MSG { public IntPtr hwnd; public uint message; public IntPtr w, l; public uint time; public int x, y; }

    [DllImport("user32.dll", SetLastError = true)] static extern IntPtr SetWindowsHookEx(int id, HookProc fn, IntPtr mod, uint tid);
    [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr h, int c, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool PeekMessage(out MSG m, IntPtr hwnd, uint min, uint max, uint remove);
    [DllImport("user32.dll")] static extern bool TranslateMessage(ref MSG m);
    [DllImport("user32.dll")] static extern IntPtr DispatchMessage(ref MSG m);
    [DllImport("kernel32.dll")] static extern IntPtr GetModuleHandle(string n);

    static readonly Stopwatch clock = Stopwatch.StartNew();
    static HookProc proc;   // keep rooted so the GC does not collect the callback

    static IntPtr Hook(int code, IntPtr w, IntPtr l)
    {
        if (code >= 0)
        {
            var k = (KBDLL)Marshal.PtrToStructure(l, typeof(KBDLL));
            int m = w.ToInt32();
            string kind = m == 0x100 ? "down" : m == 0x101 ? "up  " : m == 0x104 ? "sdwn" : m == 0x105 ? "sup " : "0x" + m.ToString("X");
            Console.WriteLine("{0,8:F3}  {1} vk=0x{2:X2} scan=0x{3:X2} flags=0x{4:X2}{5}{6}",
                clock.Elapsed.TotalSeconds, kind, k.vk, k.scan, k.flags,
                (k.flags & 1) != 0 ? " EXT" : "", (k.flags & 0x10) != 0 ? " INJECTED" : "");
        }
        return CallNextHookEx(IntPtr.Zero, code, w, l);
    }

    static void Main(string[] a)
    {
        int seconds = a.Length > 0 ? int.Parse(a[0]) : 30;
        proc = Hook;
        IntPtr hook = SetWindowsHookEx(WH_KEYBOARD_LL, proc, GetModuleHandle(null), 0);
        if (hook == IntPtr.Zero) { Console.Error.WriteLine("SetWindowsHookEx failed: " + Marshal.GetLastWin32Error()); return; }
        Console.WriteLine("watching for {0} s - press keys", seconds);
        var end = DateTime.UtcNow.AddSeconds(seconds);
        MSG msg;
        while (DateTime.UtcNow < end)
        {
            while (PeekMessage(out msg, IntPtr.Zero, 0, 0, 1)) { TranslateMessage(ref msg); DispatchMessage(ref msg); }
            System.Threading.Thread.Sleep(2);
        }
        UnhookWindowsHookEx(hook);
    }
}

// FnWatch: passive watcher. Logs everything user mode can see from the built-in
// Apple keyboard: WH_KEYBOARD_LL events, and Raw Input for keyboard, consumer and
// Apple vendor collections (RIM_TYPEHID raw reports, with the device they came from).
// Build: csc /nologo /t:exe /out:FnWatch.exe /r:System.Windows.Forms.dll FnWatch.cs
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

static class FnWatch
{
    const int WH_KEYBOARD_LL = 13, WM_INPUT = 0x00FF;
    const uint RIDEV_INPUTSINK = 0x100, RIDEV_DEVNOTIFY = 0x2000;
    const uint RID_INPUT = 0x10000003, RIDI_DEVICENAME = 0x20000007;

    delegate IntPtr HookProc(int code, IntPtr w, IntPtr l);

    [StructLayout(LayoutKind.Sequential)]
    struct KBDLL { public uint vk, scan, flags, time; public IntPtr extra; }

    [StructLayout(LayoutKind.Sequential)]
    struct RID { public ushort page, usage; public uint flags; public IntPtr target; }

    [DllImport("user32.dll", SetLastError = true)] static extern IntPtr SetWindowsHookEx(int id, HookProc fn, IntPtr mod, uint tid);
    [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr h, int c, IntPtr w, IntPtr l);
    [DllImport("kernel32.dll")] static extern IntPtr GetModuleHandle(string n);
    [DllImport("user32.dll", SetLastError = true)] static extern bool RegisterRawInputDevices(RID[] d, uint n, uint size);
    [DllImport("user32.dll")] static extern uint GetRawInputData(IntPtr h, uint cmd, byte[] data, ref uint size, uint hdr);
    [DllImport("user32.dll")] static extern uint GetRawInputDeviceInfo(IntPtr dev, uint cmd, StringBuilder data, ref uint size);

    static Stopwatch clock = Stopwatch.StartNew();
    static StreamWriter log;
    static HookProc proc;
    static Dictionary<long, string> names = new Dictionary<long, string>();

    static void Log(string s)
    {
        string line = string.Format("{0,8:F3}  {1}", clock.Elapsed.TotalSeconds, s);
        Console.WriteLine(line);
        log.WriteLine(line);
    }

    static string DevName(IntPtr h)
    {
        string n;
        if (names.TryGetValue(h.ToInt64(), out n)) return n;
        uint sz = 0; GetRawInputDeviceInfo(h, RIDI_DEVICENAME, null, ref sz);
        var sb = new StringBuilder((int)sz + 1);
        GetRawInputDeviceInfo(h, RIDI_DEVICENAME, sb, ref sz);
        string full = sb.ToString().ToLowerInvariant();
        int a = full.IndexOf("vid_"), b = full.IndexOf('#', a < 0 ? 0 : a);
        n = a >= 0 && b > a ? full.Substring(a, b - a) : full;
        names[h.ToInt64()] = n;
        return n;
    }

    static IntPtr Hook(int code, IntPtr w, IntPtr l)
    {
        if (code >= 0)
        {
            var k = (KBDLL)Marshal.PtrToStructure(l, typeof(KBDLL));
            int m = w.ToInt32();
            string kind = m == 0x100 ? "down" : m == 0x101 ? "up  " : m == 0x104 ? "sdwn" : m == 0x105 ? "sup " : "0x" + m.ToString("X");
            Log(string.Format("LL   {0} vk=0x{1:X2} scan=0x{2:X2} flags=0x{3:X2}{4}{5}", kind, k.vk, k.scan, k.flags,
                (k.flags & 1) != 0 ? " EXT" : "", (k.flags & 0x10) != 0 ? " INJECTED" : ""));
        }
        return CallNextHookEx(IntPtr.Zero, code, w, l);
    }

    class Win : NativeWindow
    {
        public Win() { CreateHandle(new CreateParams()); }
        protected override void WndProc(ref Message m)
        {
            if (m.Msg == WM_INPUT) OnRaw(m.LParam);
            base.WndProc(ref m);
        }
    }

    static void OnRaw(IntPtr hRaw)
    {
        uint size = 0, hdr = (uint)(8 + 2 * IntPtr.Size);
        GetRawInputData(hRaw, RID_INPUT, null, ref size, hdr);
        var buf = new byte[size];
        if (GetRawInputData(hRaw, RID_INPUT, buf, ref size, hdr) != size) return;
        int type = BitConverter.ToInt32(buf, 0);
        IntPtr dev = new IntPtr(IntPtr.Size == 8 ? BitConverter.ToInt64(buf, 8) : BitConverter.ToInt32(buf, 8));
        int o = (int)hdr;
        string d = DevName(dev);
        if (type == 1)   // RIM_TYPEKEYBOARD
        {
            ushort make = BitConverter.ToUInt16(buf, o), flags = BitConverter.ToUInt16(buf, o + 2), vk = BitConverter.ToUInt16(buf, o + 6);
            Log(string.Format("RAW  kbd  {0}  make=0x{1:X2} flags={2} vk=0x{3:X2}", d, make, (flags & 1) != 0 ? "BREAK" : "make ", vk));
        }
        else if (type == 2)   // RIM_TYPEHID
        {
            uint each = BitConverter.ToUInt32(buf, o), count = BitConverter.ToUInt32(buf, o + 4);
            for (int i = 0; i < count; i++)
            {
                var sb = new StringBuilder();
                for (int j = 0; j < each && j < 24; j++) sb.Append(buf[o + 8 + i * each + j].ToString("x2")).Append(' ');
                Log(string.Format("RAW  hid  {0}  [{1}b] {2}", d, each, sb.ToString().TrimEnd()));
            }
        }
    }

    [STAThread]
    static void Main(string[] a)
    {
        int seconds = a.Length > 0 ? int.Parse(a[0]) : 30;
        log = new StreamWriter(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "fnwatch.log"), false);
        log.AutoFlush = true;
        proc = Hook;
        IntPtr hook = SetWindowsHookEx(WH_KEYBOARD_LL, proc, GetModuleHandle(null), 0);
        var w = new Win();
        var reg = new RID[] {
            new RID { page = 1,      usage = 6, flags = RIDEV_INPUTSINK | RIDEV_DEVNOTIFY, target = w.Handle },
            new RID { page = 0x0C,   usage = 1, flags = RIDEV_INPUTSINK, target = w.Handle },
            new RID { page = 0xFF00, usage = 6, flags = RIDEV_INPUTSINK, target = w.Handle },
            new RID { page = 0xFF00, usage = 1, flags = RIDEV_INPUTSINK, target = w.Handle },
        };
        Log("RegisterRawInputDevices: " + RegisterRawInputDevices(reg, (uint)reg.Length, (uint)Marshal.SizeOf(typeof(RID)))
            + " err=" + Marshal.GetLastWin32Error());
        Log("watching for " + seconds + " s");
        var end = DateTime.UtcNow.AddSeconds(seconds);
        while (DateTime.UtcNow < end) { Application.DoEvents(); System.Threading.Thread.Sleep(2); }
        UnhookWindowsHookEx(hook);
        Log("done");
    }
}

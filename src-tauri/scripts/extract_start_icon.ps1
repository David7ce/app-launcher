# Render the shell's own icon for a Start Menu entry, given its AppID, as a PNG.
#
# Last-resort extractor for entries with neither an exe path nor a package
# manifest to read a logo from — classic apps registered by bare AppID (AdGuard,
# Adobe Acrobat, Raindrop) and system entries (Control Panel, WSL). The shell can
# render any Start tile, so this covers everything the other two cannot.
param([string]$AppId, [string]$Out)
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class StartTileIcon {
    [StructLayout(LayoutKind.Sequential)] struct SIZE { public int cx, cy; }
    [StructLayout(LayoutKind.Sequential)] struct BITMAP {
        public int bmType, bmWidth, bmHeight, bmWidthBytes;
        public short bmPlanes, bmBitsPixel;
        public IntPtr bmBits;
    }
    [StructLayout(LayoutKind.Sequential)] struct BITMAPINFOHEADER {
        public int biSize, biWidth, biHeight;
        public short biPlanes, biBitCount;
        public int biCompression, biSizeImage, biXPelsPerMeter, biYPelsPerMeter, biClrUsed, biClrImportant;
    }
    [StructLayout(LayoutKind.Sequential)] struct DIBSECTION {
        public BITMAP dsBm;
        public BITMAPINFOHEADER dsBmih;
        public int dsBitfields0, dsBitfields1, dsBitfields2;
        public IntPtr dshSection;
        public int dsOffset;
    }
    [ComImport, Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellItemImageFactory {
        [PreserveSig] int GetImage(SIZE size, int flags, out IntPtr phbm);
    }
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern void SHCreateItemFromParsingName(string path, IntPtr pbc, ref Guid riid,
        [MarshalAs(UnmanagedType.Interface)] out IShellItemImageFactory item);
    [DllImport("gdi32.dll")] static extern int GetObject(IntPtr h, int cb, ref DIBSECTION ds);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr h);

    // Renders the shell's own icon for `parsingName` (e.g. shell:AppsFolder\<AppID>).
    public static bool Save(string parsingName, int px, string outPath) {
        Guid iid = new Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b");
        IShellItemImageFactory factory;
        SHCreateItemFromParsingName(parsingName, IntPtr.Zero, ref iid, out factory);
        IntPtr hbm;
        // SIIGBF_BIGGERSIZEOK (1) | SIIGBF_ICONONLY (4): the icon, never a thumbnail.
        if (factory.GetImage(new SIZE { cx = px, cy = px }, 1 | 4, out hbm) != 0 || hbm == IntPtr.Zero) return false;
        try {
            DIBSECTION ds = new DIBSECTION();
            GetObject(hbm, Marshal.SizeOf(typeof(DIBSECTION)), ref ds);
            BITMAP bm = ds.dsBm;
            if (bm.bmBitsPixel != 32 || bm.bmBits == IntPtr.Zero) return false;
            // A positive biHeight is a bottom-up DIB: the first row in memory is the
            // *bottom* of the picture. Wrapping it as top-down draws it upside down
            // (the shell hands these out), so flip it back.
            bool bottomUp = ds.dsBmih.biHeight > 0;
            // The DIB is premultiplied ARGB; wrap it, then copy so it outlives the handle.
            using (Bitmap wrapped = new Bitmap(bm.bmWidth, bm.bmHeight, bm.bmWidthBytes, PixelFormat.Format32bppPArgb, bm.bmBits))
            using (Bitmap copy = new Bitmap(wrapped.Width, wrapped.Height, PixelFormat.Format32bppArgb)) {
                using (Graphics g = Graphics.FromImage(copy)) { g.Clear(Color.Transparent); g.DrawImage(wrapped, 0, 0, wrapped.Width, wrapped.Height); }
                if (bottomUp) copy.RotateFlip(RotateFlipType.RotateNoneFlipY);
                copy.Save(outPath, ImageFormat.Png);
            }
            return true;
        } finally { DeleteObject(hbm); }
    }
}
'@
try { if ([StartTileIcon]::Save("shell:AppsFolder\$AppId", 256, $Out)) { exit 0 } else { exit 1 } } catch { exit 1 }

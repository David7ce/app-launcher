# Pull an executable's own icon out of its embedded resources as a PNG.
# Shared by the running app (src-tauri/src/lib.rs, for tiles with no shipped
# icon) and tools/scan_system_apps_windows.py (authoring-time scan).
#
# `PrivateExtractIcons` asked for 256x256 returns the largest size the exe
# actually embeds; the usual `ExtractAssociatedIcon` always yields a blurry
# 32x32. Pure Python/Rust can't read a PE resource section without pulling in
# a dependency, and System.Drawing ships with every Windows.
param([string]$Exe, [string]$Out)
Add-Type -AssemblyName System.Drawing
$sig = @'
[DllImport("user32.dll", CharSet=CharSet.Unicode)]
public static extern int PrivateExtractIcons(string lpszFile, int nIconIndex, int cxIcon, int cyIcon,
    IntPtr[] phicon, int[] piconid, int nIcons, int flags);
[DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr h);
'@
Add-Type -MemberDefinition $sig -Name Ico -Namespace Ex | Out-Null
$h = New-Object IntPtr[] 1
$id = New-Object int[] 1
$n = [Ex.Ico]::PrivateExtractIcons($Exe, 0, 256, 256, $h, $id, 1, 0)
if ($n -le 0 -or $h[0] -eq [IntPtr]::Zero) { exit 1 }
try {
    $bmp = [System.Drawing.Bitmap]::FromHicon($h[0])
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
} finally {
    [Ex.Ico]::DestroyIcon($h[0]) | Out-Null
}

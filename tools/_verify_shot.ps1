Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$sig = @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool repaint);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
public struct RECT { public int L, T, R, B; }
'@
Add-Type -MemberDefinition $sig -Name Win -Namespace Shot | Out-Null

$p = Get-Process app-launcher -ErrorAction Stop
$h = $p.MainWindowHandle
# The window opened on a secondary monitor at negative coords; move it onto
# the primary display so a screen-grab actually captures it.
[Shot.Win]::MoveWindow($h, 40, 40, 1300, 900, $true) | Out-Null
[Shot.Win]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 1500

$r = New-Object Shot.Win+RECT
[Shot.Win]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.R - $r.L
$ht = $r.B - $r.T
Write-Host "window: $w x $ht at ($($r.L),$($r.T))"

$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
$out = Join-Path $env:TEMP 'verify2.png'
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
Write-Host "saved: $out"

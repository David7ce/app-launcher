# Copy the logo of a packaged (MSIX/UWP/Store) Start Menu app to a PNG.
#
# Such apps have no exe to pull an icon from. Their AppID is
# `<PackageFamilyName>!<ApplicationId>`; the package manifest names a
# Square44x44Logo, and the package folder holds it in many scale/target-size
# variants (`Logo.targetsize-256.png`, `Logo.scale-200.png`, ...). Pick the
# largest plain one: no high-contrast or light-unplated variants, and prefer
# an "unplated" (transparent) one over the tile-backed default.
param([string]$AppId, [string]$Out)
$family, $applicationId = $AppId.Split('!')
if (-not $family -or -not $applicationId) { exit 1 }
# -Name is much faster than listing every package; the family name is
# "<Name>_<PublisherId>".
$pkg = Get-AppxPackage -Name $family.Split('_')[0] -ErrorAction SilentlyContinue |
    Where-Object { $_.PackageFamilyName -eq $family } | Select-Object -First 1
if (-not $pkg) { exit 1 }

$manifest = [xml](Get-Content -LiteralPath (Join-Path $pkg.InstallLocation 'AppxManifest.xml') -Raw)
$app = $manifest.Package.Applications.Application | Where-Object { $_.Id -eq $applicationId } | Select-Object -First 1
$logo = $app.VisualElements.Square44x44Logo
if (-not $logo) { $logo = $app.VisualElements.Square150x150Logo }
if (-not $logo) { exit 1 }

$logoPath = Join-Path $pkg.InstallLocation $logo
$dir = Split-Path $logoPath
$base = [IO.Path]::GetFileNameWithoutExtension($logoPath)

function Score([string]$name) {
    if ($name -match 'contrast|lightunplated') { return -1 }
    $unplated = if ($name -match 'unplated') { 0.5 } else { 0 }
    if ($name -match 'targetsize-(\d+)') { return [double]$Matches[1] + $unplated }
    if ($name -match 'scale-(\d+)') { return 44 * [double]$Matches[1] / 100 + $unplated }
    return 1 + $unplated   # the bare, unscaled file
}

$best = Get-ChildItem -LiteralPath $dir -Filter "$base*.png" -ErrorAction SilentlyContinue |
    Where-Object { (Score $_.Name) -ge 0 } |
    Sort-Object { Score $_.Name } -Descending | Select-Object -First 1
if (-not $best) { exit 1 }
Copy-Item -LiteralPath $best.FullName -Destination $Out -Force

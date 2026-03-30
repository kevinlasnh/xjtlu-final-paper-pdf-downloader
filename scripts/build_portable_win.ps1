param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"
$PortableRoot = Join-Path $DistRoot "portable-win"
$ReleaseRoot = Join-Path $DistRoot "release"

New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null

& $PythonExe -m pip install -r (Join-Path $ProjectRoot "requirements.txt") pyinstaller
& $PythonExe -m playwright install chromium

$BrowserPath = & $PythonExe -m playwright install --dry-run chromium | Select-String "Install location:" | Select-Object -First 1
if (-not $BrowserPath) {
    throw "Unable to resolve Playwright browser installation path."
}

$ResolvedBrowserPath = ($BrowserPath.ToString() -split "Install location:\s+")[1].Trim()
$BrowserRoot = Split-Path -Parent $ResolvedBrowserPath
$env:XJTLU_PLAYWRIGHT_BROWSERS = $BrowserRoot

Remove-Item -Recurse -Force $PortableRoot -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $BuildRoot -ErrorAction SilentlyContinue

& $PythonExe -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot "desktop_app.spec")

$BundledBrowserRoot = Join-Path $ProjectRoot "dist\\XJTLU_PDF_Downloader\\ms-playwright"
New-Item -ItemType Directory -Force -Path $BundledBrowserRoot | Out-Null
Copy-Item -Recurse -Force (Join-Path $BrowserRoot "*") $BundledBrowserRoot

New-Item -ItemType Directory -Force -Path $PortableRoot | Out-Null
Copy-Item -Recurse -Force (Join-Path $ProjectRoot "dist\\XJTLU_PDF_Downloader\\*") $PortableRoot

$ZipPath = Join-Path $ReleaseRoot "XJTLU-PDF-Downloader-win-x64.zip"
if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}

Compress-Archive -Path (Join-Path $PortableRoot "*") -DestinationPath $ZipPath
Write-Host "Portable Windows package created at $ZipPath"

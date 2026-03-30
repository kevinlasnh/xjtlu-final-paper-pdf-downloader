#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_ROOT="$PROJECT_ROOT/dist"
BUILD_ROOT="$PROJECT_ROOT/build"
PORTABLE_ROOT="$DIST_ROOT/portable-macos"
RELEASE_ROOT="$DIST_ROOT/release"
ASSET_NAME="${1:-XJTLU-PDF-Downloader-macos.zip}"

mkdir -p "$DIST_ROOT" "$RELEASE_ROOT"

python3 -m pip install -r "$PROJECT_ROOT/requirements.txt" pyinstaller
python3 -m playwright install chromium

BROWSER_PATH="$(python3 -m playwright install --dry-run chromium | awk -F'Install location:[[:space:]]+' '/Install location:/ {print $2; exit}')"
if [[ -z "$BROWSER_PATH" ]]; then
  echo "Unable to resolve Playwright browser installation path." >&2
  exit 1
fi

export XJTLU_PLAYWRIGHT_BROWSERS="$(dirname "$BROWSER_PATH")"

rm -rf "$PORTABLE_ROOT" "$BUILD_ROOT"
python3 -m PyInstaller --noconfirm --clean "$PROJECT_ROOT/desktop_app.spec"

BUNDLED_BROWSER_ROOT="$PROJECT_ROOT/dist/XJTLU_PDF_Downloader/ms-playwright"
mkdir -p "$BUNDLED_BROWSER_ROOT"
cp -R "$XJTLU_PLAYWRIGHT_BROWSERS/." "$BUNDLED_BROWSER_ROOT/"

mkdir -p "$PORTABLE_ROOT"
cp -R "$PROJECT_ROOT/dist/XJTLU_PDF_Downloader/." "$PORTABLE_ROOT/"

ZIP_PATH="$RELEASE_ROOT/$ASSET_NAME"
rm -f "$ZIP_PATH"
(cd "$PORTABLE_ROOT" && zip -r "$ZIP_PATH" .)

echo "Portable macOS package created at $ZIP_PATH"

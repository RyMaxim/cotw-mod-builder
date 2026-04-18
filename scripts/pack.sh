#!/bin/sh
# Package Mod Builder - Revived into versioned 7z archives
set -e

VERSION="$(python - <<'PY'
import tomllib
from pathlib import Path

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"

if [ -z "$VERSION" ]; then
  echo "ERROR: could not parse version from pyproject.toml"
  exit 1
fi

if [ ! -d "dist/modbuilder" ]; then
  echo "ERROR: missing built application folder: dist/modbuilder"
  exit 1
fi

if [ ! -d "modbuilder/org" ]; then
  echo "ERROR: missing asset folder: modbuilder/org"
  exit 1
fi

if [ ! -f "modbuilder/org/version.txt" ]; then
  echo "ERROR: missing asset version file: modbuilder/org/version.txt"
  exit 1
fi

if [ ! -f "modbuilder/name_map.yaml" ]; then
  echo "ERROR: missing asset file: modbuilder/name_map.yaml"
  exit 1
fi

if [ ! -f "scripts/INSTALL_ORG_FILES.txt" ]; then
  echo "ERROR: missing instructions file: scripts/INSTALL_ORG_FILES.txt"
  exit 1
fi

APP_ARCHIVE="dist/modbuilder_${VERSION}.7z"
ORG_ARCHIVE="dist/modbuilder_org_${VERSION}.7z"
STAGE_DIR="dist/org_bundle_stage"

rm -f "$APP_ARCHIVE" "$ORG_ARCHIVE"
rm -rf "$STAGE_DIR"

echo "Packaging built application..."
7z a "$APP_ARCHIVE" "dist/modbuilder"

echo "Preparing org asset bundle staging folder..."
mkdir -p "$STAGE_DIR"

cp "scripts/INSTALL_ORG_FILES.txt" "$STAGE_DIR/INSTALL_ORG_FILES.txt"
cp "modbuilder/name_map.yaml" "$STAGE_DIR/name_map.yaml"
cp -R "modbuilder/org" "$STAGE_DIR/org"

echo "Packaging org asset bundle..."
(
  cd "$STAGE_DIR"
  7z a "../modbuilder_org_${VERSION}.7z" "INSTALL_ORG_FILES.txt" "name_map.yaml" "org"
)

rm -rf "$STAGE_DIR"

echo "Done."
echo "Created:"
echo "  $APP_ARCHIVE"
echo "  $ORG_ARCHIVE"
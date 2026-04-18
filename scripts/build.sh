#!/bin/sh
# Build a new Mod Builder - Revived executable for macOS
set -e

if [ ! -d "$(pwd)/modbuilder/org" ]; then
  echo "ERROR: missing modbuilder/org"
  exit 1
fi

rm -rf "$(pwd)/build" "$(pwd)/dist/modbuilder"

python ./scripts/write_build_meta.py
python ./scripts/write_org_version.py

pyinstaller modbuilder.spec
@echo off
REM Build a new Mod Builder - Revived executable for Windows
setlocal

if not exist "%CD%\modbuilder\org" (
  echo ERROR: missing modbuilder\org
  exit /b 1
)

rmdir /s /q "%CD%\build" 2>nul
rmdir /s /q "%CD%\dist\modbuilder" 2>nul

python .\scripts\write_build_meta.py
python .\scripts\write_asset_versions.py

pyinstaller modbuilder.spec
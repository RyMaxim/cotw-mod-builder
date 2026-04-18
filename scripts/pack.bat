@echo off
REM Package Mod Builder - Revived into versioned 7z archives
setlocal

set "VERSION="
for /f "usebackq tokens=2 delims==" %%A in (`findstr /r /c:"^[ ]*version[ ]*=" pyproject.toml`) do (
  for /f "tokens=* delims= " %%B in ("%%~A") do set "VERSION=%%B"
)
set "VERSION=%VERSION:"=%"

if not defined VERSION (
  echo ERROR: could not parse version from pyproject.toml
  exit /b 1
)

if not exist "%CD%\dist\modbuilder" (
  echo ERROR: missing built application folder: %CD%\dist\modbuilder
  exit /b 1
)

if not exist "%CD%\modbuilder\org" (
  echo ERROR: missing asset folder: %CD%\modbuilder\org
  exit /b 1
)

if not exist "%CD%\modbuilder\org\version.txt" (
  echo ERROR: missing asset version file: %CD%\modbuilder\org\version.txt
  exit /b 1
)

if not exist "%CD%\modbuilder\name_map.yaml" (
  echo ERROR: missing asset file: %CD%\modbuilder\name_map.yaml
  exit /b 1
)

if not exist "%CD%\scripts\INSTALL_ORG_FILES.txt" (
  echo ERROR: missing instructions file: %CD%\scripts\INSTALL_ORG_FILES.txt
  exit /b 1
)

set "APP_ARCHIVE=%CD%\dist\modbuilder_%VERSION%.7z"
set "ORG_ARCHIVE=%CD%\dist\modbuilder_org_%VERSION%.7z"
set "STAGE_DIR=%CD%\dist\org_bundle_stage"

del /q "%APP_ARCHIVE%" 2>nul
del /q "%ORG_ARCHIVE%" 2>nul
rmdir /s /q "%STAGE_DIR%" 2>nul

echo Packaging built application...
"C:\Program Files\7-Zip\7z.exe" a "%APP_ARCHIVE%" "%CD%\dist\modbuilder"
if errorlevel 1 (
  echo ERROR: failed to create application archive
  exit /b 1
)

echo Preparing org asset bundle staging folder...
mkdir "%STAGE_DIR%"
if errorlevel 1 (
  echo ERROR: failed to create staging folder
  exit /b 1
)

copy "%CD%\scripts\INSTALL_ORG_FILES.txt" "%STAGE_DIR%\INSTALL_ORG_FILES.txt" >nul
if errorlevel 1 (
  echo ERROR: failed to copy instructions file into staging folder
  exit /b 1
)

copy "%CD%\modbuilder\name_map.yaml" "%STAGE_DIR%\name_map.yaml" >nul
if errorlevel 1 (
  echo ERROR: failed to copy name_map.yaml into staging folder
  exit /b 1
)

xcopy "%CD%\modbuilder\org" "%STAGE_DIR%\org\" /E /I /Y >nul
if errorlevel 1 (
  echo ERROR: failed to copy org folder into staging folder
  exit /b 1
)

echo Packaging org asset bundle...
pushd "%STAGE_DIR%"
"C:\Program Files\7-Zip\7z.exe" a "%ORG_ARCHIVE%" "INSTALL_ORG_FILES.txt" "name_map.yaml" "org"
if errorlevel 1 (
  popd
  echo ERROR: failed to create org asset archive
  exit /b 1
)
popd

rmdir /s /q "%STAGE_DIR%" 2>nul

echo Done.
echo Created:
echo   %APP_ARCHIVE%
echo   %ORG_ARCHIVE%
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from packaging.version import InvalidVersion, Version

from modbuilder.constants import GITHUB_RELEASES_URL, ORG_DIR_NAME, ORG_VERSION_FILENAME


def should_skip_bundle_version_check() -> bool:
    """
    Return whether org bundle version validation should be skipped.

    This is intended for local development only.

    Returns:
        bool: True when the developer explicitly requested to bypass
            org bundle version checks, otherwise False.
    """
    return os.getenv("MODBUILDER_SKIP_BUNDLE_VERSION_CHECK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_frozen() -> bool:
    """
    Return whether the application is running as a frozen PyInstaller build.

    Returns:
        bool: True when running from a frozen build, otherwise False.
    """
    return bool(getattr(sys, "_MEIPASS", None))


def get_app_dir_path() -> Path:
    """
    Return the application resource root for both source and PyInstaller builds.

    Source runs resolve relative to the modbuilder package directory.
    Frozen runs resolve relative to the PyInstaller extraction directory.

    Returns:
        Path: Application resource root.
    """
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def get_name_map_file() -> Path:
    """
    Return the expected name_map.yaml path.

    Returns:
        Path: Path to name_map.yaml.
    """
    return get_app_dir_path() / "name_map.yaml"


def read_name_map_version() -> str | None:
    """
    Read the version value from name_map.yaml.

    Returns:
        str | None: Version string if present and non-empty, otherwise None.
    """
    name_map_file = get_name_map_file()

    with name_map_file.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    version = data.get("version")
    if version is None:
        return None

    version = str(version).strip()
    return version or None


def get_org_dir() -> Path:
    """
    Return the expected org asset directory.

    Returns:
        Path: Path to the org directory.
    """
    return get_app_dir_path() / ORG_DIR_NAME


def get_org_version_file() -> Path:
    """
    Return the org bundle version file path.

    Returns:
        Path: Path to the org version file.
    """
    return get_org_dir() / ORG_VERSION_FILENAME


def normalize_bundle_version(version: Version) -> str:
    """
    Normalize an application or bundle version to its asset compatibility version.
    Asset bundles are compatible across patch releases, so only the major and minor version are compared.

    Examples:
        1.2.0 -> 1.2
        1.2.3 -> 1.2
        1.2.3.dev4 -> 1.2
        1.2.3rc1 -> 1.2

    Args:
        version (Version): Parsed version.

    Returns:
        str: Major/minor compatibility version string.
    """
    major, minor = version.release[:2]
    return f"{major}.{minor}"


def read_org_bundle_version() -> str | None:
    """
    Read the org bundle version from the version file.

    Returns:
        str | None: Version string if present and non-empty, otherwise None.
    """
    version_file = get_org_version_file()
    if not version_file.exists():
        return None

    contents = version_file.read_text(encoding="utf-8").strip()
    return contents or None


def _build_result(
    ok: bool,
    severity: str,
    code: str,
    message: str,
    expected_version: str,
    found_version: str | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, str | bool | None | list[str]]:
    """
    Build a standardized asset bundle validation result.

    Args:
        ok (bool): True when startup may continue.
        severity (str): Result severity ("none", "warning", or "error").
        code (str): Machine-friendly result code.
        message (str): User-facing message.
        expected_version (str): Expected normalized bundle version.
        found_version (str | None): Found version details, if available.
        warnings (list[str] | None): User-facing warning messages.
        errors (list[str] | None): User-facing error messages.

    Returns:
        dict[str, str | bool | None | list[str]]: Standardized validation result.
    """
    return {
        "ok": ok,
        "severity": severity,
        "code": code,
        "message": message,
        "found_version": found_version,
        "expected_version": expected_version,
        "warnings": warnings or [],
        "errors": errors or [],
    }


def _release_help() -> str:
    return (
        "Download + install the latest or matching asset bundle and restart "
        f"Mod Builder:\n{GITHUB_RELEASES_URL}"
    )


def _dev_bypass_help() -> str:
    if is_frozen():
        return ""

    return (
        "\n\nFor local development only, you may bypass version checks by setting:\n"
        "   MODBUILDER_SKIP_BUNDLE_VERSION_CHECK=1\n"
        "or running with:\n"
        "   hatch run dev:modbuilder"
    )


def _version_help(expected_version: str) -> str:
    """
    Build the standard version validation help message.

    Includes the expected version, instructions for obtaining the
    correct asset bundle, and local development bypass information
    when applicable.

    Args:
        expected_version (str): Expected normalized asset bundle version.

    Returns:
        str: User-facing help text for version validation failures.
    """
    return (
        f"Expected version: {expected_version}\n\n"
        f"{_release_help()}"
        f"{_dev_bypass_help()}"
    )


def _read_text_file(path: Path) -> str | None:
    """
    Read and normalize a text file.

    The file contents are stripped of leading and trailing whitespace.
    Empty files are treated as missing and return None.

    Args:
        path (Path): Path to the file to read.

    Returns:
        str | None: Normalized file contents if present and non-empty,
            otherwise None.
    """
    if not path.exists():
        return None

    contents = path.read_text(encoding="utf-8").strip()
    return contents or None


def _read_name_map_yaml_version(path: Path) -> str | None:
    """
    Read the version value from name_map.yaml.

    Args:
        path (Path): Path to name_map.yaml.

    Returns:
        str | None: The version value if present and non-empty,
            otherwise None.
    """
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    version = data.get("version")
    if version is None:
        return None

    version = str(version).strip()
    return version or None


def _validate_required_files(org_dir: Path, name_map_file: Path) -> list[str]:
    """
    Validate that required asset files and folders exist.

    Checks for the presence of:
        - name_map.yaml
        - the org asset directory

    Also verifies that the org directory is not empty.

    Args:
        org_dir (Path): Expected org asset directory.
        name_map_file (Path): Expected name_map.yaml file.

    Returns:
        list[str]: User-facing error messages for any missing or invalid
            required assets. Returns an empty list when all required assets
            are present.
    """
    errors = []

    if not name_map_file.exists():
        errors.append(f"Missing required asset file: {name_map_file}")

    if not org_dir.exists():
        errors.append(f"Missing required asset folder: {org_dir}")
    elif not any(org_dir.iterdir()):
        errors.append(f"The org asset folder is empty: {org_dir}")

    return errors


def _validate_version_value(
    *,
    label: str,
    raw_version: str | None,
    expected_version: str,
    missing_message: str,
) -> tuple[list[str], str | None]:
    """
    Validate a version string against the expected application version.

    The version is considered invalid if it is missing, cannot be parsed
    as a valid semantic version, or does not match the expected normalized
    version.

    Args:
        label (str): Human-readable description of the asset being validated.
        raw_version (str | None): Version string read from the asset.
        expected_version (str): Expected normalized application version.
        missing_message (str): Message displayed when the version is missing.

    Returns:
        tuple[list[str], str | None]:
            warnings (list[str]): User-facing warning messages generated
                during validation.
            found_version (str | None): Raw version string that was found,
                if available.
    """
    warnings = []

    if raw_version is None:
        warnings.append(missing_message)
        return warnings, None

    try:
        parsed_version = Version(raw_version)
    except InvalidVersion:
        warnings.append(f"The {label} version is invalid. Found: {raw_version}")
        return warnings, raw_version

    actual_version = normalize_bundle_version(parsed_version)
    if actual_version != expected_version:
        warnings.append(
            f"The {label} may be outdated. Found version: {raw_version}"
        )

    return warnings, raw_version


def _validate_name_map_version(name_map_file: Path, expected_version: str) -> tuple[list[str], str | None]:
    """
    Validate the version stored in name_map.yaml.

    Args:
        name_map_file (Path): Path to name_map.yaml.
        expected_version (str): Expected normalized application version.

    Returns:
        tuple[list[str], str | None]:
            warnings (list[str]): User-facing warning messages generated
                during validation.
            found_version (str | None): Version read from name_map.yaml,
                if available.
    """
    try:
        raw_version = _read_name_map_yaml_version(name_map_file)
    except Exception as exc:
        return [
            "Unable to read name_map.yaml.\n\n"
            f"Expected file:\n{name_map_file}\n"
            f"Error: {exc}\n\n"
            f"{_release_help()}"
        ], None

    return _validate_version_value(
        label="name_map.yaml asset file",
        raw_version=raw_version,
        expected_version=expected_version,
        missing_message=(f"The name_map.yaml asset version is missing or empty: {name_map_file}"),
    )


def _validate_org_version(version_file: Path, expected_version: str) -> tuple[list[str], str | None]:
    """
    Validate the org asset bundle version file.

    Args:
        version_file (Path): Path to org/version.txt.
        expected_version (str): Expected normalized application version.

    Returns:
        tuple[list[str], str | None]:
            warnings (list[str]): User-facing warning messages generated
                during validation.
            found_version (str | None): Version read from org/version.txt,
                if available.
    """
    raw_version = _read_text_file(version_file)

    return _validate_version_value(
        label="org asset bundle",
        raw_version=raw_version,
        expected_version=expected_version,
        missing_message=(f"The org asset bundle version file is missing or empty: {version_file}"),
    )


def _format_validation_message(
    *,
    errors: list[str],
    warnings: list[str],
    expected_version: str,
) -> str:
    """
    Build the final user-facing validation message.

    Args:
        errors (list[str]): Fatal asset validation errors.
        warnings (list[str]): Non-fatal asset validation warnings.
        expected_version (str): Expected normalized asset bundle version.

    Returns:
        str: User-facing validation message.
    """
    sections = []

    if errors:
        sections.append("Errors:\n\n" + "\n\n".join(f"- {error}" for error in errors))

    if warnings:
        sections.append("Warnings:\n\n" + "\n\n".join(f"- {warning}" for warning in warnings))

    sections.append(
        f"Expected asset compatibility version: {expected_version}.x\n\n"
        "How to fix this:\n\n"
        "Download and install the latest or matching asset bundle, then restart Mod Builder:\n"
        f"{GITHUB_RELEASES_URL}"
        f"{_dev_bypass_help()}"
    )

    return "\n\n---\n\n".join(sections)


def validate_org_bundle(app_version: Version) -> dict[str, str | bool | None]:
    """
    Validate that the org asset bundle exists and, when possible, matches the
    application version.

    Fatal:
        - missing name_map.yaml
        - missing org folder
        - empty org folder

    Warning only:
        - missing version.txt
        - empty version.txt
        - invalid version.txt
        - version mismatch

    Developers may explicitly bypass version-only checks with:
        MODBUILDER_SKIP_BUNDLE_VERSION_CHECK=1

    Args:
        app_version (Version): Current application version.

    Returns:
        dict[str, str | bool | None]: Validation result with fields:
            ok (bool): True when startup may continue.
            severity (str): "none", "warning", or "error".
            code (str): Machine-friendly reason code.
            message (str): User-facing explanation.
            found_version (str | None): Found bundle version if available.
            expected_version (str): Expected base release version.
    """
    org_dir = get_org_dir()
    version_file = get_org_version_file()
    name_map_file = get_name_map_file()
    expected_version = normalize_bundle_version(app_version)

    errors = _validate_required_files(org_dir, name_map_file)

    if errors:
        return _build_result(
            ok=False,
            severity="error",
            code="asset_errors",
            message=_format_validation_message(
                errors=errors,
                warnings=[],
                expected_version=expected_version,
            ),
            expected_version=expected_version,
            errors=errors,
        )

    if should_skip_bundle_version_check():
        return _build_result(
            ok=True,
            severity="none",
            code="ok_version_check_skipped",
            message="",
            expected_version=expected_version,
        )

    warnings = []
    found_versions = []

    name_map_warnings, found_name_map_version = _validate_name_map_version(name_map_file, expected_version)
    org_warnings, found_org_version = _validate_org_version(version_file, expected_version)

    warnings.extend(name_map_warnings)
    warnings.extend(org_warnings)

    if found_name_map_version:
        found_versions.append(f"name_map.yaml={found_name_map_version}")
    if found_org_version:
        found_versions.append(f"org/version.txt={found_org_version}")

    if warnings:
        return _build_result(
            ok=True,
            severity="warning",
            code="asset_warnings",
            message=_format_validation_message(
                errors=[],
                warnings=warnings,
                expected_version=expected_version,
            ),
            expected_version=expected_version,
            found_version=", ".join(found_versions) or None,
            warnings=warnings,
        )

    return _build_result(
        ok=True,
        severity="none",
        code="ok",
        message="",
        expected_version=expected_version,
        found_version=", ".join(found_versions) or None,
    )

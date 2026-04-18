from __future__ import annotations

import os
import sys
from pathlib import Path

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
    Normalize an application or bundle version to its base release version.

    Examples:
        1.2.3 -> 1.2.3
        1.2.3.dev4 -> 1.2.3
        1.2.3rc1 -> 1.2.3

    Args:
        version (Version): Parsed version.

    Returns:
        str: Base release version string.
    """
    return ".".join(str(part) for part in version.release)


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
) -> dict[str, str | bool | None]:
    """
    Build a standardized org bundle validation result.

    Args:
        ok (bool): True when startup may continue.
        severity (str): Result severity ("none", "warning", or "error").
        code (str): Machine-friendly result code.
        message (str): User-facing message.
        expected_version (str): Expected normalized bundle version.
        found_version (str | None): Found bundle version, if available.

    Returns:
        dict[str, str | bool | None]: Standardized validation result.
    """
    return {
        "ok": ok,
        "severity": severity,
        "code": code,
        "message": message,
        "found_version": found_version,
        "expected_version": expected_version,
    }


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

    release_help = (
        "Download + install the latest or matching asset bundle and restart "
        f"Mod Builder:\n{GITHUB_RELEASES_URL}"
    )

    dev_bypass_help = ""
    if not is_frozen():
        dev_bypass_help = (
            "\n\nFor local development only, you may bypass version checks by setting:\n"
            "   MODBUILDER_SKIP_BUNDLE_VERSION_CHECK=1\n"
            "or running with:\n"
            "   hatch run dev:modbuilder"
        )

    if not name_map_file.exists():
        return _build_result(
            ok=False,
            severity="error",
            code="missing_name_map",
            message=(
                "Missing required asset file.\n\n"
                f"Expected file:\n{name_map_file}\n\n"
                f"{release_help}"
            ),
            expected_version=expected_version,
        )

    if not org_dir.exists():
        return _build_result(
            ok=False,
            severity="error",
            code="missing_org_dir",
            message=(
                "Missing required asset folder.\n\n"
                f"Expected folder:\n{org_dir}\n\n"
                f"{release_help}"
            ),
            expected_version=expected_version,
        )

    if not any(org_dir.iterdir()):
        return _build_result(
            ok=False,
            severity="error",
            code="empty_org_dir",
            message=(
                "The org asset folder is empty.\n\n"
                f"Expected folder:\n{org_dir}\n\n"
                f"{release_help}"
            ),
            expected_version=expected_version,
        )

    if should_skip_bundle_version_check():
        return _build_result(
            ok=True,
            severity="none",
            code="ok_version_check_skipped",
            message="",
            expected_version=expected_version,
        )

    if not version_file.exists():
        return _build_result(
            ok=True,
            severity="warning",
            code="missing_version_file",
            message=(
                "The org asset bundle version file is missing.\n\n"
                f"Expected file:\n{version_file}\n\n"
                f"Expected version: {expected_version}\n\n"
                f"{release_help}"
                f"{dev_bypass_help}"
            ),
            expected_version=expected_version,
        )

    raw_version = read_org_bundle_version()
    if raw_version is None:
        return _build_result(
            ok=True,
            severity="warning",
            code="empty_version_file",
            message=(
                "The org asset bundle version file is empty.\n\n"
                f"Expected file:\n{version_file}\n\n"
                f"Expected version: {expected_version}\n\n"
                f"{release_help}"
                f"{dev_bypass_help}"
            ),
            expected_version=expected_version,
        )

    try:
        bundle_version = Version(raw_version)
    except InvalidVersion:
        return _build_result(
            ok=True,
            severity="warning",
            code="invalid_version_file",
            message=(
                "The org asset bundle version file is invalid.\n\n"
                f"Found: {raw_version}\n"
                f"Expected version: {expected_version}\n\n"
                f"{release_help}"
                f"{dev_bypass_help}"
            ),
            expected_version=expected_version,
            found_version=raw_version,
        )

    actual_version = normalize_bundle_version(bundle_version)
    if actual_version != expected_version:
        return _build_result(
            ok=True,
            severity="warning",
            code="version_mismatch",
            message=(
                "The org asset bundle may be outdated.\n\n"
                f"Found bundle version: {raw_version}\n"
                f"Expected version: {expected_version}\n\n"
                f"{release_help}"
                f"{dev_bypass_help}"
            ),
            expected_version=expected_version,
            found_version=raw_version,
        )

    return _build_result(
        ok=True,
        severity="none",
        code="ok",
        message="",
        expected_version=expected_version,
        found_version=raw_version,
    )
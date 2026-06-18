"""
The modbuilder_X.X.X.7z archive and executable are versioned as major.minor.patch (2.7.1)
The modbuilder/org asset bundle and name_map.yaml are versioned as major.minor (2.7)
A new asset bundle is only required when the major or minor version changes due to game updates or large changes to Mod Builder.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.version import Version


def get_asset_version(version: str) -> str:
    """
    Return the asset compatibility version from a pyproject version string.

    Asset bundles are compatible across patch releases, so only the major and minor version are written.

    Examples:
        2.7.0 -> 2.7
        2.7.1 -> 2.7
        2.7.1.dev4 -> 2.7

    Args:
        version (str): Version string from pyproject.toml.

    Returns:
        str: Major/minor asset compatibility version.
    """
    parsed = Version(version)
    major, minor = parsed.release[:2]
    return f"{major}.{minor}"


def write_org_bundle_version(repo_root: Path, version: str) -> None:
    """
    Write the org asset bundle version file.

    Args:
        repo_root (Path): Path to the project root.
        version (str): Asset bundle compatibility version.
    """
    org_dir = repo_root / "modbuilder" / "org"
    if not org_dir.exists():
        raise FileNotFoundError(f"Missing org directory: {org_dir}")

    org_version_file = org_dir / "version.txt"
    org_version_file.write_text(f"{version}\n", encoding="utf-8")
    print(f"Wrote org bundle version {version} to {org_version_file}")


def update_name_map_version(repo_root: Path, version: str) -> None:
    """
    Update the version field in name_map.yaml.

    The existing version line is replaced in-place to preserve comments, formatting, and key ordering.

    Args:
        repo_root (Path): Path to the project root.
        version (str): Asset bundle compatibility version.

    Raises:
        FileNotFoundError: If name_map.yaml does not exist.
        ValueError: If there is not exactly one version field in name_map.yaml.
    """
    name_map_file = repo_root / "modbuilder" / "name_map.yaml"
    if not name_map_file.exists():
        raise FileNotFoundError(f"Missing name_map.yaml file: {name_map_file}")

    contents = name_map_file.read_text(encoding="utf-8")

    updated_contents, replacements = re.subn(
        r"^version:\s*.*$",
        f"version: {version}",
        contents,
        flags=re.MULTILINE,
    )

    if replacements != 1:
        raise ValueError(
            f"Expected exactly one 'version:' field in {name_map_file}, "
            f"found {replacements}"
        )

    name_map_file.write_text(updated_contents, encoding="utf-8")
    print(f"Updated name_map.yaml version to {version}")


def main() -> None:
    """
    Generate asset bundle version metadata from pyproject.toml.
    """
    repo_root = Path(__file__).resolve().parent.parent
    pyproject_path = repo_root / "pyproject.toml"

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = get_asset_version(data["project"]["version"])

    write_org_bundle_version(repo_root, version)
    update_name_map_version(repo_root, version)


if __name__ == "__main__":
    main()
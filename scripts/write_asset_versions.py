from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.version import Version


def get_base_version(version: str) -> str:
    """
    Return the base release version from a pyproject version string.
    """
    parsed = Version(version)
    return ".".join(str(part) for part in parsed.release)


def write_org_bundle_version(repo_root: Path, version: str) -> None:
    """
    Write the org asset bundle version file.

    Args:
        repo_root (Path): Path to the project root
        version (str): Asset bundle version.
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
        repo_root (Path): Path to the project root
        version (str): Asset bundle version.

    Raises:
        ValueError: If no version field exists in name_map.yaml.
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
    version = get_base_version(data["project"]["version"])

    write_org_bundle_version(repo_root, version)
    update_name_map_version(repo_root, version)


if __name__ == "__main__":
    main()

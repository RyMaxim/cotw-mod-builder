from __future__ import annotations

from pathlib import Path
import tomllib

from packaging.version import Version


def main() -> None:
    """
    Write modbuilder/org/version.txt using the base release version from pyproject.toml.
    """
    repo_root = Path(__file__).resolve().parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    org_dir = repo_root / "modbuilder" / "org"
    version_file = org_dir / "version.txt"

    if not org_dir.exists():
        raise FileNotFoundError(f"Missing org directory: {org_dir}")

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = Version(data["project"]["version"])
    base_version = ".".join(str(part) for part in version.release)

    version_file.write_text(f"{base_version}\n", encoding="utf-8")
    print(f"Wrote org bundle version {base_version} to {version_file}")


if __name__ == "__main__":
    main()
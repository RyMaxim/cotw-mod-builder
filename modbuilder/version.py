from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.version import Version


def get_version() -> Version:
    """
    Return the application version.

    Frozen builds use the generated build metadata file.
    Source runs fall back to reading pyproject.toml directly.

    Returns:
        Version: Parsed application version.
    """
    try:
        from modbuilder._build_meta import __version__

        return Version(__version__)
    except Exception:
        pass

    repo_root = Path(__file__).resolve().parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.exists():
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return Version(data["project"]["version"])

    return Version("0.0.0.dev0")

def get_base_version() -> str:
    """
    Return the normalized release version without dev/local suffixes.

    Returns:
        str: Base release version string.
    """
    version = get_version()
    return ".".join(str(part) for part in version.release)
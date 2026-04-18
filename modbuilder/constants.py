from __future__ import annotations

import tomllib
from pathlib import Path

ORG_DIR_NAME = "org"
ORG_VERSION_FILENAME = "version.txt"
ORG_ARCHIVE_PREFIX = "modbuilder_org"


def _load_urls_from_pyproject() -> dict[str, str]:
    """
    Load project URLs from pyproject.toml.

    Returns:
        dict[str, str]: Project URL mapping, or empty dict if unavailable.
    """
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        return {}

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return data.get("project", {}).get("urls", {})


try:
    from modbuilder._build_meta import (
        __latest_api_url__,
        __nexusmods_releases_url__,
        __nexusmods_url__,
        __releases_url__,
        __repository_url__,
    )

    GITHUB_REPOSITORY_URL = __repository_url__
    GITHUB_RELEASES_URL = __releases_url__
    GITHUB_LATEST_API_URL = __latest_api_url__
    NEXUSMODS_URL = __nexusmods_url__
    NEXUSMODS_RELEASES_URL = __nexusmods_releases_url__

except Exception:
    _urls = _load_urls_from_pyproject()

    GITHUB_REPOSITORY_URL = _urls["Repository"]
    GITHUB_RELEASES_URL = _urls["Releases"]
    NEXUSMODS_URL = _urls["NexusMods"]
    NEXUSMODS_RELEASES_URL = _urls["NexusModsReleases"]
    GITHUB_LATEST_API_URL = GITHUB_REPOSITORY_URL.replace(
        "https://github.com/",
        "https://api.github.com/repos/",
    ).rstrip("/") + "/releases/latest"
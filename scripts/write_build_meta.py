from __future__ import annotations

from pathlib import Path
import tomllib


def main() -> None:
    """
    Generate modbuilder/_build_meta.py from pyproject.toml.
    """
    repo_root = Path(__file__).resolve().parent.parent
    pyproject_path = repo_root / "pyproject.toml"
    output_file = repo_root / "modbuilder" / "_build_meta.py"

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data["project"]
    urls = project.get("urls", {})

    repository_url = urls["Repository"]
    releases_url = urls["Releases"]
    nexusmods_url = urls["NexusMods"]
    nexusmods_releases_url = urls["NexusModsReleases"]

    latest_api_url = repository_url.replace(
        "https://github.com/",
        "https://api.github.com/repos/",
    ).rstrip("/") + "/releases/latest"

    output_file.write_text(
        "\n".join(
            [
                '"""Auto-generated from pyproject.toml. Do not edit manually."""',
                f'__version__ = "{project["version"]}"',
                f'__repository_url__ = "{repository_url}"',
                f'__releases_url__ = "{releases_url}"',
                f'__nexusmods_url__ = "{nexusmods_url}"',
                f'__nexusmods_releases_url__ = "{nexusmods_releases_url}"',
                f'__latest_api_url__ = "{latest_api_url}"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Wrote build metadata to {output_file}")


if __name__ == "__main__":
    main()
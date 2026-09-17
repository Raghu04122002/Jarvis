"""Project discovery — scans directories to detect local development projects.

Read-only: never modifies any files on disk.
"""

import configparser
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Maps config file name -> stack identifier
_STACK_MARKERS: dict[str, str] = {
    "package.json": "node",
    "pyproject.toml": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "mix.exs": "elixir",
    "composer.json": "php",
    "Package.swift": "swift",
}


@dataclass
class DiscoveredProject:
    """A project detected on disk via heuristics."""

    name: str
    local_path: str
    github_repo: str | None = None
    stack: list[str] = field(default_factory=list)


def _parse_github_repo(git_dir: Path) -> str | None:
    """Extract GitHub repo (owner/name) from .git/config."""
    config_path = git_dir / "config"
    if not config_path.is_file():
        return None
    try:
        parser = configparser.ConfigParser()
        parser.read(str(config_path))
        for section in parser.sections():
            if section.startswith('remote "'):
                url = parser.get(section, "url", fallback="")
                if "github.com" in url:
                    # Handle SSH: git@github.com:owner/repo.git
                    if url.startswith("git@github.com:"):
                        repo = url.removeprefix("git@github.com:").removesuffix(".git")
                        return repo
                    # Handle HTTPS: https://github.com/owner/repo.git
                    if "github.com/" in url:
                        parts = url.split("github.com/", 1)
                        if len(parts) == 2:
                            return parts[1].removesuffix(".git")
    except Exception:
        logger.debug("Failed to parse git config at %s", config_path)
    return None


def _detect_stack(project_dir: Path) -> list[str]:
    """Detect technology stack from config files present in the directory."""
    stack: list[str] = []
    for filename, tech in _STACK_MARKERS.items():
        if (project_dir / filename).exists():
            stack.append(tech)

    # Detect frameworks from package.json
    pkg_json = project_dir / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "react" in deps:
                stack.append("react")
            if "vue" in deps:
                stack.append("vue")
            if "next" in deps:
                stack.append("nextjs")
            if "typescript" in deps:
                stack.append("typescript")
        except Exception:
            logger.debug("Failed to parse package.json at %s", pkg_json)

    return sorted(set(stack))


def discover_projects(base_path: str | Path) -> list[DiscoveredProject]:
    """Scan immediate subdirectories of base_path for development projects.

    Only inspects one level deep. Directories must contain a .git folder
    or a recognized config file to be considered a project.
    """
    base = Path(base_path)
    if not base.is_dir():
        return []

    projects: list[DiscoveredProject] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue

        git_dir = child / ".git"
        stack = _detect_stack(child)

        # Must have .git or at least one recognized config file
        if not git_dir.is_dir() and not stack:
            continue

        github_repo = _parse_github_repo(git_dir) if git_dir.is_dir() else None

        projects.append(
            DiscoveredProject(
                name=child.name,
                local_path=str(child),
                github_repo=github_repo,
                stack=stack,
            )
        )

    return projects

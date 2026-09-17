"""Tests for the project discovery service."""

import json
from pathlib import Path

import pytest

from jarvis.services.discovery import discover_projects


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path


def _make_git_config(project_dir: Path, url: str) -> None:
    """Create a .git/config with a remote origin URL."""
    git_dir = project_dir / ".git"
    git_dir.mkdir(parents=True)
    config = git_dir / "config"
    fetch = "+refs/heads/*:refs/remotes/origin/*"
    config.write_text(f'[remote "origin"]\n\turl = {url}\n\tfetch = {fetch}\n')


class TestDiscoverProjects:
    def test_empty_directory(self, base_dir: Path) -> None:
        assert discover_projects(base_dir) == []

    def test_nonexistent_directory(self) -> None:
        assert discover_projects("/nonexistent/path") == []

    def test_discovers_git_project(self, base_dir: Path) -> None:
        project = base_dir / "my-app"
        project.mkdir()
        _make_git_config(project, "git@github.com:user/my-app.git")

        results = discover_projects(base_dir)
        assert len(results) == 1
        assert results[0].name == "my-app"
        assert results[0].github_repo == "user/my-app"

    def test_discovers_https_github_repo(self, base_dir: Path) -> None:
        project = base_dir / "webapp"
        project.mkdir()
        _make_git_config(project, "https://github.com/org/webapp.git")

        results = discover_projects(base_dir)
        assert len(results) == 1
        assert results[0].github_repo == "org/webapp"

    def test_skips_hidden_directories(self, base_dir: Path) -> None:
        hidden = base_dir / ".hidden"
        hidden.mkdir()
        (hidden / ".git").mkdir()
        assert discover_projects(base_dir) == []

    def test_skips_non_project_directories(self, base_dir: Path) -> None:
        """Directories without .git or config files are not projects."""
        (base_dir / "random-dir").mkdir()
        assert discover_projects(base_dir) == []


class TestStackDetection:
    def test_detects_python_from_pyproject(self, base_dir: Path) -> None:
        project = base_dir / "pyapp"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname = 'pyapp'\n")

        results = discover_projects(base_dir)
        assert len(results) == 1
        assert "python" in results[0].stack

    def test_detects_node_from_package_json(self, base_dir: Path) -> None:
        project = base_dir / "nodeapp"
        project.mkdir()
        pkg = {"name": "nodeapp", "dependencies": {"express": "^4.0.0"}}
        (project / "package.json").write_text(json.dumps(pkg))

        results = discover_projects(base_dir)
        assert len(results) == 1
        assert "node" in results[0].stack

    def test_detects_react_from_dependencies(self, base_dir: Path) -> None:
        project = base_dir / "reactapp"
        project.mkdir()
        pkg = {"name": "reactapp", "dependencies": {"react": "^18.0.0"}}
        (project / "package.json").write_text(json.dumps(pkg))

        results = discover_projects(base_dir)
        assert "react" in results[0].stack
        assert "node" in results[0].stack

    def test_detects_typescript(self, base_dir: Path) -> None:
        project = base_dir / "tsapp"
        project.mkdir()
        pkg = {"name": "tsapp", "devDependencies": {"typescript": "^5.0.0"}}
        (project / "package.json").write_text(json.dumps(pkg))

        results = discover_projects(base_dir)
        assert "typescript" in results[0].stack

    def test_detects_rust_from_cargo(self, base_dir: Path) -> None:
        project = base_dir / "rustapp"
        project.mkdir()
        (project / "Cargo.toml").write_text('[package]\nname = "rustapp"\n')

        results = discover_projects(base_dir)
        assert "rust" in results[0].stack

    def test_detects_go_from_go_mod(self, base_dir: Path) -> None:
        project = base_dir / "goapp"
        project.mkdir()
        (project / "go.mod").write_text("module example.com/goapp\n")

        results = discover_projects(base_dir)
        assert "go" in results[0].stack

    def test_detects_multiple_stacks(self, base_dir: Path) -> None:
        project = base_dir / "fullstack"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname = 'api'\n")
        pkg = {"name": "frontend", "dependencies": {"react": "^18.0.0"}}
        (project / "package.json").write_text(json.dumps(pkg))

        results = discover_projects(base_dir)
        assert "python" in results[0].stack
        assert "node" in results[0].stack
        assert "react" in results[0].stack

    def test_discovers_multiple_projects(self, base_dir: Path) -> None:
        p1 = base_dir / "alpha"
        p1.mkdir()
        (p1 / "pyproject.toml").write_text("")

        p2 = base_dir / "beta"
        p2.mkdir()
        _make_git_config(p2, "git@github.com:user/beta.git")

        results = discover_projects(base_dir)
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"alpha", "beta"}

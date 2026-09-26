import subprocess
from pathlib import Path

import pytest


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def temp_git_repo(tmp_path) -> Path:
    """A small, throwaway Git repository with three commits touching one file."""
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test User")

    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-q", "-m", "Initial commit")

    (repo / "app.py").write_text("print('v1')\n", encoding="utf-8")
    run_git(repo, "add", "app.py")
    run_git(repo, "commit", "-q", "-m", "Add app.py")

    (repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
    run_git(repo, "add", "app.py")
    run_git(repo, "commit", "-q", "-m", "Update app.py")

    return repo


@pytest.fixture()
def target_app_path() -> Path:
    """Path to the real target-app repository this hackathon project is built around."""
    return Path(__file__).resolve().parents[2] / "target-app"

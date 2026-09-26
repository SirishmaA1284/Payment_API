import subprocess
from pathlib import Path

import pytest

from backend.services.sandbox_manager import SandboxManager, SandboxNotFoundError


@pytest.fixture()
def sandbox_root(tmp_path) -> Path:
    root = tmp_path / "sandboxes"
    root.mkdir()
    return root


def test_create_sandbox_creates_isolated_worktree(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    info = manager.create_sandbox()

    sandbox_path = Path(info.path)
    assert sandbox_path.exists()
    assert (sandbox_path / "app.py").exists()
    assert sandbox_path != temp_git_repo
    assert sandbox_path.parent == sandbox_root
    assert info.branch.startswith("codebase-icu/sandbox-")
    assert len(info.source_commit) == 40


def test_sandbox_does_not_modify_main_repo(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    info = manager.create_sandbox()

    (Path(info.path) / "app.py").write_text("print('modified in sandbox')\n", encoding="utf-8")

    assert (temp_git_repo / "app.py").read_text(encoding="utf-8") == "print('v2')\n"

    status = subprocess.run(
        ["git", "-C", str(temp_git_repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout.strip() == ""

    branch = subprocess.run(
        ["git", "-C", str(temp_git_repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert branch.stdout.strip() == "main"


def test_get_sandbox_returns_status(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    created = manager.create_sandbox()

    fetched = manager.get_sandbox(created.sandbox_id)
    assert fetched.sandbox_id == created.sandbox_id
    assert fetched.status == "ready"


def test_get_unknown_sandbox_raises(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    with pytest.raises(SandboxNotFoundError):
        manager.get_sandbox("does-not-exist")


def test_cleanup_removes_sandbox(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    info = manager.create_sandbox()
    sandbox_path = Path(info.path)
    assert sandbox_path.exists()

    manager.cleanup_sandbox(info.sandbox_id)

    assert not sandbox_path.exists()
    with pytest.raises(SandboxNotFoundError):
        manager.get_sandbox(info.sandbox_id)


def test_cleanup_unknown_sandbox_raises(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    with pytest.raises(SandboxNotFoundError):
        manager.cleanup_sandbox("does-not-exist")


def test_refuses_to_delete_source_repo(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    with pytest.raises(Exception):
        manager._assert_safe_to_delete(temp_git_repo)


def test_create_sandbox_rejects_unknown_ref(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    with pytest.raises(Exception):
        manager.create_sandbox(source_ref="does-not-exist-branch")


def test_sandbox_manager_rejects_non_git_directory(tmp_path):
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    with pytest.raises(FileNotFoundError):
        SandboxManager(not_a_repo)


def test_multiple_sandboxes_get_unique_ids_and_paths(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    first = manager.create_sandbox()
    second = manager.create_sandbox()

    assert first.sandbox_id != second.sandbox_id
    assert first.path != second.path
    assert Path(first.path).exists()
    assert Path(second.path).exists()

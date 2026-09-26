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


def test_get_sandbox_discovers_externally_created_worktree(temp_git_repo, sandbox_root, tmp_path):
    """A worktree created directly with `git worktree` (not via create_sandbox,
    mirroring how IBM Bob's repair sandbox is set up outside this API) must
    still be discoverable and addressable by its directory name."""
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)

    external_path = tmp_path / "hand-made-worktree"
    subprocess.run(
        [
            "git", "-C", str(temp_git_repo), "worktree", "add",
            "-b", "hand-made-branch", str(external_path), "HEAD",
        ],
        check=True, capture_output=True, text=True,
    )
    try:
        info = manager.get_sandbox(external_path.name)
        assert info.path == str(external_path)
        assert info.branch == "hand-made-branch"
        assert info.status == "ready"
        assert info.created_at is None
    finally:
        subprocess.run(
            ["git", "-C", str(temp_git_repo), "worktree", "remove", "--force", str(external_path)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(temp_git_repo), "branch", "-D", "hand-made-branch"],
            check=True, capture_output=True, text=True,
        )


def test_cleanup_cannot_delete_discovered_worktree(temp_git_repo, sandbox_root, tmp_path):
    """Discovered (externally created) worktrees are read-only through this
    manager: only sandboxes created via create_sandbox() can be deleted."""
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)

    external_path = tmp_path / "hand-made-worktree-2"
    subprocess.run(
        [
            "git", "-C", str(temp_git_repo), "worktree", "add",
            "-b", "hand-made-branch-2", str(external_path), "HEAD",
        ],
        check=True, capture_output=True, text=True,
    )
    try:
        manager.get_sandbox(external_path.name)  # discover it
        with pytest.raises(SandboxNotFoundError):
            manager.cleanup_sandbox(external_path.name)
        assert external_path.exists()  # cleanup must not have touched it
    finally:
        subprocess.run(
            ["git", "-C", str(temp_git_repo), "worktree", "remove", "--force", str(external_path)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(temp_git_repo), "branch", "-D", "hand-made-branch-2"],
            check=True, capture_output=True, text=True,
        )


def test_multiple_sandboxes_get_unique_ids_and_paths(temp_git_repo, sandbox_root):
    manager = SandboxManager(temp_git_repo, sandbox_root=sandbox_root)
    first = manager.create_sandbox()
    second = manager.create_sandbox()

    assert first.sandbox_id != second.sandbox_id
    assert first.path != second.path
    assert Path(first.path).exists()
    assert Path(second.path).exists()

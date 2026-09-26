"""FastAPI-level tests for the sandbox test-execution endpoint.

These exercise the actual app (via TestClient) against a small, disposable
Git repository shaped like the real one - a repo root with an `app`
subdirectory containing a pytest suite - so they never touch target-app or
the real Payment API repository.
"""
import importlib
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def sample_project_repo(tmp_path) -> Path:
    repo = tmp_path / "sample-repo"
    app_dir = repo / "app"
    app_dir.mkdir(parents=True)

    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test User")

    (app_dir / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "Initial commit")
    return repo


@pytest.fixture()
def api_client(sample_project_repo, monkeypatch):
    """A TestClient for backend.main, reloaded so it picks up a target repo
    pointed at the disposable sample project rather than the real target-app.
    """
    monkeypatch.setenv("CODEBASE_ICU_TARGET_REPO", str(sample_project_repo / "app"))

    import backend.main as main_module

    importlib.reload(main_module)

    with TestClient(main_module.app) as client:
        yield client, sample_project_repo


def test_run_tests_endpoint_runs_main_checkout(api_client):
    client, _ = api_client
    response = client.post("/tests/run")
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] == 1
    assert body["failed"] == 0
    assert body["total"] == 1


def test_run_sandbox_tests_returns_live_results(api_client):
    client, _ = api_client

    created = client.post("/sandbox/create", json={"source_ref": "HEAD"})
    assert created.status_code == 200
    sandbox_id = created.json()["sandbox_id"]

    try:
        response = client.post(f"/sandbox/{sandbox_id}/tests")
        assert response.status_code == 200
        body = response.json()
        assert body["passed"] == 1
        assert body["failed"] == 0
        assert body["total"] == 1
        assert body["returncode"] == 0
        assert "pytest" in " ".join(body["command"])
    finally:
        client.delete(f"/sandbox/{sandbox_id}")


def test_run_sandbox_tests_unknown_sandbox_returns_404(api_client):
    client, _ = api_client
    response = client.post("/sandbox/does-not-exist/tests")
    assert response.status_code == 404


def test_run_sandbox_tests_never_modifies_main_or_sandbox(api_client):
    client, repo = api_client

    created = client.post("/sandbox/create", json={"source_ref": "HEAD"})
    sandbox_id = created.json()["sandbox_id"]
    sandbox_path = Path(created.json()["path"])

    try:
        client.post(f"/sandbox/{sandbox_id}/tests")

        main_status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        assert main_status.stdout.strip() == ""

        main_branch = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        assert main_branch.stdout.strip() == "main"

        sandbox_status = subprocess.run(
            ["git", "-C", str(sandbox_path), "status", "--porcelain",
             "--untracked-files=no"],
            capture_output=True, text=True, check=True,
        )
        assert sandbox_status.stdout.strip() == ""
    finally:
        client.delete(f"/sandbox/{sandbox_id}")


def test_run_sandbox_tests_works_for_externally_created_worktree(api_client, tmp_path):
    """Mirrors the real scenario: IBM Bob's repair sandbox is a worktree
    created directly with `git worktree`, not through POST /sandbox/create -
    the test endpoint must still be able to run tests inside it by name."""
    client, repo = api_client

    external_path = tmp_path / "external-repair"
    run_git(repo, "worktree", "add", "-b", "manual-repair-branch", str(external_path), "HEAD")

    try:
        response = client.post(f"/sandbox/{external_path.name}/tests")
        assert response.status_code == 200
        body = response.json()
        assert body["passed"] == 1
        assert body["failed"] == 0
    finally:
        run_git(repo, "worktree", "remove", "--force", str(external_path))
        run_git(repo, "branch", "-D", "manual-repair-branch")


def test_cannot_delete_externally_created_worktree_via_api(api_client, tmp_path):
    client, repo = api_client

    external_path = tmp_path / "external-repair-2"
    run_git(repo, "worktree", "add", "-b", "manual-repair-branch-2", str(external_path), "HEAD")

    try:
        response = client.delete(f"/sandbox/{external_path.name}")
        assert response.status_code == 404
        assert external_path.exists()
    finally:
        run_git(repo, "worktree", "remove", "--force", str(external_path))
        run_git(repo, "branch", "-D", "manual-repair-branch-2")

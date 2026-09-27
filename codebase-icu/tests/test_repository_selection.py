"""Tests for runtime repository selection (POST /repository/configure).

The app starts pointed at one disposable "default" repository (standing in
for the Payment API demo) and a second disposable repository is selected at
runtime, so every assertion can tell which of the two an endpoint actually
operated on. Neither repository is the real target-app.
"""
import importlib
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.services.repository_selection import (
    RepositoryConfigurationError,
    RepositorySelection,
    resolve_repository,
)


def run_git(repo_path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def make_repo(path: Path, branch: str, test_body: str, commit_message: str) -> Path:
    path.mkdir(parents=True)
    run_git(path, "init", "-q", "-b", branch)
    run_git(path, "config", "user.email", "test@example.com")
    run_git(path, "config", "user.name", "Test User")
    (path / "test_sample.py").write_text(test_body, encoding="utf-8")
    run_git(path, "add", "-A")
    run_git(path, "commit", "-q", "-m", commit_message)
    return path


@pytest.fixture()
def default_repo(tmp_path) -> Path:
    return make_repo(
        tmp_path / "default-repo",
        "main",
        "def test_default():\n    assert True\n",
        "Default repo commit",
    )


@pytest.fixture()
def selected_repo(tmp_path) -> Path:
    """Two passing tests, one failing, on branch 'trunk', with two commits."""
    repo = make_repo(
        tmp_path / "selected-repo",
        "trunk",
        "def test_a():\n    assert True\n\n"
        "def test_b():\n    assert True\n\n"
        "def test_c():\n    assert 1 == 2\n",
        "Add selected repo tests",
    )
    (repo / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    run_git(repo, "add", "module.py")
    run_git(repo, "commit", "-q", "-m", "Add module.py")
    return repo


@pytest.fixture()
def client(default_repo, monkeypatch):
    monkeypatch.setenv("CODEBASE_ICU_TARGET_REPO", str(default_repo))

    import backend.main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        yield test_client


@pytest.fixture()
def configured_client(client, selected_repo):
    response = client.post("/repository/configure", json={"path": str(selected_repo)})
    assert response.status_code == 200, response.text
    return client


# ---- validation -------------------------------------------------------------


def test_default_repository_is_selected_until_configured(client, default_repo):
    response = client.get("/repository")
    assert response.status_code == 200
    body = response.json()
    assert Path(body["path"]) == default_repo.resolve()
    assert body["is_default"] is True
    assert body["branch"] == "main"


def test_configure_valid_repository(client, selected_repo):
    response = client.post("/repository/configure", json={"path": str(selected_repo)})
    assert response.status_code == 200
    body = response.json()
    assert Path(body["path"]) == selected_repo.resolve()
    assert Path(body["repo_root"]) == selected_repo.resolve()
    assert body["branch"] == "trunk"
    assert body["is_default"] is False

    current = client.get("/repository").json()
    assert Path(current["path"]) == selected_repo.resolve()


def test_configure_accepts_quoted_path(client, selected_repo):
    response = client.post("/repository/configure", json={"path": f'  "{selected_repo}"  '})
    assert response.status_code == 200
    assert Path(response.json()["path"]) == selected_repo.resolve()


def test_configure_subdirectory_resolves_repository_root(client, tmp_path):
    """Like the demo's target-app: tests live in a subdirectory of the repo."""
    repo = tmp_path / "nested-repo"
    (repo / "app").mkdir(parents=True)
    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test User")
    (repo / "app" / "test_nested.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "Nested app")

    response = client.post("/repository/configure", json={"path": str(repo / "app")})
    assert response.status_code == 200
    assert Path(response.json()["path"]) == (repo / "app").resolve()
    assert Path(response.json()["repo_root"]) == repo.resolve()

    created = client.post("/sandbox/create", json={"source_ref": "HEAD"}).json()
    try:
        body = client.post(f"/sandbox/{created['sandbox_id']}/tests").json()
        assert (body["passed"], body["failed"]) == (1, 0)
    finally:
        client.delete(f"/sandbox/{created['sandbox_id']}")


def test_configure_nonexistent_path(client, tmp_path):
    response = client.post("/repository/configure", json={"path": str(tmp_path / "missing")})
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_configure_non_directory_path(client, tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a repo", encoding="utf-8")
    response = client.post("/repository/configure", json={"path": str(file_path)})
    assert response.status_code == 400
    assert "is not a directory" in response.json()["detail"]


def test_configure_non_git_directory(client, tmp_path, monkeypatch):
    # Stop Git's upward search above tmp_path (see test_git_analyzer.py).
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()
    response = client.post("/repository/configure", json={"path": str(plain_dir)})
    assert response.status_code == 400
    assert "is not a Git repository" in response.json()["detail"]


@pytest.mark.parametrize("bad_path", ["", "   ", "relative/path", "x\x00y"])
def test_configure_rejects_empty_relative_or_malformed_paths(client, bad_path):
    response = client.post("/repository/configure", json={"path": bad_path})
    assert response.status_code == 400


def test_configure_rejects_missing_path_field(client):
    assert client.post("/repository/configure", json={}).status_code == 422


def test_failed_configure_keeps_previous_selection(configured_client, selected_repo, tmp_path):
    response = configured_client.post(
        "/repository/configure", json={"path": str(tmp_path / "missing")}
    )
    assert response.status_code == 400
    assert Path(configured_client.get("/repository").json()["path"]) == selected_repo.resolve()


def test_configure_path_is_never_run_as_a_command(client, tmp_path):
    marker = tmp_path / "pwned"
    payload = f"{tmp_path} && echo x > {marker}"
    response = client.post("/repository/configure", json={"path": payload})
    assert response.status_code == 400
    assert not marker.exists()


def test_reconfiguring_default_path_marks_it_default(configured_client, default_repo):
    response = configured_client.post("/repository/configure", json={"path": str(default_repo)})
    assert response.status_code == 200
    assert response.json()["is_default"] is True


def test_resolve_repository_errors_are_configuration_errors(tmp_path):
    with pytest.raises(RepositoryConfigurationError):
        resolve_repository(tmp_path / "missing")


def test_selection_falls_back_to_default(default_repo):
    selection = RepositorySelection(default_repo)
    assert selection.current().path == default_repo.resolve()
    assert selection.current().is_default is True


# ---- repository-dependent operations follow the selection ------------------


def test_status_uses_selected_repository(configured_client):
    body = configured_client.get("/repository/status").json()
    assert body["branch"] == "trunk"
    assert body["is_clean"] is True


def test_commits_use_selected_repository(configured_client):
    messages = [c["message"] for c in configured_client.get("/repository/commits").json()]
    assert messages == ["Add module.py", "Add selected repo tests"]


def test_commit_detail_and_diff_use_selected_repository(configured_client, selected_repo):
    head = run_git(selected_repo, "rev-parse", "HEAD").strip()

    detail = configured_client.get(f"/repository/commits/{head}")
    assert detail.status_code == 200
    assert detail.json()["changed_files"] == ["module.py"]

    diff = configured_client.get(f"/repository/diff/{head}")
    assert diff.status_code == 200
    assert "+VALUE = 1" in diff.json()["diff"]


def test_commit_from_previous_repository_is_not_found(client, default_repo, selected_repo):
    default_head = run_git(default_repo, "rev-parse", "HEAD").strip()
    assert client.get(f"/repository/commits/{default_head}").status_code == 200

    client.post("/repository/configure", json={"path": str(selected_repo)})
    assert client.get(f"/repository/commits/{default_head}").status_code == 404


def test_file_history_uses_selected_repository(configured_client):
    response = configured_client.get("/repository/file-history", params={"path": "module.py"})
    assert response.status_code == 200
    assert [e["commit"]["message"] for e in response.json()] == ["Add module.py"]


def test_test_run_uses_selected_repository(configured_client):
    body = configured_client.post("/tests/run").json()
    assert (body["total"], body["passed"], body["failed"]) == (3, 2, 1)
    assert body["failing_tests"][0]["node_id"].endswith("test_c")
    assert body["error_code"] is None


def test_test_run_reports_structured_error_when_repository_has_no_tests(client, tmp_path):
    repo = tmp_path / "no-tests"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("no tests here\n", encoding="utf-8")

    assert client.post("/repository/configure", json={"path": str(repo)}).status_code == 200
    response = client.post("/tests/run")
    assert response.status_code == 200
    body = response.json()
    assert body["error_code"] == "no_tests"
    assert body["error"]
    assert body["total"] == 0


def test_sandbox_lifecycle_uses_selected_repository(configured_client, selected_repo):
    created = configured_client.post("/sandbox/create", json={"source_ref": "HEAD"})
    assert created.status_code == 200
    info = created.json()
    sandbox_path = Path(info["path"])

    try:
        # Outside the selected repository, on its own repair branch.
        assert selected_repo.resolve() not in sandbox_path.resolve().parents
        assert info["branch"].startswith("codebase-icu/sandbox-")
        assert info["source_commit"] == run_git(selected_repo, "rev-parse", "HEAD").strip()
        branches = run_git(selected_repo, "branch", "--list", info["branch"])
        assert info["branch"] in branches

        lookup = configured_client.get(f"/sandbox/{info['sandbox_id']}")
        assert lookup.status_code == 200
        assert Path(lookup.json()["path"]) == sandbox_path

        # Repair the failing test only inside the sandbox: sandbox tests must
        # see the repair, while the selected repository stays untouched.
        test_file = sandbox_path / "test_sample.py"
        test_file.write_text(
            test_file.read_text(encoding="utf-8").replace("assert 1 == 2", "assert 1 == 1"),
            encoding="utf-8",
        )
        sandbox_run = configured_client.post(f"/sandbox/{info['sandbox_id']}/tests").json()
        assert (sandbox_run["passed"], sandbox_run["failed"]) == (3, 0)

        main_run = configured_client.post("/tests/run").json()
        assert (main_run["passed"], main_run["failed"]) == (2, 1)
        assert run_git(selected_repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == "trunk"
        assert run_git(selected_repo, "status", "--porcelain", "--untracked-files=no").strip() == ""
    finally:
        configured_client.delete(f"/sandbox/{info['sandbox_id']}")

    assert not sandbox_path.exists()


def test_sandbox_created_in_previous_repository_is_not_visible(client, default_repo, selected_repo):
    created = client.post("/sandbox/create", json={"source_ref": "HEAD"}).json()
    try:
        client.post("/repository/configure", json={"path": str(selected_repo)})
        assert client.get(f"/sandbox/{created['sandbox_id']}").status_code == 404
    finally:
        # Switching back restores access to (and cleanup of) the first
        # repository's sandbox.
        client.post("/repository/configure", json={"path": str(default_repo)})
        assert client.delete(f"/sandbox/{created['sandbox_id']}").status_code == 200

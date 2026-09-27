"""Codebase ICU infrastructure API.

Exposes deterministic, non-AI capabilities around a target repository:
Git history/diff inspection, test execution, and isolated sandbox creation.

IBM Bob 2.0 is the AI reasoning component of Codebase ICU. This backend
performs no root-cause analysis, no repair generation, and no autonomous
reasoning - it only gives that (and future) components a safe, structured
way to inspect the repository, run its tests, and get an isolated worktree
to try a repair in.

Configuration
--------------
The repository this API inspects can be selected at runtime with
``POST /repository/configure`` (a local path to a Git repository, or a
directory inside one). Until a repository is selected, the default target is
used: the ``CODEBASE_ICU_TARGET_REPO`` environment variable if set, otherwise
the sibling ``target-app`` directory (``../../target-app`` relative to this
file), which is where the Payment API demo application lives.

Every repository-dependent endpoint reads the *current* selection per
request, so after a successful configure call, status/commits/diffs/file
history, test runs, and sandboxes all operate on the newly selected
repository.

Sandbox worktrees are created against the top-level Git repository that
contains the target path (discovered via ``git rev-parse --show-toplevel``),
since a worktree cannot be created from a subdirectory that has no ``.git``
of its own.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    CommitDetailResponse,
    CommitDiffResponse,
    CommitSummaryResponse,
    FailingTestResponse,
    FileHistoryEntryResponse,
    RepositoryConfigureRequest,
    RepositorySelectionResponse,
    RepositoryStatusResponse,
    SandboxCreateRequest,
    SandboxDeleteResponse,
    SandboxInfoResponse,
    TestRunRequest,
    TestRunResponse,
)
from .services.git_analyzer import GitAnalyzer, GitCommandError, InvalidReferenceError
from .services.repository_selection import (
    RepositoryConfigurationError,
    RepositorySelection,
    SelectedRepository,
)
from .services.sandbox_manager import SandboxError, SandboxManager, SandboxNotFoundError
from .services.test_runner import TestRunner

DEFAULT_TARGET_REPO = Path(__file__).resolve().parent.parent.parent / "target-app"
TARGET_REPO_PATH = Path(
    os.environ.get("CODEBASE_ICU_TARGET_REPO", str(DEFAULT_TARGET_REPO))
).resolve()

# The repository currently being analyzed; starts at TARGET_REPO_PATH.
_selection = RepositorySelection(TARGET_REPO_PATH)

app = FastAPI(
    title="Codebase ICU - Infrastructure API",
    description=(
        "Deterministic repository analysis, test execution, and sandbox "
        "management for the target application. IBM Bob 2.0 is the AI "
        "reasoning component of Codebase ICU; this API performs no "
        "root-cause analysis or automated repair."
    ),
    version="0.1.0",
)

# The dashboard (Vite dev server / static build) runs on a different origin
# than this API, so the browser needs an explicit CORS allow-list to let it
# call these endpoints. Configurable so a non-default frontend port/host
# still works without editing source.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_allowed_origins = [
    origin.strip()
    for origin in os.environ.get("CODEBASE_ICU_CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# One manager per repository root, so switching repositories and back keeps
# each repository's own sandbox bookkeeping (and the ability to clean up
# sandboxes created there).
_sandbox_managers: Dict[Path, SandboxManager] = {}
_sandbox_managers_lock = threading.Lock()


def _get_selected_repository() -> SelectedRepository:
    try:
        return _selection.current()
    except RepositoryConfigurationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _get_git_analyzer() -> GitAnalyzer:
    try:
        return GitAnalyzer(_get_selected_repository().path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _get_test_runner() -> TestRunner:
    try:
        return TestRunner(_get_selected_repository().path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _get_sandbox_manager(selected: Optional[SelectedRepository] = None) -> SandboxManager:
    repo_root = (selected or _get_selected_repository()).repo_root
    with _sandbox_managers_lock:
        manager = _sandbox_managers.get(repo_root)
        if manager is None:
            try:
                manager = SandboxManager(repo_root)
            except (FileNotFoundError, ValueError) as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            _sandbox_managers[repo_root] = manager
    return manager


def _to_selection_response(selected: SelectedRepository) -> RepositorySelectionResponse:
    try:
        branch = GitAnalyzer(selected.path).get_status().branch
    except (FileNotFoundError, GitCommandError):
        branch = "unknown"
    return RepositorySelectionResponse(
        path=str(selected.path),
        repo_root=str(selected.repo_root),
        branch=branch,
        is_default=selected.is_default,
    )


def _to_test_run_response(result) -> TestRunResponse:
    return TestRunResponse(
        command=result.command,
        returncode=result.returncode,
        passed=result.passed,
        failed=result.failed,
        skipped=result.skipped,
        errors=result.errors,
        total=result.total,
        failing_tests=[FailingTestResponse(node_id=f.node_id, reason=f.reason) for f in result.failing_tests],
        error_tests=[FailingTestResponse(node_id=f.node_id, reason=f.reason) for f in result.error_tests],
        duration_seconds=result.duration_seconds,
        parsed_successfully=result.parsed_successfully,
        stdout=result.stdout,
        stderr=result.stderr,
        error_code=result.error_code,
        error=result.error,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "codebase-icu-backend"}


@app.get("/repository", response_model=RepositorySelectionResponse)
def repository_current() -> RepositorySelectionResponse:
    """The repository currently being analyzed (the default until one is configured)."""
    return _to_selection_response(_get_selected_repository())


@app.post("/repository/configure", response_model=RepositorySelectionResponse)
def repository_configure(request: RepositoryConfigureRequest) -> RepositorySelectionResponse:
    """Select the local Git repository every other endpoint operates on.

    ``path`` is treated purely as a filesystem path: it must exist, be a
    directory, and be inside a Git work tree whose root Git can resolve. On
    failure the previously selected repository stays selected.
    """
    try:
        selected = _selection.configure(request.path)
    except RepositoryConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_selection_response(selected)


@app.get("/repository/status", response_model=RepositoryStatusResponse)
def repository_status() -> RepositoryStatusResponse:
    analyzer = _get_git_analyzer()
    try:
        status = analyzer.get_status()
    except GitCommandError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RepositoryStatusResponse(**status.__dict__)


@app.get("/repository/commits", response_model=List[CommitSummaryResponse])
def repository_commits(
    limit: int = Query(default=20, ge=1, le=200),
    branch: Optional[str] = Query(default=None),
) -> List[CommitSummaryResponse]:
    analyzer = _get_git_analyzer()
    try:
        commits = analyzer.get_commits(limit=limit, branch=branch)
    except InvalidReferenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitCommandError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [CommitSummaryResponse(**c.__dict__) for c in commits]


@app.get("/repository/commits/{commit_hash}", response_model=CommitDetailResponse)
def repository_commit_detail(commit_hash: str) -> CommitDetailResponse:
    analyzer = _get_git_analyzer()
    try:
        detail = analyzer.get_commit_detail(commit_hash)
    except InvalidReferenceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GitCommandError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return CommitDetailResponse(**detail.__dict__)


@app.get("/repository/diff/{commit_hash}", response_model=CommitDiffResponse)
def repository_diff(commit_hash: str) -> CommitDiffResponse:
    analyzer = _get_git_analyzer()
    try:
        diff = analyzer.get_commit_diff(commit_hash)
    except InvalidReferenceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GitCommandError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return CommitDiffResponse(commit=commit_hash, diff=diff)


@app.get("/repository/file-history", response_model=List[FileHistoryEntryResponse])
def repository_file_history(
    path: str = Query(..., description="File path relative to the repository root"),
    limit: int = Query(default=20, ge=1, le=200),
) -> List[FileHistoryEntryResponse]:
    analyzer = _get_git_analyzer()
    try:
        entries = analyzer.get_file_history(path, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitCommandError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [
        FileHistoryEntryResponse(
            commit=CommitSummaryResponse(**entry.commit.__dict__),
            file_path=entry.file_path,
        )
        for entry in entries
    ]


@app.post("/tests/run", response_model=TestRunResponse)
def run_tests(request: TestRunRequest = TestRunRequest()) -> TestRunResponse:
    runner = _get_test_runner()
    result = runner.run(extra_args=request.extra_args)
    return _to_test_run_response(result)


@app.post("/sandbox/create", response_model=SandboxInfoResponse)
def create_sandbox(request: SandboxCreateRequest = SandboxCreateRequest()) -> SandboxInfoResponse:
    manager = _get_sandbox_manager()
    try:
        info = manager.create_sandbox(source_ref=request.source_ref)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SandboxInfoResponse(**info.__dict__)


@app.get("/sandbox/{sandbox_id}", response_model=SandboxInfoResponse)
def get_sandbox(sandbox_id: str) -> SandboxInfoResponse:
    manager = _get_sandbox_manager()
    try:
        info = manager.get_sandbox(sandbox_id)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SandboxInfoResponse(**info.__dict__)


@app.delete("/sandbox/{sandbox_id}", response_model=SandboxDeleteResponse)
def delete_sandbox(sandbox_id: str) -> SandboxDeleteResponse:
    manager = _get_sandbox_manager()
    try:
        manager.cleanup_sandbox(sandbox_id)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SandboxDeleteResponse(sandbox_id=sandbox_id, status="deleted")


@app.post("/sandbox/{sandbox_id}/tests", response_model=TestRunResponse)
def run_sandbox_tests(
    sandbox_id: str, request: TestRunRequest = TestRunRequest()
) -> TestRunResponse:
    """Run the target application's test suite inside an existing sandbox.

    This only ever reads the sandbox's checked-out files and runs `pytest`
    there (cwd=sandbox path); it never runs a Git command against the
    sandbox and never touches the main checkout, so both remain exactly as
    they were before the call.
    """
    selected = _get_selected_repository()
    manager = _get_sandbox_manager(selected)
    try:
        info = manager.get_sandbox(sandbox_id)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    sandbox_path = Path(info.path)
    if info.status != "ready" or not sandbox_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"sandbox '{sandbox_id}' has no working directory on disk",
        )

    # A sandbox mirrors the whole repository, so the selected project lives
    # at the same relative path inside it as inside the main checkout.
    try:
        runner = TestRunner((sandbox_path / selected.subpath).resolve())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = runner.run(extra_args=request.extra_args)
    return _to_test_run_response(result)

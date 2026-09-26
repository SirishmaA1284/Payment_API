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
The target repository/application this API inspects is configured via the
``CODEBASE_ICU_TARGET_REPO`` environment variable. If unset, it defaults to
the sibling ``target-app`` directory (``../../target-app`` relative to this
file), which is where the Payment API demo application lives.

Sandbox worktrees are created against the top-level Git repository that
contains the target path (discovered via ``git rev-parse --show-toplevel``),
since a worktree cannot be created from a subdirectory that has no ``.git``
of its own.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query

from .models import (
    CommitDetailResponse,
    CommitDiffResponse,
    CommitSummaryResponse,
    FailingTestResponse,
    FileHistoryEntryResponse,
    RepositoryStatusResponse,
    SandboxCreateRequest,
    SandboxDeleteResponse,
    SandboxInfoResponse,
    TestRunRequest,
    TestRunResponse,
)
from .services.git_analyzer import GitAnalyzer, GitCommandError, InvalidReferenceError
from .services.sandbox_manager import SandboxError, SandboxManager, SandboxNotFoundError
from .services.test_runner import TestRunner

DEFAULT_TARGET_REPO = Path(__file__).resolve().parent.parent.parent / "target-app"
TARGET_REPO_PATH = Path(
    os.environ.get("CODEBASE_ICU_TARGET_REPO", str(DEFAULT_TARGET_REPO))
).resolve()

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

_sandbox_manager: Optional[SandboxManager] = None


def _get_git_analyzer() -> GitAnalyzer:
    try:
        return GitAnalyzer(TARGET_REPO_PATH)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _get_test_runner() -> TestRunner:
    try:
        return TestRunner(TARGET_REPO_PATH)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _get_sandbox_manager() -> SandboxManager:
    global _sandbox_manager
    if _sandbox_manager is not None:
        return _sandbox_manager
    try:
        repo_root = GitAnalyzer(TARGET_REPO_PATH).get_repo_root()
        _sandbox_manager = SandboxManager(repo_root)
    except (FileNotFoundError, GitCommandError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _sandbox_manager


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "codebase-icu-backend"}


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
    )


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

"""Pydantic request/response schemas for the Codebase ICU infrastructure API."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RepositoryStatusResponse(BaseModel):
    branch: str
    is_clean: bool
    changed_files: List[str]


class CommitSummaryResponse(BaseModel):
    hash: str
    short_hash: str
    author: str
    author_email: str
    timestamp: str
    message: str


class CommitDetailResponse(CommitSummaryResponse):
    parents: List[str]
    changed_files: List[str]
    stat: str


class CommitDiffResponse(BaseModel):
    commit: str
    diff: str


class FileHistoryEntryResponse(BaseModel):
    commit: CommitSummaryResponse
    file_path: str


class FailingTestResponse(BaseModel):
    node_id: str
    reason: Optional[str] = None


class TestRunRequest(BaseModel):
    extra_args: Optional[List[str]] = Field(
        default=None,
        description="Additional pytest CLI arguments, e.g. ['-k', 'expired']",
    )


class TestRunResponse(BaseModel):
    command: List[str]
    returncode: int
    passed: int
    failed: int
    skipped: int
    errors: int
    total: int
    failing_tests: List[FailingTestResponse]
    error_tests: List[FailingTestResponse]
    duration_seconds: Optional[float] = None
    parsed_successfully: bool
    stdout: str
    stderr: str


class SandboxCreateRequest(BaseModel):
    source_ref: str = Field(
        default="HEAD",
        description="Branch, tag, or commit hash the sandbox worktree should be based on",
    )


class SandboxInfoResponse(BaseModel):
    sandbox_id: str
    path: str
    branch: str
    source_commit: str
    status: str
    created_at: str


class SandboxDeleteResponse(BaseModel):
    sandbox_id: str
    status: str

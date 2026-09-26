"""Safe, read-only interface around the Git CLI.

This module never uses ``shell=True`` and never interpolates user-provided
values into a shell string - all Git invocations are plain argv lists passed
to ``subprocess.run``. References (branches/tags/commit hashes) and file
paths are validated before use so that a caller cannot smuggle extra Git
flags (e.g. a ref beginning with ``-``) or escape the repository root via
path traversal.

Nothing in this module mutates repository state - it only reads history,
status, and diffs.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# A conservative allow-list for Git "revisions" (branches, tags, hashes, and
# simple relative forms like HEAD~1 or HEAD^). Deliberately excludes shell
# metacharacters, whitespace, and anything that could be mistaken for a CLI
# flag when a ref happens to start with "-".
_REF_RE = re.compile(r"^[A-Za-z0-9._/\-~^:]+$")


class GitCommandError(RuntimeError):
    """Raised when a Git subprocess exits with a non-zero status."""

    def __init__(self, command: List[str], returncode: int, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr.strip()
        super().__init__(
            f"git command failed ({returncode}): {' '.join(command)}\n{self.stderr}"
        )


class InvalidReferenceError(ValueError):
    """Raised when a commit hash, branch, or tag reference is invalid or unknown."""


@dataclass
class RepositoryStatus:
    branch: str
    is_clean: bool
    changed_files: List[str]


@dataclass
class CommitSummary:
    hash: str
    short_hash: str
    author: str
    author_email: str
    timestamp: str
    message: str


@dataclass
class CommitDetail:
    hash: str
    short_hash: str
    author: str
    author_email: str
    timestamp: str
    message: str
    parents: List[str]
    changed_files: List[str]
    stat: str


@dataclass
class FileHistoryEntry:
    commit: CommitSummary
    file_path: str


def _validate_ref(value: str) -> str:
    """Reject refs that are empty, look like CLI flags, or contain shell-unsafe characters."""
    candidate = value.strip()
    if not candidate or candidate.startswith("-") or not _REF_RE.match(candidate):
        raise InvalidReferenceError(f"'{value}' is not a valid git reference")
    return candidate


class GitAnalyzer:
    """Read-only interface around a local Git repository (or a subdirectory of one)."""

    # Fields separated by 0x1f (unit separator) and records by 0x1e (record
    # separator) so that commit messages containing normal punctuation never
    # corrupt the parse.
    _LOG_FORMAT = "%H%x1f%h%x1f%an%x1f%ae%x1f%aI%x1f%s%x1e"

    def __init__(self, repo_path: Path | str):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.is_dir():
            raise FileNotFoundError(f"'{self.repo_path}' does not exist")
        if not (self.repo_path / ".git").exists() and not self._is_inside_work_tree():
            raise FileNotFoundError(f"'{self.repo_path}' is not inside a Git repository")

    # ---- low-level plumbing -------------------------------------------------

    def _run(self, args: List[str]) -> str:
        command = ["git", "-C", str(self.repo_path), *args]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        if result.returncode != 0:
            raise GitCommandError(command, result.returncode, result.stderr)
        return result.stdout

    def _is_inside_work_tree(self) -> bool:
        try:
            self._run(["rev-parse", "--is-inside-work-tree"])
            return True
        except GitCommandError:
            return False

    def _validate_relative_path(self, file_path: str) -> str:
        candidate = (self.repo_path / file_path).resolve()
        try:
            candidate.relative_to(self.repo_path)
        except ValueError as exc:
            raise ValueError(f"'{file_path}' escapes the repository root") from exc
        return Path(file_path).as_posix()

    def _parse_log(self, raw: str) -> List[CommitSummary]:
        commits: List[CommitSummary] = []
        for entry in raw.split("\x1e"):
            entry = entry.strip("\n")
            if not entry:
                continue
            parts = entry.split("\x1f")
            if len(parts) != 6:
                continue
            full_hash, short_hash, author, email, timestamp, message = parts
            commits.append(
                CommitSummary(
                    hash=full_hash,
                    short_hash=short_hash,
                    author=author,
                    author_email=email,
                    timestamp=timestamp,
                    message=message,
                )
            )
        return commits

    # ---- public API -----------------------------------------------------

    def get_repo_root(self) -> Path:
        """Return the top-level directory of the repository (may differ from repo_path
        when repo_path points at a subdirectory, e.g. target-app inside a larger repo)."""
        return Path(self._run(["rev-parse", "--show-toplevel"]).strip())

    def get_status(self) -> RepositoryStatus:
        """Return current branch, clean/dirty state, and changed file paths."""
        try:
            branch = self._run(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        except GitCommandError:
            branch = "HEAD"  # detached HEAD or repository with no commits yet
        porcelain = self._run(["status", "--porcelain"])
        changed_files = [line[3:].strip() for line in porcelain.splitlines() if line.strip()]
        return RepositoryStatus(
            branch=branch,
            is_clean=len(changed_files) == 0,
            changed_files=changed_files,
        )

    def get_commits(self, limit: int = 20, branch: Optional[str] = None) -> List[CommitSummary]:
        """Return the most recent commits, newest first."""
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        args = ["log", f"-n{limit}", f"--format={self._LOG_FORMAT}"]
        if branch:
            args.append(_validate_ref(branch))
        try:
            raw = self._run(args)
        except GitCommandError as exc:
            if branch:
                raise InvalidReferenceError(f"unknown branch or ref '{branch}'") from exc
            raise
        return self._parse_log(raw)

    def get_commit_detail(self, commit_hash: str) -> CommitDetail:
        """Return metadata, parent hash(es), changed files, and a stat summary for one commit."""
        ref = _validate_ref(commit_hash)
        try:
            raw = self._run(["show", "-s", f"--format={self._LOG_FORMAT}", ref])
        except GitCommandError as exc:
            raise InvalidReferenceError(f"unknown commit '{commit_hash}'") from exc

        commits = self._parse_log(raw)
        if not commits:
            raise InvalidReferenceError(f"unknown commit '{commit_hash}'")
        summary = commits[0]

        parents_raw = self._run(["rev-list", "--parents", "-n", "1", summary.hash]).strip()
        parent_hashes = parents_raw.split()[1:]  # first token is the commit itself

        name_status = self._run(["show", "--name-status", "--format=", summary.hash])
        changed_files = [
            line.split("\t")[-1] for line in name_status.splitlines() if line.strip()
        ]

        stat = self._run(["show", "--stat", "--format=", summary.hash]).strip()

        return CommitDetail(
            hash=summary.hash,
            short_hash=summary.short_hash,
            author=summary.author,
            author_email=summary.author_email,
            timestamp=summary.timestamp,
            message=summary.message,
            parents=parent_hashes,
            changed_files=changed_files,
            stat=stat,
        )

    def get_commit_diff(self, commit_hash: str, context_lines: int = 3) -> str:
        """Return the unified diff introduced by a single commit."""
        ref = _validate_ref(commit_hash)
        if context_lines < 0:
            raise ValueError("context_lines must be >= 0")
        try:
            return self._run(["show", f"-U{context_lines}", "--format=", ref])
        except GitCommandError as exc:
            raise InvalidReferenceError(f"unknown commit '{commit_hash}'") from exc

    def get_file_history(self, file_path: str, limit: int = 20) -> List[FileHistoryEntry]:
        """Return commits (newest first) that modified the given file."""
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        relative_path = self._validate_relative_path(file_path)
        args = ["log", f"-n{limit}", f"--format={self._LOG_FORMAT}", "--follow", "--", relative_path]
        raw = self._run(args)
        commits = self._parse_log(raw)
        return [FileHistoryEntry(commit=commit, file_path=relative_path) for commit in commits]

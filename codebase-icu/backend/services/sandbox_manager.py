"""Isolated Git worktrees for future AI-proposed repairs.

Each sandbox is a plain ``git worktree`` checked out onto its own throwaway
branch, rooted under a dedicated ``sandbox_root`` directory that lives
*outside* the source repository's working tree. Creating or deleting a
sandbox never touches the source repository's checked-out branch, staged
changes, or HEAD - it only adds/removes worktree metadata and throwaway
branches.

This module implements infrastructure only: it does not generate, apply, or
merge any repair. That is out of scope for this block.
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class SandboxError(RuntimeError):
    """Raised when a sandbox operation fails."""


class SandboxNotFoundError(SandboxError):
    """Raised when a sandbox id is not known to this manager."""


@dataclass
class SandboxInfo:
    sandbox_id: str
    path: str
    branch: str
    source_commit: str
    status: str
    # None for a sandbox this manager discovered rather than created itself
    # (see _find_worktree_by_sandbox_id) - its actual creation time isn't
    # known to this process.
    created_at: Optional[str] = None


class SandboxManager:
    """Creates and tears down isolated Git worktrees for one source repository."""

    BRANCH_PREFIX = "codebase-icu/sandbox-"

    def __init__(self, repo_path: Path | str, sandbox_root: Optional[Path | str] = None):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            # A worktree must be created from the top-level repository, not a
            # subdirectory of one (target-app has no .git of its own).
            raise FileNotFoundError(
                f"'{self.repo_path}' is not a Git repository root (no .git directory)"
            )

        self.sandbox_root = (
            Path(sandbox_root).resolve()
            if sandbox_root is not None
            else self.repo_path.parent / ".codebase-icu-sandboxes"
        )
        self.sandbox_root.mkdir(parents=True, exist_ok=True)

        self._sandboxes: Dict[str, SandboxInfo] = {}

    # ---- low-level plumbing -------------------------------------------------

    def _run_git(self, args: List[str]) -> str:
        command = ["git", "-C", str(self.repo_path), *args]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        if result.returncode != 0:
            raise SandboxError(f"git command failed: {' '.join(command)}\n{result.stderr.strip()}")
        return result.stdout

    def _list_git_worktrees(self) -> List[Dict[str, str]]:
        """Parse `git worktree list --porcelain` into per-worktree dicts.

        This surfaces every worktree Git knows about for the repository -
        including ones created directly with `git worktree` outside this
        manager (e.g. a repair sandbox IBM Bob set up by hand) - not just
        ones this manager's own bookkeeping created.
        """
        raw = self._run_git(["worktree", "list", "--porcelain"])
        worktrees: List[Dict[str, str]] = []
        current: Dict[str, str] = {}
        for line in raw.splitlines():
            if not line.strip():
                if current:
                    worktrees.append(current)
                    current = {}
                continue
            if line.startswith("worktree "):
                current["path"] = line[len("worktree "):].strip()
            elif line.startswith("HEAD "):
                current["head"] = line[len("HEAD "):].strip()
            elif line.startswith("branch "):
                current["branch"] = line[len("branch "):].strip()
        if current:
            worktrees.append(current)
        return worktrees

    def _find_worktree_by_sandbox_id(self, sandbox_id: str) -> Optional[Dict[str, str]]:
        for worktree in self._list_git_worktrees():
            path = worktree.get("path", "")
            if path and Path(path).name == sandbox_id:
                return worktree
        return None

    def _assert_safe_to_delete(self, path: Path) -> None:
        """Refuse to delete anything that is not a path this manager created."""
        resolved = path.resolve()
        if resolved == self.repo_path or self.repo_path in resolved.parents:
            raise SandboxError("refusing to delete the source repository")
        try:
            resolved.relative_to(self.sandbox_root)
        except ValueError as exc:
            raise SandboxError(f"refusing to delete path outside sandbox root: {resolved}") from exc

    # ---- public API -----------------------------------------------------

    def create_sandbox(self, source_ref: str = "HEAD") -> SandboxInfo:
        """Create a new isolated worktree checked out from ``source_ref``."""
        ref = source_ref.strip()
        if not ref or ref.startswith("-"):
            raise ValueError(f"invalid source reference: {source_ref!r}")

        try:
            resolved_commit = self._run_git(["rev-parse", ref]).strip()
        except SandboxError as exc:
            raise SandboxError(f"unknown reference '{source_ref}'") from exc

        sandbox_id = uuid.uuid4().hex[:12]
        branch_name = f"{self.BRANCH_PREFIX}{sandbox_id}"
        sandbox_path = self.sandbox_root / sandbox_id
        if sandbox_path.exists():
            raise SandboxError(f"sandbox path already exists: {sandbox_path}")

        self._run_git(["worktree", "add", "-b", branch_name, str(sandbox_path), resolved_commit])

        info = SandboxInfo(
            sandbox_id=sandbox_id,
            path=str(sandbox_path),
            branch=branch_name,
            source_commit=resolved_commit,
            status="ready",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._sandboxes[sandbox_id] = info
        return info

    def get_sandbox(self, sandbox_id: str) -> SandboxInfo:
        """Return current info for a sandbox, refreshing its status from disk.

        Looks up sandboxes this manager created itself first (bookkeeping in
        `_sandboxes`); if not found there, falls back to discovering any
        Git worktree - created by this manager or not - whose directory name
        matches `sandbox_id`. Discovered sandboxes are returned read-only:
        they are never added to `_sandboxes`, so `cleanup_sandbox` (which
        only ever looks there) can never delete a worktree this manager
        didn't create.
        """
        info = self._sandboxes.get(sandbox_id)
        if info is not None:
            status = "ready" if Path(info.path).exists() else "missing"
            if status != info.status:
                info = replace(info, status=status)
                self._sandboxes[sandbox_id] = info
            return info

        worktree = self._find_worktree_by_sandbox_id(sandbox_id)
        if worktree is None:
            raise SandboxNotFoundError(f"unknown sandbox '{sandbox_id}'")

        path = Path(worktree.get("path", ""))
        branch = worktree.get("branch", "")
        if branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/"):]

        return SandboxInfo(
            sandbox_id=sandbox_id,
            path=str(path),
            branch=branch or "(detached)",
            source_commit=worktree.get("head", ""),
            status="ready" if path.exists() else "missing",
            created_at=None,
        )

    def list_sandboxes(self) -> List[SandboxInfo]:
        return [self.get_sandbox(sandbox_id) for sandbox_id in list(self._sandboxes)]

    def cleanup_sandbox(self, sandbox_id: str) -> None:
        """Remove a sandbox's worktree, branch, and bookkeeping entry."""
        info = self._sandboxes.get(sandbox_id)
        if info is None:
            raise SandboxNotFoundError(f"unknown sandbox '{sandbox_id}'")

        sandbox_path = Path(info.path)
        self._assert_safe_to_delete(sandbox_path)

        try:
            self._run_git(["worktree", "remove", "--force", str(sandbox_path)])
        except SandboxError:
            # Worktree metadata may already be gone or corrupted; fall back to
            # a direct filesystem removal (still guarded by the safety check
            # above) followed by pruning stale worktree records.
            if sandbox_path.exists():
                shutil.rmtree(sandbox_path, ignore_errors=True)
            try:
                self._run_git(["worktree", "prune"])
            except SandboxError:
                pass

        try:
            self._run_git(["branch", "-D", info.branch])
        except SandboxError:
            pass  # branch may already be gone; cleanup should not fail on this

        self._sandboxes.pop(sandbox_id, None)

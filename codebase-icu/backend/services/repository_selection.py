"""Runtime selection of the repository Codebase ICU analyzes.

The backend starts out pointed at a default target (the Payment API demo, or
whatever ``CODEBASE_ICU_TARGET_REPO`` names). A client can then select a
different local Git repository at runtime; every repository-dependent
operation (Git analysis, test execution, sandboxes) reads the current
selection from here instead of a fixed path.

A submitted value is only ever treated as a filesystem path. It is validated
(exists, is a directory, is inside a Git work tree whose root Git can
resolve) through ``GitAnalyzer``, which runs Git with argv lists and no
shell - the value is never interpolated into a command string.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .git_analyzer import GitAnalyzer, GitCommandError

# Generous upper bound; real paths are far shorter. Rejects absurd payloads
# before they ever reach the filesystem or Git.
_MAX_PATH_LENGTH = 4096


class RepositoryConfigurationError(ValueError):
    """Raised when a path cannot be used as the analyzed repository."""


@dataclass(frozen=True)
class SelectedRepository:
    # Directory tests run in. May be a subdirectory of repo_root (e.g. the
    # demo's target-app, which lives inside a larger repository).
    path: Path
    # Top-level directory of the Git repository containing ``path``;
    # sandbox worktrees are created from here.
    repo_root: Path
    is_default: bool

    @property
    def subpath(self) -> str:
        """``path`` relative to ``repo_root`` ("." when they are the same)."""
        return os.path.relpath(self.path, self.repo_root)


def _normalize(raw_path: str | Path) -> Path:
    text = str(raw_path).strip()
    # Windows Explorer's "Copy as path" wraps the path in double quotes.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    if not text:
        raise RepositoryConfigurationError("a repository path is required")
    if len(text) > _MAX_PATH_LENGTH or "\x00" in text:
        raise RepositoryConfigurationError("the repository path is not a valid filesystem path")

    path = Path(text)
    if not path.is_absolute():
        raise RepositoryConfigurationError(
            f"'{text}' is not an absolute path; enter the full path to a local Git repository"
        )
    return path


def resolve_repository(raw_path: str | Path, default_path: Optional[Path] = None) -> SelectedRepository:
    """Validate ``raw_path`` and return it as a selectable repository."""
    path = _normalize(raw_path)
    if not path.exists():
        raise RepositoryConfigurationError(f"'{path}' does not exist")
    if not path.is_dir():
        raise RepositoryConfigurationError(f"'{path}' is not a directory")

    path = path.resolve()
    try:
        repo_root = GitAnalyzer(path).get_repo_root().resolve()
    except FileNotFoundError as exc:
        raise RepositoryConfigurationError(f"'{path}' is not a Git repository") from exc
    except GitCommandError as exc:
        # e.g. a bare repository (no work tree to test), or Git refusing a
        # repository owned by another user ("dubious ownership").
        raise RepositoryConfigurationError(
            f"Git could not resolve a repository root for '{path}': {exc.stderr or 'unknown error'}"
        ) from exc

    is_default = default_path is not None and path == Path(default_path).resolve()
    return SelectedRepository(path=path, repo_root=repo_root, is_default=is_default)


class RepositorySelection:
    """Thread-safe holder for the currently selected repository."""

    def __init__(self, default_path: Path | str):
        self.default_path = Path(default_path).resolve()
        self._selected: Optional[SelectedRepository] = None
        self._lock = threading.Lock()

    def current(self) -> SelectedRepository:
        """The selected repository, falling back to (and validating) the default."""
        with self._lock:
            if self._selected is not None:
                return self._selected
        # Resolved on demand rather than at startup, so a misconfigured
        # default only fails the requests that need it instead of the app.
        return resolve_repository(self.default_path, default_path=self.default_path)

    def configure(self, raw_path: str | Path) -> SelectedRepository:
        """Validate and select a new repository; the previous one stays selected on failure."""
        selected = resolve_repository(raw_path, default_path=self.default_path)
        with self._lock:
            self._selected = selected
        return selected

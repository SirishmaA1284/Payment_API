"""Runs a target project's pytest suite and parses the result into structured data.

The parser is intentionally general: it looks for pytest's own summary
vocabulary ("N passed", "N failed", "N skipped", "N error(s)") and its
"FAILED <nodeid> - <reason>" / "ERROR <nodeid> - <reason>" lines, rather than
assuming any specific project's test names or counts. If parsing comes up
empty (unexpected pytest output format, a crash before pytest even starts,
etc.) the raw stdout/stderr is still returned so a caller can inspect it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_SUMMARY_COUNT_RE = re.compile(
    r"(?P<count>\d+)\s+(?P<label>passed|failed|skipped|deselected|xfailed|xpassed|error|errors)\b"
)
_FAILED_LINE_RE = re.compile(r"^FAILED (?P<nodeid>\S+?)(?: - (?P<reason>.*))?$", re.MULTILINE)
_ERROR_LINE_RE = re.compile(r"^ERROR (?P<nodeid>\S+?)(?: - (?P<reason>.*))?$", re.MULTILINE)
_DURATION_RE = re.compile(r"in\s+(?P<seconds>[\d.]+)\s*s\b")


@dataclass
class FailingTest:
    node_id: str
    reason: Optional[str] = None


@dataclass
class TestRunResult:
    __test__ = False  # not a pytest test class, despite the name

    command: List[str]
    returncode: int
    passed: int
    failed: int
    skipped: int
    errors: int
    total: int
    failing_tests: List[FailingTest]
    error_tests: List[FailingTest]
    duration_seconds: Optional[float]
    stdout: str
    stderr: str
    parsed_successfully: bool


class TestRunner:
    """Executes ``pytest -q`` (plus optional extra args) inside a target project directory."""

    __test__ = False  # not a pytest test class, despite the name

    def __init__(self, project_path: Path | str, timeout_seconds: int = 120):
        self.project_path = Path(project_path).resolve()
        if not self.project_path.is_dir():
            raise FileNotFoundError(f"'{self.project_path}' does not exist")
        self.timeout_seconds = timeout_seconds

    def run(self, extra_args: Optional[List[str]] = None) -> TestRunResult:
        args = ["-q"]
        if extra_args:
            args.extend(str(a) for a in extra_args)
        command = [sys.executable, "-m", "pytest", *args]

        try:
            result = subprocess.run(
                command,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                shell=False,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return TestRunResult(
                command=command,
                returncode=-1,
                passed=0,
                failed=0,
                skipped=0,
                errors=0,
                total=0,
                failing_tests=[],
                error_tests=[],
                duration_seconds=None,
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + f"\ntest run timed out after {self.timeout_seconds}s",
                parsed_successfully=False,
            )

        return self._parse(command, result.returncode, result.stdout, result.stderr)

    @staticmethod
    def _parse(command: List[str], returncode: int, stdout: str, stderr: str) -> TestRunResult:
        counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
        parsed_any = False
        for match in _SUMMARY_COUNT_RE.finditer(stdout):
            label = match.group("label")
            if label == "errors":
                label = "error"
            if label in counts:
                counts[label] = int(match.group("count"))
                parsed_any = True

        duration_match = _DURATION_RE.search(stdout)
        duration = float(duration_match.group("seconds")) if duration_match else None

        failing_tests = [
            FailingTest(node_id=m.group("nodeid"), reason=m.group("reason"))
            for m in _FAILED_LINE_RE.finditer(stdout)
        ]
        error_tests = [
            FailingTest(node_id=m.group("nodeid"), reason=m.group("reason"))
            for m in _ERROR_LINE_RE.finditer(stdout)
        ]

        total = counts["passed"] + counts["failed"] + counts["skipped"] + counts["error"]

        return TestRunResult(
            command=command,
            returncode=returncode,
            passed=counts["passed"],
            failed=counts["failed"],
            skipped=counts["skipped"],
            errors=counts["error"],
            total=total,
            failing_tests=failing_tests,
            error_tests=error_tests,
            duration_seconds=duration,
            stdout=stdout,
            stderr=stderr,
            parsed_successfully=parsed_any,
        )

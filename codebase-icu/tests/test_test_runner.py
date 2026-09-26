import textwrap
from pathlib import Path

import pytest

from backend.services.test_runner import TestRunner


@pytest.fixture()
def sample_test_project(tmp_path) -> Path:
    project = tmp_path / "sample-project"
    project.mkdir()
    (project / "test_sample.py").write_text(
        textwrap.dedent(
            """
            def test_pass_one():
                assert 1 == 1


            def test_pass_two():
                assert True


            def test_fail_one():
                assert 1 == 2, "expected mismatch"
            """
        ),
        encoding="utf-8",
    )
    return project


def test_run_executes_pytest_and_returns_counts(sample_test_project):
    runner = TestRunner(sample_test_project)
    result = runner.run()

    assert result.passed == 2
    assert result.failed == 1
    assert result.skipped == 0
    assert result.total == 3
    assert result.returncode == 1
    assert result.parsed_successfully is True


def test_run_detects_failing_test_names(sample_test_project):
    runner = TestRunner(sample_test_project)
    result = runner.run()

    node_ids = [f.node_id for f in result.failing_tests]
    assert any("test_fail_one" in node_id for node_id in node_ids)
    assert result.failing_tests[0].reason


def test_run_preserves_raw_output(sample_test_project):
    runner = TestRunner(sample_test_project)
    result = runner.run()

    assert "test_fail_one" in result.stdout
    assert isinstance(result.stderr, str)


def test_run_records_command_executed(sample_test_project):
    runner = TestRunner(sample_test_project)
    result = runner.run()

    assert "pytest" in " ".join(result.command)


def test_run_supports_extra_args(sample_test_project):
    runner = TestRunner(sample_test_project)
    result = runner.run(extra_args=["-k", "test_pass_one"])

    assert result.passed == 1
    assert result.failed == 0
    assert result.total == 1


def test_runner_rejects_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        TestRunner(tmp_path / "does-not-exist")


def test_run_on_project_with_no_failures(tmp_path):
    project = tmp_path / "clean-project"
    project.mkdir()
    (project / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    runner = TestRunner(project)
    result = runner.run()

    assert result.passed == 1
    assert result.failed == 0
    assert result.returncode == 0
    assert result.failing_tests == []


# ---- against the real target-app repository (validates the known,
# currently-intentional regression state without hard-coding it into the
# parser itself) --------------------------------------------------------


def test_run_against_real_target_app(target_app_path):
    runner = TestRunner(target_app_path)
    result = runner.run()

    assert result.parsed_successfully is True
    assert result.total == result.passed + result.failed + result.skipped + result.errors
    assert result.failed >= 1
    assert any("expired" in f.node_id.lower() for f in result.failing_tests)

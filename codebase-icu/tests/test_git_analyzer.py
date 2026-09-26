import pytest

from backend.services.git_analyzer import GitAnalyzer, InvalidReferenceError


# ---- against an isolated, throwaway repo (generic behavior) ----------------


def test_status_reports_clean_repo(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    status = analyzer.get_status()
    assert status.branch == "main"
    assert status.is_clean is True
    assert status.changed_files == []


def test_status_reports_dirty_repo(temp_git_repo):
    (temp_git_repo / "untracked.txt").write_text("x", encoding="utf-8")
    analyzer = GitAnalyzer(temp_git_repo)
    status = analyzer.get_status()
    assert status.is_clean is False
    assert any("untracked.txt" in f for f in status.changed_files)


def test_get_commits_returns_history_newest_first(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    commits = analyzer.get_commits(limit=10)
    assert [c.message for c in commits] == ["Update app.py", "Add app.py", "Initial commit"]
    assert all(len(c.hash) == 40 for c in commits)
    assert all(c.hash.startswith(c.short_hash) for c in commits)


def test_get_commits_respects_limit(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    commits = analyzer.get_commits(limit=1)
    assert len(commits) == 1
    assert commits[0].message == "Update app.py"


def test_get_commits_rejects_unknown_branch(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    with pytest.raises(InvalidReferenceError):
        analyzer.get_commits(branch="does-not-exist")


def test_get_commit_detail(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    latest = analyzer.get_commits(limit=1)[0]
    detail = analyzer.get_commit_detail(latest.hash)
    assert detail.hash == latest.hash
    assert detail.message == "Update app.py"
    assert "app.py" in detail.changed_files
    assert len(detail.parents) == 1
    assert "app.py" in detail.stat


def test_get_commit_detail_rejects_unknown_commit(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    with pytest.raises(InvalidReferenceError):
        analyzer.get_commit_detail("deadbeef")


def test_get_commit_diff_contains_expected_change(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    latest = analyzer.get_commits(limit=1)[0]
    diff = analyzer.get_commit_diff(latest.hash)
    assert "app.py" in diff
    assert "-print('v1')" in diff
    assert "+print('v2')" in diff


def test_get_commit_diff_rejects_unknown_commit(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    with pytest.raises(InvalidReferenceError):
        analyzer.get_commit_diff("deadbeef")


def test_get_file_history_returns_commits_touching_file(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    entries = analyzer.get_file_history("app.py")
    assert [e.commit.message for e in entries] == ["Update app.py", "Add app.py"]


def test_get_file_history_rejects_path_traversal(temp_git_repo):
    analyzer = GitAnalyzer(temp_git_repo)
    with pytest.raises(ValueError):
        analyzer.get_file_history("../outside.txt")


def test_analyzer_rejects_non_git_directory(tmp_path, monkeypatch):
    # Bound Git's upward repository search to tmp_path's parent, in case the
    # machine running this test happens to have an unrelated repository
    # somewhere above the OS temp directory (e.g. a dotfiles repo in $HOME).
    # GIT_CEILING_DIRECTORIES must name a strict ancestor of tmp_path to take
    # effect - naming tmp_path itself does not stop the upward search.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    with pytest.raises(FileNotFoundError):
        GitAnalyzer(tmp_path)


def test_analyzer_rejects_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        GitAnalyzer(tmp_path / "does-not-exist")


# ---- against the real target-app repository (structural checks only) ------
# These intentionally avoid asserting anything about the specific regression
# commit - the analyzer must stay generic and not encode knowledge of it.


def test_analyzer_works_against_target_app(target_app_path):
    analyzer = GitAnalyzer(target_app_path)

    status = analyzer.get_status()
    assert isinstance(status.branch, str) and status.branch

    commits = analyzer.get_commits(limit=5)
    assert len(commits) >= 1
    assert all(len(c.hash) == 40 for c in commits)

    latest = commits[0]
    detail = analyzer.get_commit_detail(latest.hash)
    assert detail.hash == latest.hash
    assert detail.changed_files  # every real commit here touches at least one file

    diff = analyzer.get_commit_diff(latest.hash)
    assert isinstance(diff, str)


def test_file_history_for_auth_module(target_app_path):
    analyzer = GitAnalyzer(target_app_path)
    entries = analyzer.get_file_history("app/auth.py")
    assert len(entries) >= 1
    assert all(e.file_path == "app/auth.py" for e in entries)

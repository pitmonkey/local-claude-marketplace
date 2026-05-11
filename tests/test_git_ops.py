from __future__ import annotations

import json
import logging
import subprocess
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.marketplace.core.git_ops import (
    _inject_token,
    check_token_expiry,
    clone_repo,
    get_file_sha,
    get_repo_sha,
    pull_repo,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a real temp git repo for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    return repo


def test_get_repo_sha(git_repo: Path) -> None:
    """Test getting the current HEAD sha from a repo."""
    # Create a file and commit it
    test_file = git_repo / "test.txt"
    test_file.write_text("test content")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=git_repo, check=True)

    sha = get_repo_sha(git_repo)
    # SHA should be 40 hex characters
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


def test_get_file_sha_returns_commit_sha(git_repo: Path) -> None:
    """Test that get_file_sha returns the commit sha of a committed file."""
    # Create and commit a file
    test_file = git_repo / "test.txt"
    test_file.write_text("test content")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Add test.txt"], cwd=git_repo, check=True)

    # Get the file sha
    file_sha = get_file_sha(git_repo, "test.txt")
    # Should be 40 hex characters
    assert len(file_sha) == 40
    assert all(c in "0123456789abcdef" for c in file_sha)


def test_get_file_sha_missing_file_returns_empty(git_repo: Path) -> None:
    """Test that get_file_sha returns empty string for uncommitted files."""
    file_sha = get_file_sha(git_repo, "nonexistent.txt")
    assert file_sha == ""


def test_clone_repo(git_repo: Path, tmp_path: Path) -> None:
    """Test cloning a repo."""
    # Create a commit to clone
    test_file = git_repo / "test.txt"
    test_file.write_text("test content")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=git_repo, check=True)

    # Clone to a new directory
    clone_dest = tmp_path / "clone"
    clone_repo(str(git_repo), clone_dest)

    # Verify the clone exists and has the file
    assert clone_dest.exists()
    assert (clone_dest / "test.txt").exists()


def test_clone_repo_is_noop_if_exists(git_repo: Path, tmp_path: Path) -> None:
    """Test that clone_repo is a no-op if dest already exists."""
    # Create a commit to clone
    test_file = git_repo / "test.txt"
    test_file.write_text("test content")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=git_repo, check=True)

    # Clone to a new directory
    clone_dest = tmp_path / "clone"
    clone_repo(str(git_repo), clone_dest)

    # Clone again (should be no-op)
    clone_repo(str(git_repo), clone_dest)

    # Verify the clone still exists
    assert clone_dest.exists()
    assert (clone_dest / "test.txt").exists()


def test_pull_repo(git_repo: Path, tmp_path: Path) -> None:
    """Test pulling a repo."""
    # Create a commit to clone
    test_file = git_repo / "test.txt"
    test_file.write_text("test content 1")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=git_repo, check=True)

    # Clone to a new directory
    clone_dest = tmp_path / "clone"
    clone_repo(str(git_repo), clone_dest)

    # Get the initial sha
    initial_sha = get_repo_sha(clone_dest)

    # Add another commit to the source repo
    test_file.write_text("test content 2")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Second commit"], cwd=git_repo, check=True)

    # Pull the changes
    new_sha = pull_repo(clone_dest)

    # Verify the sha changed
    assert new_sha != initial_sha
    # Verify the file was updated
    assert (clone_dest / "test.txt").read_text() == "test content 2"


class TestInjectToken:
    def test_https_url_gets_token_injected(self) -> None:
        url = "https://github.com/example/repo.git"
        result = _inject_token(url, "mytoken")
        assert result == "https://token:mytoken@github.com/example/repo.git"

    def test_http_url_gets_token_injected(self) -> None:
        url = "http://example.com/repo.git"
        result = _inject_token(url, "abc123")
        assert result == "http://token:abc123@example.com/repo.git"

    def test_https_url_with_port_gets_token_and_port(self) -> None:
        url = "https://example.com:8443/repo.git"
        result = _inject_token(url, "tok")
        assert "token:tok@example.com:8443" in result

    def test_ssh_url_is_unchanged(self) -> None:
        url = "git@github.com:example/repo.git"
        result = _inject_token(url, "mytoken")
        assert result == url

    def test_local_path_url_is_unchanged(self) -> None:
        url = "/tmp/some/local/repo"
        result = _inject_token(url, "mytoken")
        assert result == url


def test_clone_repo_accepts_token_none(git_repo: Path, tmp_path: Path) -> None:
    """clone_repo with token=None should behave identically to no-token call."""
    test_file = git_repo / "test.txt"
    test_file.write_text("hello")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=git_repo, check=True)

    clone_dest = tmp_path / "clone_no_token"
    clone_repo(str(git_repo), clone_dest, token=None)

    assert clone_dest.exists()
    assert (clone_dest / "test.txt").read_text() == "hello"


def test_pull_repo_accepts_token_none(git_repo: Path, tmp_path: Path) -> None:
    """pull_repo with token=None should behave identically to no-token call."""
    test_file = git_repo / "test.txt"
    test_file.write_text("v1")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=git_repo, check=True)

    clone_dest = tmp_path / "pull_no_token"
    clone_repo(str(git_repo), clone_dest)

    test_file.write_text("v2")
    subprocess.run(["git", "add", "test.txt"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "update"], cwd=git_repo, check=True)

    new_sha = pull_repo(clone_dest, token=None)
    assert len(new_sha) == 40
    assert (clone_dest / "test.txt").read_text() == "v2"


def _make_github_mock_response(expiry_date: str | None) -> MagicMock:
    """Build a mock urlopen context-manager response for GitHub rate_limit."""
    mock_resp = MagicMock()
    mock_resp.headers.get.return_value = expiry_date
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_resp)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


def _make_gitlab_mock_response(expires_at: str | None) -> MagicMock:
    """Build a mock urlopen context-manager response for GitLab token API."""
    payload: dict[str, object] = {"expires_at": expires_at}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_resp)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


def _fmt_github(dt: datetime) -> str:
    """Format datetime as GitHub expiry header value (UTC)."""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_gitlab(dt: datetime) -> str:
    """Format datetime as GitLab expires_at value."""
    return dt.strftime("%Y-%m-%d")


class TestCheckTokenExpiry:
    def test_github_warning_when_expiring_soon(self, caplog: pytest.LogCaptureFixture) -> None:
        expiry = datetime.now(UTC) + timedelta(days=10, hours=12)
        mock_cm = _make_github_mock_response(_fmt_github(expiry))
        with (
            patch("urllib.request.urlopen", return_value=mock_cm),
            caplog.at_level(logging.WARNING, logger="src.marketplace.core.git_ops"),
        ):
            check_token_expiry("tok", "https://github.com/owner/repo")
        assert "PAT expiry in 10 days" in caplog.text

    def test_github_no_warning_when_not_expiring(self, caplog: pytest.LogCaptureFixture) -> None:
        expiry = datetime.now(UTC) + timedelta(days=60)
        mock_cm = _make_github_mock_response(_fmt_github(expiry))
        with (
            patch("urllib.request.urlopen", return_value=mock_cm),
            caplog.at_level(logging.WARNING, logger="src.marketplace.core.git_ops"),
        ):
            check_token_expiry("tok", "https://github.com/owner/repo")
        assert "PAT expiry" not in caplog.text

    def test_github_no_expiry_header(self, caplog: pytest.LogCaptureFixture) -> None:
        mock_cm = _make_github_mock_response(None)
        with (
            patch("urllib.request.urlopen", return_value=mock_cm),
            caplog.at_level(logging.WARNING, logger="src.marketplace.core.git_ops"),
        ):
            check_token_expiry("tok", "https://github.com/owner/repo")
        assert "PAT expiry" not in caplog.text

    def test_gitlab_warning_when_expiring_soon(self, caplog: pytest.LogCaptureFixture) -> None:
        # GitLab uses date-only precision (%Y-%m-%d), so strptime yields midnight UTC.
        # Use timedelta(days=11) so midnight of the resulting date is at least 10 days away.
        expiry = datetime.now(UTC) + timedelta(days=11)
        mock_cm = _make_gitlab_mock_response(_fmt_gitlab(expiry))
        with (
            patch("urllib.request.urlopen", return_value=mock_cm),
            caplog.at_level(logging.WARNING, logger="src.marketplace.core.git_ops"),
        ):
            check_token_expiry("tok", "https://gitlab.com/owner/repo")
        assert "PAT expiry in" in caplog.text
        assert "rotate GIT_AUTH_TOKEN" in caplog.text

    def test_gitlab_null_expiry(self, caplog: pytest.LogCaptureFixture) -> None:
        mock_cm = _make_gitlab_mock_response(None)
        with (
            patch("urllib.request.urlopen", return_value=mock_cm),
            caplog.at_level(logging.WARNING, logger="src.marketplace.core.git_ops"),
        ):
            check_token_expiry("tok", "https://gitlab.com/owner/repo")
        assert "PAT expiry" not in caplog.text

    def test_unknown_host_skips_api_call(self) -> None:
        with patch("urllib.request.urlopen") as mock_urlopen:
            check_token_expiry("tok", "https://example.com/owner/repo")
        assert mock_urlopen.call_count == 0

    def test_network_error_suppressed(self, caplog: pytest.LogCaptureFixture) -> None:
        with (
            patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")),
            caplog.at_level(logging.WARNING, logger="src.marketplace.core.git_ops"),
        ):
            check_token_expiry("tok", "https://github.com/owner/repo")
        assert "PAT expiry check failed" in caplog.text

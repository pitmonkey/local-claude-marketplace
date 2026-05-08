from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.marketplace.core.git_ops import clone_repo, get_file_sha, get_repo_sha, pull_repo


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

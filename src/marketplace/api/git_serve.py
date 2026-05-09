"""Git HTTP smart protocol server for the plugin repository.

Wraps the dulwich WSGI git application in a Starlette ``WSGIMiddleware`` so
it can be mounted directly on a FastAPI application.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from a2wsgi import WSGIMiddleware
from dulwich.repo import Repo
from dulwich.server import BackendRepo, DictBackend
from dulwich.web import HTTPGitApplication


def create_git_wsgi_app(repo_path: Path) -> WSGIMiddleware:
    """Create a WSGI middleware that serves the git repo at *repo_path*.

    The repository must already exist on disk before this function is called.
    Mount the returned middleware on the FastAPI application at ``/git.git``:

    .. code-block:: python

        app.mount("/git.git", create_git_wsgi_app(plugin_repo_path))

    Args:
        repo_path: Absolute path to the dulwich-managed git repository.

    Returns:
        A ``WSGIMiddleware`` instance wrapping the dulwich HTTP git application.
    """
    repo = Repo(str(repo_path))
    backend = DictBackend({b"/": cast(BackendRepo, repo)})
    git_app = HTTPGitApplication(backend)
    return WSGIMiddleware(git_app)  # type: ignore[arg-type]

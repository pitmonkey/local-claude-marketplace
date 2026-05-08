from __future__ import annotations


def test_app_exists() -> None:
    """Verify the FastAPI app is importable and has all routers registered."""
    from src.marketplace.main import app

    assert app.title == "Claude Marketplace"

    routes = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert "/marketplace.json" in routes
    assert "/api/plugins" in routes
    assert "/" in routes

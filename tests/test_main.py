from __future__ import annotations


def test_app_exists() -> None:
    """Verify the FastAPI app is importable and has all routers registered."""
    from src.marketplace.main import app

    assert app.title == "Claude Marketplace"

    def collect_paths(route_list: list) -> set[str]:  # type: ignore[type-arg]
        paths: set[str] = set()
        for r in route_list:
            if hasattr(r, "path"):
                paths.add(r.path)
            if hasattr(r, "original_router"):
                paths |= collect_paths(r.original_router.routes)
        return paths

    routes = collect_paths(app.routes)
    assert "/marketplace.json" in routes
    assert "/api/plugins" in routes
    assert "/" in routes

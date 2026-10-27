"""Pytest plugin integration for Vexfox."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Generator

import pytest

from vexfox.config import RecordMode, VexfoxConfig
from vexfox.transport import use_cassette


def pytest_configure(config: Any) -> None:
    """Register custom markers for vexfox."""
    config.addinivalue_line(
        "markers",
        "vexfox(cassette_path, mode='once', **kwargs): Record or replay HTTP interactions for this test.",
    )


@pytest.fixture
def vexfox(request: pytest.FixtureRequest) -> Generator[Callable[..., use_cassette], None, None]:
    """A pytest fixture providing a callable context manager for vexfox cassettes.

    Example:
        ```python
        def test_api(vexfox):
            with vexfox("fixtures/users.json"):
                resp = httpx.get("https://api.example.com/users")
                assert resp.status_code == 200
        ```
    """

    def _use_cassette(
        cassette_path: str | Path,
        mode: RecordMode | str | None = None,
        config: VexfoxConfig | None = None,
        **kwargs: Any,
    ) -> use_cassette:
        return use_cassette(cassette_path=cassette_path, mode=mode, config=config, **kwargs)

    yield _use_cassette


@pytest.fixture(autouse=True)
def _vexfox_marker_fixture(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Automatically wraps tests annotated with `@pytest.mark.vexfox(...)` in a cassette context."""
    marker = request.node.get_closest_marker("vexfox")
    if marker is None:
        yield
        return

    cassette_path = marker.args[0] if marker.args else f"fixtures/{request.node.name}.json"
    kwargs = dict(marker.kwargs)

    with use_cassette(cassette_path, **kwargs):
        yield

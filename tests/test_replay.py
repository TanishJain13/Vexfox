"""Tests verifying deterministic replay without contacting the live network."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

import vexfox
from vexfox.exceptions import (
    CassetteNotFoundError,
    ExhaustedCassetteError,
    RequestMismatchError,
)


def test_second_run_replays_without_network(
    local_server: str, tmp_path: Path, server_requests: list[dict[str, str]]
) -> None:
    """Verifies that a replayed run returns recorded response and makes 0 server calls."""
    cassette_file = tmp_path / "replay_test.json"

    # 1. Record run
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        resp = httpx.get(f"{local_server}/users")
        assert resp.status_code == 200
        assert resp.json()["users"][0]["name"] == "Ada Lovelace"

    assert len(server_requests) == 1
    server_requests.clear()

    # 2. Replay run in strict REPLAY mode
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
        replayed_resp = httpx.get(f"{local_server}/users")
        assert replayed_resp.status_code == 200
        assert replayed_resp.json()["users"][0]["name"] == "Ada Lovelace"
        assert replayed_resp.headers.get("X-Custom-Header") == "VexfoxTest"

    # ZERO live network calls must have reached the server!
    assert len(server_requests) == 0


def test_missing_cassette_fails_in_replay_mode(tmp_path: Path) -> None:
    """Verifies that an absent cassette file raises CassetteNotFoundError in replay mode."""
    cassette_file = tmp_path / "non_existent.json"

    with pytest.raises(CassetteNotFoundError) as exc_info:
        with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
            httpx.get("https://api.example.com/test")

    assert "Cassette file not found" in str(exc_info.value)
    assert str(cassette_file) in str(exc_info.value)


def test_unexpected_request_fails_in_replay_mode(
    local_server: str, tmp_path: Path, server_requests: list[dict[str, str]]
) -> None:
    """Verifies that an unrecorded request triggers RequestMismatchError without network leakage."""
    cassette_file = tmp_path / "mismatch.json"

    # Record /health only
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.get(f"{local_server}/health")

    server_requests.clear()

    # In replay mode, request /users which was not recorded
    with pytest.raises(RequestMismatchError) as exc_info:
        with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
            httpx.get(f"{local_server}/users")

    assert "No matching recorded interaction found" in str(exc_info.value)
    # Zero server calls
    assert len(server_requests) == 0


def test_multiple_interactions_ordered_replay(
    local_server: str, tmp_path: Path, server_requests: list[dict[str, str]]
) -> None:
    """Verifies that multiple requests are consumed deterministically in order."""
    cassette_file = tmp_path / "multiple.json"

    # Record 3 distinct endpoints
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        r1 = httpx.get(f"{local_server}/health")
        r2 = httpx.get(f"{local_server}/users")
        r3 = httpx.get(f"{local_server}/not-found")

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 404

    server_requests.clear()

    # Replay all 3 in order
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
        rep1 = httpx.get(f"{local_server}/health")
        rep2 = httpx.get(f"{local_server}/users")
        rep3 = httpx.get(f"{local_server}/not-found")

        assert rep1.status_code == 200
        assert rep2.status_code == 200
        assert rep3.status_code == 404

    assert len(server_requests) == 0


def test_exhausted_cassette_fails(
    local_server: str, tmp_path: Path, server_requests: list[dict[str, str]]
) -> None:
    """Verifies that making more requests than recorded raises ExhaustedCassetteError."""
    cassette_file = tmp_path / "exhaust.json"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.get(f"{local_server}/health")

    server_requests.clear()

    with pytest.raises(ExhaustedCassetteError) as exc_info:
        with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
            # 1st request succeeds
            httpx.get(f"{local_server}/health")
            # 2nd request exhausts the single recorded interaction
            httpx.get(f"{local_server}/health")

    assert "All 1 interaction(s) in cassette" in str(exc_info.value)
    assert len(server_requests) == 0


def test_repeat_playback_mode_when_enabled(
    local_server: str, tmp_path: Path, server_requests: list[dict[str, str]]
) -> None:
    """Verifies that when allow_playback_repeats is enabled, interaction can be replayed repeatedly."""
    cassette_file = tmp_path / "repeat.json"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.get(f"{local_server}/health")

    server_requests.clear()

    config = vexfox.VexfoxConfig(
        mode=vexfox.RecordMode.REPLAY,
        allow_playback_repeats=True,
    )
    with vexfox.use_cassette(cassette_file, config=config):
        r1 = httpx.get(f"{local_server}/health")
        r2 = httpx.get(f"{local_server}/health")
        r3 = httpx.get(f"{local_server}/health")

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200

    assert len(server_requests) == 0

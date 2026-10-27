"""Example pytest test suite demonstrating Vexfox integration."""

from __future__ import annotations

import httpx
import pytest

import vexfox


# 1. Using the context manager with local or mock endpoints
def test_user_profile_replay(tmp_path: pytest.TempPathFactory) -> None:
    cassette_path = tmp_path / "profile.json"

    # In your test suite, replace with your API endpoint
    with vexfox.use_cassette(cassette_path, mode=vexfox.RecordMode.ONCE):
        resp = httpx.get("https://httpbin.org/get?user=42")
        assert resp.status_code == 200
        assert "user=42" in resp.text


# 2. Replay an API error scenario (e.g. 404 Not Found or 429 Rate Limit)
def test_simulated_error_replay(tmp_path: pytest.TempPathFactory) -> None:
    cassette_path = tmp_path / "error_404.json"

    with vexfox.use_cassette(cassette_path, mode=vexfox.RecordMode.ONCE):
        resp = httpx.get("https://httpbin.org/status/404")
        assert resp.status_code == 404


# 3. Test strict request mismatch detection
def test_strict_mismatch_prevention(tmp_path: pytest.TempPathFactory) -> None:
    cassette_path = tmp_path / "strict.json"

    # Record /status/200
    with vexfox.use_cassette(cassette_path, mode=vexfox.RecordMode.RECORD):
        httpx.get("https://httpbin.org/status/200")

    # In replay mode, requesting an unrecorded endpoint fails without hitting the network
    with pytest.raises(vexfox.RequestMismatchError):
        with vexfox.use_cassette(cassette_path, mode=vexfox.RecordMode.REPLAY):
            httpx.get("https://httpbin.org/status/500")

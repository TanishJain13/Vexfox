"""Tests verifying deterministic request matching and mismatch reporting."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

import vexfox
from tests.conftest import LocalTestServerHandler
from vexfox.exceptions import RequestMismatchError


def test_query_parameters_matching_order_insensitive(local_server: str, tmp_path: Path) -> None:
    """Verifies that query parameters match regardless of parameter order."""
    cassette_file = tmp_path / "query_match.json"

    # Record with a=1&b=2
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.get(f"{local_server}/users?page=1&limit=20")

    LocalTestServerHandler.request_history.clear()

    # Replay with inverted query order limit=20&page=1
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
        resp = httpx.get(f"{local_server}/users?limit=20&page=1")
        assert resp.status_code == 200

    assert len(LocalTestServerHandler.request_history) == 0


def test_json_body_matching_key_order_insensitive(local_server: str, tmp_path: Path) -> None:
    """Verifies that JSON body matching parses structure rather than fragile raw string equality."""
    cassette_file = tmp_path / "json_match.json"

    # Record with {"name": "Widget", "role": "admin"}
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.post(
            f"{local_server}/items",
            content=b'{"name": "Widget", "role": "admin"}',
            headers={"Content-Type": "application/json"},
        )

    LocalTestServerHandler.request_history.clear()

    # Replay with inverted key order {"role": "admin", "name": "Widget"}
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
        resp = httpx.post(
            f"{local_server}/items",
            content=b'{"role": "admin", "name": "Widget"}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 201

    assert len(LocalTestServerHandler.request_history) == 0


def test_json_body_mismatch_produces_actionable_diagnostic(
    local_server: str, tmp_path: Path
) -> None:
    """Verifies that mismatched body content triggers RequestMismatchError with clear details."""
    cassette_file = tmp_path / "body_mismatch.json"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.post(
            f"{local_server}/items",
            json={"role": "member", "active": True},
        )

    LocalTestServerHandler.request_history.clear()

    with pytest.raises(RequestMismatchError) as exc_info:
        with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
            httpx.post(
                f"{local_server}/items",
                json={"role": "superadmin", "active": True},
            )

    err_msg = str(exc_info.value)
    assert "No matching recorded interaction found" in err_msg
    assert "role" in err_msg
    assert "superadmin" in err_msg or "expected 'member'" in err_msg


def test_method_mismatch_fails_cleanly(local_server: str, tmp_path: Path) -> None:
    """Verifies that sending a POST when GET was recorded fails with clear method diagnostics."""
    cassette_file = tmp_path / "method_mismatch.json"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.get(f"{local_server}/users")

    LocalTestServerHandler.request_history.clear()

    with pytest.raises(RequestMismatchError) as exc_info:
        with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
            httpx.post(f"{local_server}/users")

    err_msg = str(exc_info.value)
    assert "Method mismatch: expected 'GET', got 'POST'" in err_msg


def test_match_headers_when_configured(local_server: str, tmp_path: Path) -> None:
    """Verifies that configured match_headers strictly validates required header values."""
    cassette_file = tmp_path / "headers_match.json"

    config = vexfox.VexfoxConfig(
        match_headers=("x-api-version",),
    )

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD, config=config):
        httpx.get(f"{local_server}/health", headers={"X-Api-Version": "v2"})

    LocalTestServerHandler.request_history.clear()

    # Replay with matching header succeeds
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY, config=config):
        resp = httpx.get(f"{local_server}/health", headers={"X-Api-Version": "v2"})
        assert resp.status_code == 200

    # Replay with different header fails
    with pytest.raises(RequestMismatchError) as exc_info:
        with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY, config=config):
            httpx.get(f"{local_server}/health", headers={"X-Api-Version": "v1"})

    assert "Header 'x-api-version' mismatch" in str(exc_info.value)

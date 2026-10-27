"""Rigorous security and edge-case audit tests for Vexfox."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

import vexfox
from vexfox.exceptions import RequestMismatchError
from vexfox.models import CassetteData


def test_embedded_url_credentials_redacted_on_disk(local_server: str, tmp_path: Path) -> None:
    """Verifies that basic-auth user:password embedded in URLs is scrubbed before saving."""
    cassette_file = tmp_path / "url_creds.json"
    host_port = local_server.replace("http://", "")
    url_with_auth = f"http://admin:super_secret_pw_999@{host_port}/users"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        resp = httpx.get(url_with_auth)
        assert resp.status_code == 200

    raw_cassette = cassette_file.read_text(encoding="utf-8")
    assert "super_secret_pw_999" not in raw_cassette
    assert "[REDACTED]" in raw_cassette


def test_request_mismatch_error_does_not_leak_secrets(local_server: str, tmp_path: Path) -> None:
    """Verifies that RequestMismatchError never exposes sensitive query parameters in error text."""
    cassette_file = tmp_path / "mismatch_no_leak.json"

    # Record /health
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.get(f"{local_server}/health")

    # In replay mode, request /users with a live secret key that will trigger a mismatch
    live_secret = "LIVE_CONFIDENTIAL_KEY_777888"
    with pytest.raises(RequestMismatchError) as exc_info:
        with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
            httpx.get(f"{local_server}/users?api_key={live_secret}")

    err_text = str(exc_info.value)
    # The live secret must NEVER be printed in the exception message!
    assert live_secret not in err_text
    assert "[REDACTED]" in err_text or "api_key" in err_text


def test_authorization_header_in_match_headers_matches_cleanly(
    local_server: str, tmp_path: Path
) -> None:
    """Verifies that match_headers=('authorization',) allows matching when cassette has [REDACTED]."""
    cassette_file = tmp_path / "auth_match_header.json"

    config = vexfox.VexfoxConfig(
        match_headers=("authorization",),
    )

    live_token = "Bearer live_token_xyz_12345"

    # 1. Record
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD, config=config):
        resp = httpx.get(f"{local_server}/users", headers={"Authorization": live_token})
        assert resp.status_code == 200

    # Verify disk cassette is scrubbed
    raw_text = cassette_file.read_text(encoding="utf-8")
    assert live_token not in raw_text

    # 2. Replay with matching Authorization header (even with different live token)
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY, config=config):
        resp_replayed = httpx.get(
            f"{local_server}/users",
            headers={"Authorization": "Bearer another_live_token_67890"},
        )
        assert resp_replayed.status_code == 200


def test_response_secrets_redacted_on_disk(tmp_path: Path) -> None:
    """Verifies that response body tokens and set-cookie headers are sanitized on disk."""
    cassette_file = tmp_path / "resp_secrets.json"
    cassette = vexfox.Cassette(cassette_file)

    req = vexfox.RecordedRequest(method="POST", url="https://api.example.com/oauth/token")
    resp = vexfox.RecordedResponse(
        status_code=200,
        headers={"Set-Cookie": ["session_id=ultra_secret_cookie; Secure; HttpOnly"]},
        body=json.dumps(
            {
                "access_token": "mock_synthetic_access_token_1234567890",
                "refresh_token": "mock_synthetic_refresh_token_9876543210",
                "token_type": "Bearer",
                "user_id": 42,
            }
        ),
    )

    cassette.record_interaction(req, resp)
    cassette.save()

    raw_text = cassette_file.read_text(encoding="utf-8")
    assert "ultra_secret_cookie" not in raw_text
    assert "mock_synthetic_access_token_1234567890" not in raw_text
    assert "mock_synthetic_refresh_token_9876543210" not in raw_text

    data = CassetteData.from_json(raw_text)
    saved_body = json.loads(data.interactions[0].response.body or "{}")
    assert saved_body["access_token"] == "[REDACTED]"
    assert saved_body["refresh_token"] == "[REDACTED]"
    assert saved_body["user_id"] == 42


def test_standalone_transport_saves_on_close(local_server: str, tmp_path: Path) -> None:
    """Verifies that using VexfoxSyncTransport directly saves cassette when client closes."""
    cassette_file = tmp_path / "standalone_transport.json"
    cassette = vexfox.Cassette(cassette_file, vexfox.VexfoxConfig(mode=vexfox.RecordMode.RECORD))

    transport = vexfox.VexfoxSyncTransport(cassette)
    with httpx.Client(transport=transport) as client:
        resp = client.get(f"{local_server}/health")
        assert resp.status_code == 200

    # On client exit, transport.close() was called and cassette must be persisted!
    assert cassette_file.exists()
    data = CassetteData.from_json(cassette_file.read_text(encoding="utf-8"))
    assert len(data.interactions) == 1
    assert data.interactions[0].response.status_code == 200


def test_duplicate_query_parameters_matching(local_server: str, tmp_path: Path) -> None:
    """Verifies that duplicate query parameters (lists) match accurately."""
    cassette_file = tmp_path / "duplicate_queries.json"

    # Record ?tag=python&tag=async&tag=testing
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.get(f"{local_server}/users?tag=python&tag=async&tag=testing")

    # Replay with tags in different order: ?tag=testing&tag=python&tag=async
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
        resp = httpx.get(f"{local_server}/users?tag=testing&tag=python&tag=async")
        assert resp.status_code == 200

    # Replay with missing duplicate tag fails
    with pytest.raises(RequestMismatchError):
        with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
            httpx.get(f"{local_server}/users?tag=python&tag=async")

"""Tests verifying security sanitization and secret redaction before disk persistence."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

import vexfox
from tests.conftest import LocalTestServerHandler
from vexfox.models import CassetteData


def test_authorization_and_cookie_headers_redacted_on_disk(
    local_server: str, tmp_path: Path
) -> None:
    """Verifies that Authorization and Cookie headers are replaced with [REDACTED] on disk."""
    cassette_file = tmp_path / "auth_redacted.json"

    secret_auth_token = "Bearer secret-token-xyz-9876543210"
    secret_cookie = "session_id=super_secret_cookie_value"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        resp = httpx.get(
            f"{local_server}/users",
            headers={
                "Authorization": secret_auth_token,
                "Cookie": secret_cookie,
                "X-Api-Key": "my-secret-key-12345",
            },
        )
        assert resp.status_code == 200

    # Read raw cassette file from disk
    raw_content = cassette_file.read_text(encoding="utf-8")

    # Critical security assertion: secrets must NEVER appear in the persisted file!
    assert "secret-token-xyz-9876543210" not in raw_content
    assert "super_secret_cookie_value" not in raw_content
    assert "my-secret-key-12345" not in raw_content

    # Verify [REDACTED] marker was used
    data = CassetteData.from_json(raw_content)
    req_headers = data.interactions[0].request.headers

    # Check case-insensitively
    headers_lower = {k.lower(): v for k, v in req_headers.items()}
    assert headers_lower.get("authorization") == ["[REDACTED]"]
    assert headers_lower.get("cookie") == ["[REDACTED]"]
    assert headers_lower.get("x-api-key") == ["[REDACTED]"]


def test_query_parameter_secrets_redacted(local_server: str, tmp_path: Path) -> None:
    """Verifies that sensitive query parameters are redacted from both query dict and URL string."""
    cassette_file = tmp_path / "query_redacted.json"
    secret_key = "super_secret_api_key_abc123"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        resp = httpx.get(f"{local_server}/users?api_key={secret_key}&page=1")
        assert resp.status_code == 200

    raw_content = cassette_file.read_text(encoding="utf-8")
    assert secret_key not in raw_content
    assert "[REDACTED]" in raw_content

    data = CassetteData.from_json(raw_content)
    interaction = data.interactions[0]
    assert interaction.request.query.get("api_key") == ["[REDACTED]"]
    assert interaction.request.query.get("page") == ["1"]
    assert (
        "api_key=%5BREDACTED%5D" in interaction.request.url
        or "api_key=[REDACTED]" in interaction.request.url
    )


def test_json_body_secrets_redacted(local_server: str, tmp_path: Path) -> None:
    """Verifies that sensitive keys in request bodies are replaced with [REDACTED]."""
    cassette_file = tmp_path / "body_redacted.json"
    secret_password = "very_sensitive_user_password_999"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        resp = httpx.post(
            f"{local_server}/items",
            json={
                "username": "alex",
                "password": secret_password,
                "api_key": "test_mock_api_key_12345abcdef",
            },
        )
        assert resp.status_code == 201

    raw_content = cassette_file.read_text(encoding="utf-8")
    assert secret_password not in raw_content
    assert "test_mock_api_key_12345abcdef" not in raw_content

    data = CassetteData.from_json(raw_content)
    body_dict = json.loads(data.interactions[0].request.body or "{}")
    assert body_dict["username"] == "alex"
    assert body_dict["password"] == "[REDACTED]"
    assert body_dict["api_key"] == "[REDACTED]"


def test_regex_secret_patterns_redacted_in_plain_text(local_server: str, tmp_path: Path) -> None:
    """Verifies that regex secret patterns like Bearer tokens or Stripe/OpenAI keys are redacted."""
    cassette_file = tmp_path / "regex_redacted.json"
    openai_key = "sk-FAKE_TEST_KEY_NOT_VALID_123456789"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        resp = httpx.post(
            f"{local_server}/items",
            content=f"Connecting with token: {openai_key}".encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 201

    raw_content = cassette_file.read_text(encoding="utf-8")
    assert openai_key not in raw_content
    assert "[REDACTED]" in raw_content

    data = CassetteData.from_json(raw_content)
    assert data.interactions[0].request.body == "Connecting with token: [REDACTED]"


def test_all_supported_regex_patterns_redacted(local_server: str, tmp_path: Path) -> None:
    """Verifies that all default secret regex patterns (Bearer, Stripe, OpenAI, JWT, AWS) are redacted."""
    cassette_file = tmp_path / "all_patterns_redacted.json"

    # Synthetic, non-functional dummy fixtures designed not to trigger provider secret scanners
    bearer_val = "Bearer mock_synthetic_bearer_token_12345"
    stripe_val = "sk_test_mockdummyfixture12345"
    openai_val = "sk-mock-synthetic-openai-key-99999"
    jwt_val = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.mock_signature"
    aws_val = "AKIAIOSFODNN7EXAMPLE"  # Official AWS documentation dummy identifier

    test_payload = (
        f"auth={bearer_val}&stripe={stripe_val}&openai={openai_val}&jwt={jwt_val}&aws={aws_val}"
    )

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        resp = httpx.post(
            f"{local_server}/items",
            content=test_payload.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 201

    raw_content = cassette_file.read_text(encoding="utf-8")
    assert bearer_val not in raw_content
    assert stripe_val not in raw_content
    assert openai_val not in raw_content
    assert jwt_val not in raw_content
    assert aws_val not in raw_content

    data = CassetteData.from_json(raw_content)
    assert (
        data.interactions[0].request.body
        == "auth=[REDACTED]&stripe=[REDACTED]&openai=[REDACTED]&jwt=[REDACTED]&aws=[REDACTED]"
    )


def test_replay_with_redacted_secrets_matches_incoming_secrets(
    local_server: str, tmp_path: Path
) -> None:
    """Verifies that when replaying a request with sensitive data, it matches the redacted cassette correctly."""
    cassette_file = tmp_path / "replay_redacted_match.json"

    # 1. Record
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        httpx.get(
            f"{local_server}/users?api_key=my_live_secret",
            headers={"Authorization": "Bearer token123"},
        )

    LocalTestServerHandler.request_history.clear()

    # 2. Replay with matching sensitive parameter and header
    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
        resp = httpx.get(
            f"{local_server}/users?api_key=my_live_secret",
            headers={"Authorization": "Bearer token123"},
        )
        assert resp.status_code == 200

    assert len(LocalTestServerHandler.request_history) == 0

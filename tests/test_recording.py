"""Tests verifying real HTTP recording behavior."""

from __future__ import annotations

from pathlib import Path

import httpx

import vexfox
from vexfox.models import CassetteData


def test_first_run_records_real_response(
    local_server: str, tmp_path: Path, server_requests: list[dict[str, str]]
) -> None:
    """Verifies that the first run contacts the real server, returns response, and persists cassette."""
    cassette_file = tmp_path / "first_run.json"
    assert not cassette_file.exists()

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.ONCE):
        resp = httpx.get(f"{local_server}/users")
        assert resp.status_code == 200
        assert resp.json() == {"users": [{"id": 1, "name": "Ada Lovelace"}]}
        assert resp.headers.get("X-Custom-Header") == "VexfoxTest"

    # Verify server actually received request
    assert len(server_requests) == 1
    assert server_requests[0]["path"] == "/users"

    # Verify cassette was persisted to disk
    assert cassette_file.exists()
    data = CassetteData.from_json(cassette_file.read_text(encoding="utf-8"))
    assert data.version == 1
    assert len(data.interactions) == 1

    interaction = data.interactions[0]
    assert interaction.request.method == "GET"
    assert f"{local_server}/users" in interaction.request.url
    assert interaction.response.status_code == 200
    assert "Ada Lovelace" in (interaction.response.body or "")


def test_recording_reusable_client(local_server: str, tmp_path: Path) -> None:
    """Verifies that using `with httpx.Client() as client` inside cassette records properly."""
    cassette_file = tmp_path / "client_run.json"

    with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        with httpx.Client() as client:
            resp1 = client.get(f"{local_server}/health")
            resp2 = client.post(f"{local_server}/items", json={"name": "Widget"})

            assert resp1.status_code == 200
            assert resp1.json() == {"status": "healthy"}
            assert resp2.status_code == 201
            assert resp2.json() == {"created": True, "id": 101}

    assert cassette_file.exists()
    data = CassetteData.from_json(cassette_file.read_text(encoding="utf-8"))
    assert len(data.interactions) == 2
    assert data.interactions[0].request.method == "GET"
    assert data.interactions[1].request.method == "POST"


def test_recording_binary_and_empty_responses(local_server: str, tmp_path: Path) -> None:
    """Verifies that binary payloads and empty 204 responses are recorded correctly."""
    cassette_file = tmp_path / "binary_empty.json"

    with vexfox.use_cassette(cassette_file):
        resp_bin = httpx.get(f"{local_server}/binary")
        assert resp_bin.status_code == 200
        assert resp_bin.content == bytes([0x00, 0xFF, 0xFE, 0x12, 0x34])

        resp_empty = httpx.get(f"{local_server}/empty")
        assert resp_empty.status_code == 204
        assert resp_empty.content == b""

    data = CassetteData.from_json(cassette_file.read_text(encoding="utf-8"))
    assert len(data.interactions) == 2

    bin_interaction = data.interactions[0]
    assert bin_interaction.response.is_binary is True
    assert bin_interaction.response.get_body_bytes() == bytes([0x00, 0xFF, 0xFE, 0x12, 0x34])

    empty_interaction = data.interactions[1]
    assert empty_interaction.response.status_code == 204
    assert empty_interaction.response.get_body_bytes() == b""

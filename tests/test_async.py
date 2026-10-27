"""Tests verifying asynchronous HTTPX client recording and replay."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

import vexfox
from vexfox.models import CassetteData


@pytest.mark.asyncio
async def test_async_recording_and_replay(
    local_server: str, tmp_path: Path, server_requests: list[dict[str, str]]
) -> None:
    """Verifies that httpx.AsyncClient records and replays accurately."""
    cassette_file = tmp_path / "async_cassette.json"

    # 1. Record using AsyncClient
    async with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{local_server}/users")
            assert resp.status_code == 200
            assert resp.json()["users"][0]["name"] == "Ada Lovelace"

    assert len(server_requests) == 1
    server_requests.clear()

    # Verify cassette exists
    assert cassette_file.exists()
    data = CassetteData.from_json(cassette_file.read_text(encoding="utf-8"))
    assert len(data.interactions) == 1

    # 2. Replay using AsyncClient
    async with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
        async with httpx.AsyncClient() as client:
            replayed_resp = await client.get(f"{local_server}/users")
            assert replayed_resp.status_code == 200
            assert replayed_resp.json()["users"][0]["name"] == "Ada Lovelace"

    # Verify zero network requests
    assert len(server_requests) == 0


@pytest.mark.asyncio
async def test_async_post_with_body_matching(
    local_server: str, tmp_path: Path, server_requests: list[dict[str, str]]
) -> None:
    """Verifies async POST with body recording and replay."""
    cassette_file = tmp_path / "async_post.json"

    async with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.RECORD):
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{local_server}/items", json={"task": "Async Test"})
            assert resp.status_code == 201

    server_requests.clear()

    async with vexfox.use_cassette(cassette_file, mode=vexfox.RecordMode.REPLAY):
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{local_server}/items", json={"task": "Async Test"})
            assert resp.status_code == 201
            assert resp.json() == {"created": True, "id": 101}

    assert len(server_requests) == 0

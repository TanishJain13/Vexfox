"""HTTPX transport interception and context manager for Vexfox."""

from __future__ import annotations

import time
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import httpx

from vexfox.cassette import Cassette
from vexfox.config import RecordMode, VexfoxConfig
from vexfox.exceptions import (
    NestedCassetteError,
)
from vexfox.models import RecordedRequest, RecordedResponse

# Context variable tracking the current active cassette
_ACTIVE_CASSETTE: ContextVar[Cassette | None] = ContextVar("_ACTIVE_CASSETTE", default=None)

# Storage for original methods when patched
_ORIGINAL_SYNC_SEND: Callable[..., httpx.Response] | None = None
_ORIGINAL_ASYNC_SEND: Callable[..., Any] | None = None
_PATCH_COUNT: int = 0


def _request_to_recorded(request: httpx.Request, store_body: bool = True) -> RecordedRequest:
    """Converts an httpx.Request into a Vexfox RecordedRequest model."""
    headers_dict: dict[str, list[str]] = {}
    for k, v in request.headers.multi_items():
        headers_dict.setdefault(k, []).append(v)

    parsed = urlparse(str(request.url))
    query_dict = parse_qs(parsed.query, keep_blank_values=True)

    # Read body bytes safely
    body_bytes = request.content if hasattr(request, "content") else b""

    return RecordedRequest.from_bytes(
        method=request.method,
        url=str(request.url),
        headers=headers_dict,
        query=query_dict,
        body_bytes=body_bytes,
        store_body=store_body,
    )


def _recorded_to_response(recorded: RecordedResponse, request: httpx.Request) -> httpx.Response:
    """Constructs an httpx.Response from a Vexfox RecordedResponse model."""
    body_bytes = recorded.get_body_bytes()
    # Flatten multi-item headers or preserve them
    headers: list[tuple[str, str]] = []
    for k, values in recorded.headers.items():
        for v in values:
            headers.append((k, v))

    return httpx.Response(
        status_code=recorded.status_code,
        headers=headers,
        content=body_bytes,
        request=request,
        extensions={"http_version": recorded.http_version.encode("ascii")},
    )


class VexfoxSyncTransport(httpx.BaseTransport):
    """A standalone synchronous HTTPX transport that records or replays using a Cassette."""

    def __init__(
        self,
        cassette: Cassette,
        real_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.cassette = cassette
        self.real_transport = real_transport or httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        recorded_req = _request_to_recorded(request, store_body=self.cassette.config.store_body)

        mode = self.cassette.config.mode
        should_replay = mode == RecordMode.REPLAY or (
            mode == RecordMode.ONCE and self.cassette.file_exists
        )

        if should_replay:
            recorded_resp = self.cassette.find_match(recorded_req)
            return _recorded_to_response(recorded_resp, request)

        if mode == RecordMode.NONE:
            return self.real_transport.handle_request(request)

        # Recording mode (RECORD or ONCE with missing file)
        start_time = time.perf_counter()
        response = self.real_transport.handle_request(request)
        response.read()
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        headers_dict: dict[str, list[str]] = {}
        for k, v in response.headers.multi_items():
            headers_dict.setdefault(k, []).append(v)

        recorded_resp = RecordedResponse.from_bytes(
            status_code=response.status_code,
            headers=headers_dict,
            body_bytes=response.content,
            http_version=response.extensions.get("http_version", b"HTTP/1.1").decode("ascii"),
            reason_phrase=response.reason_phrase or "OK",
        )

        self.cassette.record_interaction(recorded_req, recorded_resp, duration_ms)
        return response

    def close(self) -> None:
        try:
            self.cassette.save()
        finally:
            if hasattr(self.real_transport, "close"):
                self.real_transport.close()


class VexfoxAsyncTransport(httpx.AsyncBaseTransport):
    """A standalone asynchronous HTTPX transport that records or replays using a Cassette."""

    def __init__(
        self,
        cassette: Cassette,
        real_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.cassette = cassette
        self.real_transport = real_transport or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await request.aread()
        recorded_req = _request_to_recorded(request, store_body=self.cassette.config.store_body)

        mode = self.cassette.config.mode
        should_replay = mode == RecordMode.REPLAY or (
            mode == RecordMode.ONCE and self.cassette.file_exists
        )

        if should_replay:
            recorded_resp = self.cassette.find_match(recorded_req)
            return _recorded_to_response(recorded_resp, request)

        if mode == RecordMode.NONE:
            return await self.real_transport.handle_async_request(request)

        # Recording mode
        start_time = time.perf_counter()
        response = await self.real_transport.handle_async_request(request)
        await response.aread()
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        headers_dict: dict[str, list[str]] = {}
        for k, v in response.headers.multi_items():
            headers_dict.setdefault(k, []).append(v)

        recorded_resp = RecordedResponse.from_bytes(
            status_code=response.status_code,
            headers=headers_dict,
            body_bytes=response.content,
            http_version=response.extensions.get("http_version", b"HTTP/1.1").decode("ascii"),
            reason_phrase=response.reason_phrase or "OK",
        )

        self.cassette.record_interaction(recorded_req, recorded_resp, duration_ms)
        return response

    async def aclose(self) -> None:
        try:
            self.cassette.save()
        finally:
            if hasattr(self.real_transport, "aclose"):
                await self.real_transport.aclose()


def _patched_sync_send(
    self: httpx.Client,
    request: httpx.Request,
    **kwargs: Any,
) -> httpx.Response:
    """Intercepts httpx.Client.send during an active cassette context."""
    cassette = _ACTIVE_CASSETTE.get()
    if cassette is None:
        assert _ORIGINAL_SYNC_SEND is not None
        return _ORIGINAL_SYNC_SEND(self, request, **kwargs)

    # Read request body content
    request.read()
    recorded_req = _request_to_recorded(request, store_body=cassette.config.store_body)

    mode = cassette.config.mode
    should_replay = mode == RecordMode.REPLAY or (mode == RecordMode.ONCE and cassette.file_exists)

    if should_replay:
        recorded_resp = cassette.find_match(recorded_req)
        return _recorded_to_response(recorded_resp, request)

    if mode == RecordMode.NONE:
        assert _ORIGINAL_SYNC_SEND is not None
        return _ORIGINAL_SYNC_SEND(self, request, **kwargs)

    # Recording mode (RECORD or ONCE when file is missing)
    assert _ORIGINAL_SYNC_SEND is not None
    start_time = time.perf_counter()
    response = _ORIGINAL_SYNC_SEND(self, request, **kwargs)
    response.read()
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    headers_dict: dict[str, list[str]] = {}
    for k, v in response.headers.multi_items():
        headers_dict.setdefault(k, []).append(v)

    recorded_resp = RecordedResponse.from_bytes(
        status_code=response.status_code,
        headers=headers_dict,
        body_bytes=response.content,
        http_version=response.extensions.get("http_version", b"HTTP/1.1").decode("ascii"),
        reason_phrase=response.reason_phrase or "OK",
    )

    cassette.record_interaction(recorded_req, recorded_resp, duration_ms)
    return response


async def _patched_async_send(
    self: httpx.AsyncClient,
    request: httpx.Request,
    **kwargs: Any,
) -> httpx.Response:
    """Intercepts httpx.AsyncClient.send during an active cassette context."""
    cassette = _ACTIVE_CASSETTE.get()
    if cassette is None:
        assert _ORIGINAL_ASYNC_SEND is not None
        return await _ORIGINAL_ASYNC_SEND(self, request, **kwargs)

    await request.aread()
    recorded_req = _request_to_recorded(request, store_body=cassette.config.store_body)

    mode = cassette.config.mode
    should_replay = mode == RecordMode.REPLAY or (mode == RecordMode.ONCE and cassette.file_exists)

    if should_replay:
        recorded_resp = cassette.find_match(recorded_req)
        return _recorded_to_response(recorded_resp, request)

    if mode == RecordMode.NONE:
        assert _ORIGINAL_ASYNC_SEND is not None
        return await _ORIGINAL_ASYNC_SEND(self, request, **kwargs)

    assert _ORIGINAL_ASYNC_SEND is not None
    start_time = time.perf_counter()
    response = await _ORIGINAL_ASYNC_SEND(self, request, **kwargs)
    await response.aread()
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    headers_dict: dict[str, list[str]] = {}
    for k, v in response.headers.multi_items():
        headers_dict.setdefault(k, []).append(v)

    recorded_resp = RecordedResponse.from_bytes(
        status_code=response.status_code,
        headers=headers_dict,
        body_bytes=response.content,
        http_version=response.extensions.get("http_version", b"HTTP/1.1").decode("ascii"),
        reason_phrase=response.reason_phrase or "OK",
    )

    cassette.record_interaction(recorded_req, recorded_resp, duration_ms)
    return response


def _install_client_interceptor() -> None:
    """Installs the HTTPX client interception hooks."""
    global _ORIGINAL_SYNC_SEND, _ORIGINAL_ASYNC_SEND, _PATCH_COUNT
    if _PATCH_COUNT == 0:
        _ORIGINAL_SYNC_SEND = httpx.Client.send
        _ORIGINAL_ASYNC_SEND = httpx.AsyncClient.send
        httpx.Client.send = _patched_sync_send  # type: ignore[assignment]
        httpx.AsyncClient.send = _patched_async_send  # type: ignore[assignment]
    _PATCH_COUNT += 1


def _uninstall_client_interceptor() -> None:
    """Restores the original HTTPX client methods."""
    global _ORIGINAL_SYNC_SEND, _ORIGINAL_ASYNC_SEND, _PATCH_COUNT
    _PATCH_COUNT = max(0, _PATCH_COUNT - 1)
    if _PATCH_COUNT == 0:
        if _ORIGINAL_SYNC_SEND is not None:
            httpx.Client.send = _ORIGINAL_SYNC_SEND  # type: ignore[assignment]
            _ORIGINAL_SYNC_SEND = None
        if _ORIGINAL_ASYNC_SEND is not None:
            httpx.AsyncClient.send = _ORIGINAL_ASYNC_SEND  # type: ignore[assignment]
            _ORIGINAL_ASYNC_SEND = None


class use_cassette:
    """Context manager for recording and replaying HTTP interactions.

    Example:
        ```python
        with vexfox.use_cassette("fixtures/api.json"):
            response = httpx.get("https://api.example.com/users")
            assert response.status_code == 200
        ```
    """

    def __init__(
        self,
        cassette_path: str | Path,
        mode: RecordMode | str | None = None,
        config: VexfoxConfig | None = None,
        **config_overrides: Any,
    ) -> None:
        self.cassette_path = str(cassette_path)
        base_config = config or VexfoxConfig()

        if mode is not None:
            base_config.mode = RecordMode(mode) if isinstance(mode, str) else mode

        for k, v in config_overrides.items():
            if hasattr(base_config, k):
                setattr(base_config, k, v)

        self.config = base_config
        self.cassette: Cassette | None = None
        self._token: Any = None

    def __enter__(self) -> Cassette:
        active = _ACTIVE_CASSETTE.get()
        if active is not None:
            raise NestedCassetteError(
                active_path=str(active.path),
                attempted_path=self.cassette_path,
            )

        self.cassette = Cassette(self.cassette_path, self.config)
        self._token = _ACTIVE_CASSETTE.set(self.cassette)
        _install_client_interceptor()
        return self.cassette

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if self.cassette is not None and exc_type is None:
                self.cassette.save()
        finally:
            _uninstall_client_interceptor()
            if self._token is not None:
                _ACTIVE_CASSETTE.reset(self._token)
                self._token = None

    async def __aenter__(self) -> Cassette:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)

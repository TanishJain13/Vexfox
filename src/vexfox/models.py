"""Data models for Vexfox cassette recordings."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1
RECORDER_NAME = "vexfox 0.1.0"


@dataclass
class RecordedRequest:
    """Represents an intercepted and sanitized HTTP request."""

    method: str
    url: str
    headers: dict[str, list[str]] = field(default_factory=dict)
    query: dict[str, list[str]] = field(default_factory=dict)
    body: str | None = None
    is_binary: bool = False

    def get_body_bytes(self) -> bytes:
        """Returns the request body as raw bytes."""
        if self.body is None:
            return b""
        if self.is_binary:
            return base64.b64decode(self.body.encode("ascii"))
        return self.body.encode("utf-8")

    @classmethod
    def from_bytes(
        cls,
        method: str,
        url: str,
        headers: dict[str, list[str]],
        query: dict[str, list[str]],
        body_bytes: bytes | None,
        store_body: bool = True,
    ) -> RecordedRequest:
        """Creates a RecordedRequest from raw bytes, handling text and binary encodings."""
        if not store_body or body_bytes is None or len(body_bytes) == 0:
            return cls(
                method=method.upper(),
                url=url,
                headers=headers,
                query=query,
                body=None,
                is_binary=False,
            )

        try:
            text = body_bytes.decode("utf-8")
            return cls(
                method=method.upper(),
                url=url,
                headers=headers,
                query=query,
                body=text,
                is_binary=False,
            )
        except UnicodeDecodeError:
            b64_str = base64.b64encode(body_bytes).decode("ascii")
            return cls(
                method=method.upper(),
                url=url,
                headers=headers,
                query=query,
                body=b64_str,
                is_binary=True,
            )


@dataclass
class RecordedResponse:
    """Represents an intercepted HTTP response."""

    status_code: int
    headers: dict[str, list[str]] = field(default_factory=dict)
    body: str | None = None
    is_binary: bool = False
    http_version: str = "HTTP/1.1"
    reason_phrase: str = "OK"

    def get_body_bytes(self) -> bytes:
        """Returns the response body as raw bytes."""
        if self.body is None:
            return b""
        if self.is_binary:
            return base64.b64decode(self.body.encode("ascii"))
        return self.body.encode("utf-8")

    @classmethod
    def from_bytes(
        cls,
        status_code: int,
        headers: dict[str, list[str]],
        body_bytes: bytes | None,
        http_version: str = "HTTP/1.1",
        reason_phrase: str = "OK",
    ) -> RecordedResponse:
        """Creates a RecordedResponse from raw bytes, handling text and binary encodings."""
        if body_bytes is None or len(body_bytes) == 0:
            return cls(
                status_code=status_code,
                headers=headers,
                body="",
                is_binary=False,
                http_version=http_version,
                reason_phrase=reason_phrase,
            )

        try:
            text = body_bytes.decode("utf-8")
            return cls(
                status_code=status_code,
                headers=headers,
                body=text,
                is_binary=False,
                http_version=http_version,
                reason_phrase=reason_phrase,
            )
        except UnicodeDecodeError:
            b64_str = base64.b64encode(body_bytes).decode("ascii")
            return cls(
                status_code=status_code,
                headers=headers,
                body=b64_str,
                is_binary=True,
                http_version=http_version,
                reason_phrase=reason_phrase,
            )


@dataclass
class Interaction:
    """A paired request and response recorded at a specific moment."""

    id: str
    recorded_at: str
    duration_ms: float
    request: RecordedRequest
    response: RecordedResponse


@dataclass
class CassetteData:
    """Top-level versioned schema for a Vexfox cassette file."""

    version: int = SCHEMA_VERSION
    recorder: str = RECORDER_NAME
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    interactions: list[Interaction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converts the cassette data to a JSON-serializable dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serializes cassette data to a formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CassetteData:
        """Deserializes a dictionary into a CassetteData object with schema validation."""
        if not isinstance(data, dict):
            raise ValueError("Cassette root must be a JSON object.")

        version = data.get("version")
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported cassette schema version: {version}. Expected version {SCHEMA_VERSION}."
            )

        recorder = str(data.get("recorder", RECORDER_NAME))
        recorded_at = str(data.get("recorded_at", datetime.now(timezone.utc).isoformat()))

        raw_interactions = data.get("interactions")
        if not isinstance(raw_interactions, list):
            raise ValueError("Cassette 'interactions' must be a list.")

        interactions: list[Interaction] = []
        for idx, item in enumerate(raw_interactions):
            if not isinstance(item, dict):
                raise ValueError(f"Interaction at index {idx} must be an object.")

            req_data = item.get("request")
            resp_data = item.get("response")

            if not isinstance(req_data, dict) or not isinstance(resp_data, dict):
                raise ValueError(
                    f"Interaction {item.get('id', idx)} must contain 'request' and 'response' objects."
                )

            request = RecordedRequest(
                method=str(req_data.get("method", "GET")),
                url=str(req_data.get("url", "")),
                headers=req_data.get("headers", {}),
                query=req_data.get("query", {}),
                body=req_data.get("body"),
                is_binary=bool(req_data.get("is_binary", False)),
            )

            response = RecordedResponse(
                status_code=int(resp_data.get("status_code", 200)),
                headers=resp_data.get("headers", {}),
                body=resp_data.get("body"),
                is_binary=bool(resp_data.get("is_binary", False)),
                http_version=str(resp_data.get("http_version", "HTTP/1.1")),
                reason_phrase=str(resp_data.get("reason_phrase", "OK")),
            )

            interactions.append(
                Interaction(
                    id=str(item.get("id", str(idx + 1))),
                    recorded_at=str(item.get("recorded_at", "")),
                    duration_ms=float(item.get("duration_ms", 0.0)),
                    request=request,
                    response=response,
                )
            )

        return cls(
            version=version,
            recorder=recorder,
            recorded_at=recorded_at,
            interactions=interactions,
        )

    @classmethod
    def from_json(cls, json_str: str) -> CassetteData:
        """Loads and parses cassette data from a JSON string."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON: {exc}") from exc
        return cls.from_dict(data)

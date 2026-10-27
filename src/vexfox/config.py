"""Configuration options and recording modes for Vexfox."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class RecordMode(str, Enum):
    """Cassette recording mode.

    - `ONCE`: If cassette exists, replay it. If cassette does not exist, record real interactions.
    - `RECORD`: Always record interactions against the live network, updating/overwriting the cassette.
    - `REPLAY`: Strictly replay existing recordings. Fails if cassette is missing or if requests mismatch.
               Live network access is completely forbidden.
    - `NONE`: Passthrough mode. Makes live requests without recording or intercepting into a cassette.
    """

    ONCE = "once"
    RECORD = "record"
    REPLAY = "replay"
    NONE = "none"


DEFAULT_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "x-auth-token",
        "token",
        "bearer",
        "apikey",
        "secret",
        "x-secret",
        "client-secret",
    }
)

DEFAULT_SENSITIVE_QUERY_PARAMS = frozenset(
    {
        "api_key",
        "apikey",
        "key",
        "token",
        "access_token",
        "auth_token",
        "secret",
        "password",
        "client_secret",
        "signature",
    }
)

DEFAULT_SENSITIVE_BODY_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "credit_card",
        "cvv",
        "ssn",
    }
)

DEFAULT_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Bearer tokens: Bearer <token>
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    # Stripe / Payment provider keys: sk_live_..., sk_test_..., pk_live_..., rk_live_...
    re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{14,}\b", re.IGNORECASE),
    # OpenAI API secret keys: sk-... or sk-proj-...
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    # Common JWT tokens: eyJ...
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\b"),
    # AWS access key ID format: AKIA[0-9A-Z]{16}
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


@dataclass
class VexfoxConfig:
    """Configuration controlling Vexfox cassette behavior, matching, and sanitization."""

    mode: RecordMode = RecordMode.ONCE
    sensitive_headers: set[str] = field(default_factory=lambda: set(DEFAULT_SENSITIVE_HEADERS))
    sensitive_query_params: set[str] = field(
        default_factory=lambda: set(DEFAULT_SENSITIVE_QUERY_PARAMS)
    )
    sensitive_body_keys: set[str] = field(default_factory=lambda: set(DEFAULT_SENSITIVE_BODY_KEYS))
    secret_patterns: list[re.Pattern[str]] = field(
        default_factory=lambda: list(DEFAULT_SECRET_PATTERNS)
    )
    redaction_marker: str = "[REDACTED]"
    match_on: tuple[str, ...] = ("method", "url", "query", "body")
    match_headers: tuple[str, ...] = ()
    store_body: bool = True
    allow_playback_repeats: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.mode, str):
            self.mode = RecordMode(self.mode.lower())
        # Normalize header keys to lowercase for fast case-insensitive checks
        self.sensitive_headers = {h.lower() for h in self.sensitive_headers}
        self.sensitive_query_params = {q.lower() for q in self.sensitive_query_params}
        self.sensitive_body_keys = {b.lower() for b in self.sensitive_body_keys}
        self.match_headers = tuple(h.lower() for h in self.match_headers)

    def with_sensitive_headers(self, *headers: str) -> VexfoxConfig:
        """Returns a copy of config with extra sensitive header names added."""
        new_headers = self.sensitive_headers | {h.lower() for h in headers}
        return VexfoxConfig(
            mode=self.mode,
            sensitive_headers=new_headers,
            sensitive_query_params=set(self.sensitive_query_params),
            sensitive_body_keys=set(self.sensitive_body_keys),
            secret_patterns=list(self.secret_patterns),
            redaction_marker=self.redaction_marker,
            match_on=self.match_on,
            match_headers=self.match_headers,
            store_body=self.store_body,
            allow_playback_repeats=self.allow_playback_repeats,
        )

    def with_sensitive_body_keys(self, *keys: str) -> VexfoxConfig:
        """Returns a copy of config with extra sensitive body keys added."""
        new_keys = self.sensitive_body_keys | {k.lower() for k in keys}
        return VexfoxConfig(
            mode=self.mode,
            sensitive_headers=set(self.sensitive_headers),
            sensitive_query_params=set(self.sensitive_query_params),
            sensitive_body_keys=new_keys,
            secret_patterns=list(self.secret_patterns),
            redaction_marker=self.redaction_marker,
            match_on=self.match_on,
            match_headers=self.match_headers,
            store_body=self.store_body,
            allow_playback_repeats=self.allow_playback_repeats,
        )

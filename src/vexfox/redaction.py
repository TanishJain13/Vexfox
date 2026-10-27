"""Sanitization and redaction engine for Vexfox."""

from __future__ import annotations

import copy
import json
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

from vexfox.config import VexfoxConfig
from vexfox.models import RecordedRequest, RecordedResponse


class Redactor:
    """Sanitizes sensitive information from requests and responses before cassette persistence."""

    def __init__(self, config: VexfoxConfig) -> None:
        self.config = config

    def redact_headers(self, headers: dict[str, list[str]]) -> dict[str, list[str]]:
        """Redacts sensitive headers case-insensitively, replacing values with the redaction marker."""
        sanitized: dict[str, list[str]] = {}
        for key, values in headers.items():
            key_lower = key.lower()
            if key_lower in self.config.sensitive_headers:
                sanitized[key] = [self.config.redaction_marker for _ in values]
            else:
                # Also check each value against regex secret patterns
                cleaned_values = [self._redact_string_patterns(val) for val in values]
                sanitized[key] = cleaned_values
        return sanitized

    def redact_url_and_query(
        self, url: str, query: dict[str, list[str]]
    ) -> tuple[str, dict[str, list[str]]]:
        """Redacts sensitive userinfo and query parameters from both query dictionary and URL string."""
        # 1. Redact query dictionary
        sanitized_query: dict[str, list[str]] = {}
        for key, values in query.items():
            key_lower = key.lower()
            if key_lower in self.config.sensitive_query_params:
                sanitized_query[key] = [self.config.redaction_marker for _ in values]
            else:
                sanitized_query[key] = [self._redact_string_patterns(val) for val in values]

        # 2. Redact userinfo (password/token in netloc) and query components inside raw URL
        parsed = urlparse(url)
        netloc = parsed.netloc
        if "@" in netloc:
            userinfo, _, hostpart = netloc.partition("@")
            if ":" in userinfo:
                user, _, _ = userinfo.partition(":")
                sanitized_userinfo = f"{user}:{self.config.redaction_marker}"
            else:
                sanitized_userinfo = self.config.redaction_marker
            netloc = f"{sanitized_userinfo}@{hostpart}"

        sanitized_path = self._redact_string_patterns(parsed.path)

        if parsed.query:
            query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
            sanitized_pairs: list[tuple[str, str]] = []
            for k, v in query_pairs:
                if k.lower() in self.config.sensitive_query_params:
                    sanitized_pairs.append((k, self.config.redaction_marker))
                else:
                    sanitized_pairs.append((k, self._redact_string_patterns(v)))
            sanitized_query_string = urlencode(sanitized_pairs)
        else:
            sanitized_query_string = ""

        sanitized_url = urlunparse(
            (
                parsed.scheme,
                netloc,
                sanitized_path,
                parsed.params,
                sanitized_query_string,
                parsed.fragment,
            )
        )

        return sanitized_url, sanitized_query

    def redact_url(self, url: str) -> str:
        """Sanitizes a URL string directly, removing embedded credentials and sensitive query params."""
        parsed = urlparse(url)
        query_dict = parse_qs(parsed.query, keep_blank_values=True)
        sanitized_url, _ = self.redact_url_and_query(url, query_dict)
        return sanitized_url

    def redact_json_value(self, value: Any) -> Any:
        """Recursively traverses a JSON structure and redacts sensitive keys and regex patterns."""
        if isinstance(value, dict):
            new_dict: dict[str, Any] = {}
            for k, v in value.items():
                if str(k).lower() in self.config.sensitive_body_keys:
                    new_dict[k] = self.config.redaction_marker
                else:
                    new_dict[k] = self.redact_json_value(v)
            return new_dict
        elif isinstance(value, list):
            return [self.redact_json_value(item) for item in value]
        elif isinstance(value, str):
            return self._redact_string_patterns(value)
        return value

    def redact_body(self, body: str | None, is_binary: bool) -> str | None:
        """Redacts sensitive fields in the body text or JSON structure."""
        if body is None or is_binary or not body.strip():
            return body

        # Try to parse as JSON first
        try:
            parsed = json.loads(body)
            sanitized_obj = self.redact_json_value(parsed)
            return json.dumps(sanitized_obj)
        except (json.JSONDecodeError, TypeError):
            # Not JSON, redact via regex patterns on plain text
            return self._redact_string_patterns(body)

    def _redact_string_patterns(self, text: str) -> str:
        """Applies configured secret regex patterns against a text string."""
        if not text:
            return text
        result = text
        for pattern in self.config.secret_patterns:
            result = pattern.sub(self.config.redaction_marker, result)
        return result

    def sanitize_request(self, request: RecordedRequest) -> RecordedRequest:
        """Produces a new sanitized RecordedRequest with all sensitive data scrubbed."""
        sanitized = copy.deepcopy(request)

        # Redact headers
        sanitized.headers = self.redact_headers(sanitized.headers)

        # Redact URL and query parameters
        sanitized.url, sanitized.query = self.redact_url_and_query(sanitized.url, sanitized.query)

        # Redact request body
        if not self.config.store_body:
            sanitized.body = None
            sanitized.is_binary = False
        else:
            sanitized.body = self.redact_body(sanitized.body, sanitized.is_binary)

        return sanitized

    def sanitize_response(self, response: RecordedResponse) -> RecordedResponse:
        """Produces a new sanitized RecordedResponse with sensitive headers and bodies scrubbed."""
        sanitized = copy.deepcopy(response)

        # Redact headers (e.g. Set-Cookie, secret headers)
        sanitized.headers = self.redact_headers(sanitized.headers)

        # Redact response body if it contains sensitive JSON or tokens
        sanitized.body = self.redact_body(sanitized.body, sanitized.is_binary)

        return sanitized

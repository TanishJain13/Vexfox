"""Deterministic request matching engine for Vexfox."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from vexfox.config import VexfoxConfig
from vexfox.models import RecordedRequest


class MatchResult:
    """Outcome of comparing an incoming request against a recorded interaction."""

    def __init__(self, is_match: bool, reasons: list[str] | None = None) -> None:
        self.is_match = is_match
        self.reasons = reasons or []

    def __bool__(self) -> bool:
        return self.is_match


class RequestMatcher:
    """Matches an incoming request against recorded cassette requests according to configured rules."""

    def __init__(self, config: VexfoxConfig) -> None:
        self.config = config

    def match(self, incoming: RecordedRequest, recorded: RecordedRequest) -> MatchResult:
        """Compares an incoming request against a recorded interaction."""
        reasons: list[str] = []

        # 1. Method matching
        if "method" in self.config.match_on:
            if incoming.method.upper() != recorded.method.upper():
                reasons.append(
                    f"Method mismatch: expected '{recorded.method.upper()}', got '{incoming.method.upper()}'"
                )

        # 2. URL Path and Scheme/Host matching
        if "url" in self.config.match_on:
            parsed_in = urlparse(incoming.url)
            parsed_rec = urlparse(recorded.url)

            # Sanitize netloc for safe comparison without leaking passwords in mismatch error
            sanitized_netloc_in = self._sanitize_netloc(parsed_in.netloc.lower())
            sanitized_netloc_rec = self._sanitize_netloc(parsed_rec.netloc.lower())

            # Compare scheme + netloc + path
            base_in = (
                parsed_in.scheme.lower(),
                sanitized_netloc_in,
                parsed_in.path.rstrip("/"),
            )
            base_rec = (
                parsed_rec.scheme.lower(),
                sanitized_netloc_rec,
                parsed_rec.path.rstrip("/"),
            )

            if base_in != base_rec:
                reasons.append(
                    f"URL mismatch: expected '{parsed_rec.scheme}://{sanitized_netloc_rec}{parsed_rec.path}', "
                    f"got '{parsed_in.scheme}://{sanitized_netloc_in}{parsed_in.path}'"
                )

        # 3. Query parameters matching
        if "query" in self.config.match_on:
            parsed_in = urlparse(incoming.url)
            parsed_rec = urlparse(recorded.url)

            in_query = parse_qs(parsed_in.query, keep_blank_values=True)
            rec_query = parse_qs(parsed_rec.query, keep_blank_values=True)

            # Filter out sensitive keys from query comparison if they were redacted in the recorded cassette
            # or compare normalized values
            query_mismatch = self._compare_query_params(in_query, rec_query)
            if query_mismatch:
                reasons.append(query_mismatch)

        # 4. Request body matching
        if "body" in self.config.match_on:
            body_mismatch = self._compare_bodies(incoming, recorded)
            if body_mismatch:
                reasons.append(body_mismatch)

        # 5. Selected headers matching
        if self.config.match_headers:
            header_mismatch = self._compare_headers(incoming, recorded)
            if header_mismatch:
                reasons.append(header_mismatch)

        return MatchResult(is_match=len(reasons) == 0, reasons=reasons)

    def _compare_query_params(
        self,
        in_query: dict[str, list[str]],
        rec_query: dict[str, list[str]],
    ) -> str | None:
        """Compares two parsed query dictionaries order-insensitively."""
        # Normalize keys to lowercase for comparison
        in_norm = {k.lower(): sorted(v) for k, v in in_query.items()}
        rec_norm = {k.lower(): sorted(v) for k, v in rec_query.items()}

        # For sensitive query params that were redacted in the cassette, treat any non-empty value in the incoming request as matching the redaction marker
        for sensitive_key in self.config.sensitive_query_params:
            if sensitive_key in rec_norm and rec_norm[sensitive_key] == [
                self.config.redaction_marker
            ]:
                if sensitive_key in in_norm and in_norm[sensitive_key]:
                    # Accept match for the redacted query param
                    in_norm[sensitive_key] = [self.config.redaction_marker]

        if in_norm != rec_norm:
            in_keys = set(in_norm.keys())
            rec_keys = set(rec_norm.keys())

            missing_keys = rec_keys - in_keys
            extra_keys = in_keys - rec_keys

            details: list[str] = []
            if missing_keys:
                details.append(f"missing parameters {sorted(missing_keys)}")
            if extra_keys:
                details.append(f"unexpected parameters {sorted(extra_keys)}")

            common_keys = in_keys & rec_keys
            for key in common_keys:
                if in_norm[key] != rec_norm[key]:
                    # Mask value if sensitive
                    if key in self.config.sensitive_query_params:
                        details.append(f"parameter '{key}' value mismatch")
                    else:
                        details.append(
                            f"parameter '{key}' expected {rec_norm[key]}, got {in_norm[key]}"
                        )

            return f"Query parameter mismatch: {', '.join(details)}"

        return None

    def _compare_bodies(self, incoming: RecordedRequest, recorded: RecordedRequest) -> str | None:
        """Compares request bodies, handling JSON structural comparison and text comparison."""
        # Both empty
        if not incoming.body and not recorded.body:
            return None

        # One empty, one present
        if bool(incoming.body) != bool(recorded.body):
            return (
                f"Body presence mismatch: recorded interaction has "
                f"{'body' if recorded.body else 'no body'}, "
                f"incoming request has {'body' if incoming.body else 'no body'}"
            )

        assert incoming.body is not None
        assert recorded.body is not None

        # If both are binary
        if incoming.is_binary or recorded.is_binary:
            if incoming.body != recorded.body:
                return "Binary body mismatch: payload bytes do not match recorded payload"
            return None

        # Try JSON comparison
        in_is_json = False
        rec_is_json = False
        in_json = None
        rec_json = None

        try:
            in_json = json.loads(incoming.body)
            in_is_json = True
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            rec_json = json.loads(recorded.body)
            rec_is_json = True
        except (json.JSONDecodeError, TypeError):
            pass

        if in_is_json and rec_is_json:
            # Mask sensitive keys in incoming json if recorded json had them redacted
            in_json_masked = self._mask_json_for_matching(in_json, rec_json)
            if in_json_masked != rec_json:
                return self._json_diff_summary(in_json_masked, rec_json)
            return None

        # Text comparison (trim trailing whitespace)
        if incoming.body.strip() != recorded.body.strip():
            return "Request body text mismatch: content does not match recorded body"

        return None

    def _mask_json_for_matching(self, in_val: Any, rec_val: Any) -> Any:
        """Masks incoming json keys with the redaction marker if the recorded json has them redacted."""
        if isinstance(in_val, dict) and isinstance(rec_val, dict):
            res: dict[str, Any] = {}
            for k, v in in_val.items():
                if (
                    str(k).lower() in self.config.sensitive_body_keys
                    and rec_val.get(k) == self.config.redaction_marker
                ):
                    res[k] = self.config.redaction_marker
                else:
                    res[k] = self._mask_json_for_matching(v, rec_val.get(k))
            return res
        elif isinstance(in_val, list) and isinstance(rec_val, list):
            res_list: list[Any] = []
            for i, item in enumerate(in_val):
                rec_item = rec_val[i] if i < len(rec_val) else None
                res_list.append(self._mask_json_for_matching(item, rec_item))
            return res_list
        return in_val

    def _json_diff_summary(self, in_val: Any, rec_val: Any) -> str:
        """Produces a short, safe diff summary for JSON mismatches without exposing secrets."""
        if isinstance(in_val, dict) and isinstance(rec_val, dict):
            in_keys = set(in_val.keys())
            rec_keys = set(rec_val.keys())
            if in_keys != rec_keys:
                missing = rec_keys - in_keys
                extra = in_keys - rec_keys
                parts: list[str] = []
                if missing:
                    parts.append(f"missing keys {sorted(missing)}")
                if extra:
                    parts.append(f"extra keys {sorted(extra)}")
                return f"JSON body mismatch: {', '.join(parts)}"
            for k in sorted(in_keys):
                if in_val[k] != rec_val[k]:
                    if str(k).lower() in self.config.sensitive_body_keys:
                        return f"JSON body mismatch at key '{k}'"
                    return f"JSON body mismatch at key '{k}': expected '{rec_val[k]}', got '{in_val[k]}'"
        return "JSON body content mismatch"

    def _sanitize_netloc(self, netloc: str) -> str:
        """Sanitizes netloc by masking credentials embedded in URLs."""
        if "@" in netloc:
            userinfo, _, hostpart = netloc.partition("@")
            if ":" in userinfo:
                user, _, _ = userinfo.partition(":")
                return f"{user}:{self.config.redaction_marker}@{hostpart}"
            return f"{self.config.redaction_marker}@{hostpart}"
        return netloc

    def _compare_headers(self, incoming: RecordedRequest, recorded: RecordedRequest) -> str | None:
        """Compares only configured match_headers safely without exposing credentials."""
        in_norm = {k.lower(): v for k, v in incoming.headers.items()}
        rec_norm = {k.lower(): v for k, v in recorded.headers.items()}

        for header_name in self.config.match_headers:
            header_name = header_name.lower()
            in_val = in_norm.get(header_name, [])
            rec_val = rec_norm.get(header_name, [])

            # If header is sensitive and was redacted to redaction_marker in cassette,
            # any non-empty value in the incoming request is considered matching
            if header_name in self.config.sensitive_headers and rec_val == [
                self.config.redaction_marker
            ]:
                if in_val and len(in_val) > 0:
                    continue

            if in_val != rec_val:
                if header_name in self.config.sensitive_headers:
                    return f"Header '{header_name}' mismatch: value differed from recorded fixture"
                return f"Header '{header_name}' mismatch: expected {rec_val}, got {in_val}"
        return None

"""Exceptions for the Vexfox library."""

from __future__ import annotations


class VexfoxError(Exception):
    """Base exception for all Vexfox errors."""


class CassetteNotFoundError(VexfoxError):
    """Raised in replay mode when the requested cassette file does not exist."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"Cassette file not found at '{path}'. In replay mode, existing cassette files are required."
        )
        self.path = path


class CannotOverwriteCassetteError(VexfoxError):
    """Raised when an operation would overwrite an existing cassette without explicit permission."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"Cannot overwrite existing cassette file at '{path}' without appropriate record mode."
        )
        self.path = path


class RequestMismatchError(VexfoxError):
    """Raised in replay mode when an incoming request fails to match recorded cassette interactions."""

    def __init__(
        self,
        method: str,
        url: str,
        reasons: list[str] | None = None,
        available_interactions: list[str] | None = None,
    ) -> None:
        message_parts = [f"No matching recorded interaction found for request: {method} {url}"]
        if reasons:
            message_parts.append("\nMismatch diagnostics:")
            for reason in reasons:
                message_parts.append(f"  - {reason}")
        if available_interactions:
            message_parts.append("\nRecorded interactions in cassette:")
            for item in available_interactions:
                message_parts.append(f"  * {item}")
        super().__init__("\n".join(message_parts))
        self.method = method
        self.url = url
        self.reasons = reasons or []
        self.available_interactions = available_interactions or []


class ExhaustedCassetteError(VexfoxError):
    """Raised when all recorded interactions in a cassette have been consumed and another request is made."""

    def __init__(self, cassette_path: str, total_interactions: int) -> None:
        super().__init__(
            f"All {total_interactions} interaction(s) in cassette '{cassette_path}' have been consumed. "
            "No remaining interactions available to replay."
        )
        self.cassette_path = cassette_path
        self.total_interactions = total_interactions


class NetworkForbiddenInReplayError(VexfoxError):
    """Raised when an HTTP request attempts to access the live network while in replay mode."""

    def __init__(self, method: str, url: str) -> None:
        super().__init__(
            f"Live network request forbidden in replay mode for: {method} {url}. "
            "Vexfox guarantees zero live network calls during replay."
        )
        self.method = method
        self.url = url


class InvalidCassetteError(VexfoxError):
    """Raised when a cassette file is corrupted, malformed, or has an incompatible schema version."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Invalid cassette file '{path}': {reason}")
        self.path = path
        self.reason = reason


class NestedCassetteError(VexfoxError):
    """Raised when attempting to enter a cassette context while another cassette context is already active."""

    def __init__(self, active_path: str, attempted_path: str) -> None:
        super().__init__(
            f"Cannot enter cassette context '{attempted_path}' while cassette '{active_path}' is already active. "
            "Nested cassette contexts are not supported."
        )
        self.active_path = active_path
        self.attempted_path = attempted_path

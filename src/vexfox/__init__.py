"""Vexfox: Deterministic HTTP interaction recording, sanitization, and replay for Python tests.

Capture reality. Replay with confidence.
"""

from __future__ import annotations

from vexfox.cassette import Cassette
from vexfox.config import RecordMode, VexfoxConfig
from vexfox.exceptions import (
    CannotOverwriteCassetteError,
    CassetteNotFoundError,
    ExhaustedCassetteError,
    InvalidCassetteError,
    NestedCassetteError,
    NetworkForbiddenInReplayError,
    RequestMismatchError,
    VexfoxError,
)
from vexfox.models import (
    CassetteData,
    Interaction,
    RecordedRequest,
    RecordedResponse,
)
from vexfox.transport import (
    VexfoxAsyncTransport,
    VexfoxSyncTransport,
    use_cassette,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "use_cassette",
    "Cassette",
    "VexfoxConfig",
    "RecordMode",
    "VexfoxSyncTransport",
    "VexfoxAsyncTransport",
    "RecordedRequest",
    "RecordedResponse",
    "Interaction",
    "CassetteData",
    "VexfoxError",
    "CassetteNotFoundError",
    "CannotOverwriteCassetteError",
    "RequestMismatchError",
    "ExhaustedCassetteError",
    "NetworkForbiddenInReplayError",
    "InvalidCassetteError",
    "NestedCassetteError",
]

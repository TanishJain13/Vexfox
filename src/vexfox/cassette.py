"""Cassette management, persistence, and replay coordination."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from vexfox.config import RecordMode, VexfoxConfig
from vexfox.exceptions import (
    CassetteNotFoundError,
    ExhaustedCassetteError,
    InvalidCassetteError,
    RequestMismatchError,
)
from vexfox.matching import RequestMatcher
from vexfox.models import (
    CassetteData,
    Interaction,
    RecordedRequest,
    RecordedResponse,
)
from vexfox.redaction import Redactor


class Cassette:
    """Represents an active cassette fixture backed by a versioned JSON file."""

    def __init__(
        self,
        path: str | Path,
        config: VexfoxConfig | None = None,
    ) -> None:
        self.path = Path(path).resolve()
        self.config = config or VexfoxConfig()
        self.redactor = Redactor(self.config)
        self.matcher = RequestMatcher(self.config)
        self.data = CassetteData()
        self.is_dirty = False
        self.consumed_indices: set[int] = set()

        self._load()

    @property
    def file_exists(self) -> bool:
        """Returns True if the cassette file already exists on disk."""
        return self.path.is_file()

    @property
    def total_interactions(self) -> int:
        """Returns the total number of interactions in the cassette."""
        return len(self.data.interactions)

    @property
    def remaining_interactions(self) -> int:
        """Returns the number of unconsumed interactions."""
        return len(self.data.interactions) - len(self.consumed_indices)

    def _load(self) -> None:
        """Loads and parses cassette file if it exists, verifying schema."""
        if not self.file_exists:
            if self.config.mode == RecordMode.REPLAY:
                raise CassetteNotFoundError(str(self.path))
            return

        try:
            content = self.path.read_text(encoding="utf-8")
            self.data = CassetteData.from_json(content)
        except Exception as exc:
            raise InvalidCassetteError(str(self.path), str(exc)) from exc

    def record_interaction(
        self,
        request: RecordedRequest,
        response: RecordedResponse,
        duration_ms: float = 0.0,
    ) -> Interaction:
        """Sanitizes and stores a new interaction into the cassette."""
        sanitized_request = self.redactor.sanitize_request(request)
        sanitized_response = self.redactor.sanitize_response(response)

        interaction_id = str(len(self.data.interactions) + 1)
        interaction = Interaction(
            id=interaction_id,
            recorded_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=round(duration_ms, 2),
            request=sanitized_request,
            response=sanitized_response,
        )

        self.data.interactions.append(interaction)
        self.is_dirty = True
        return interaction

    def find_match(self, incoming: RecordedRequest) -> RecordedResponse:
        """Finds a matching recorded response for the incoming request, following consumption rules."""
        sanitized_incoming_url = self.redactor.redact_url(incoming.url)

        if not self.data.interactions:
            raise RequestMismatchError(
                method=incoming.method,
                url=sanitized_incoming_url,
                reasons=["Cassette contains no recorded interactions."],
            )

        # In strict non-repeating mode, check if all interactions have been consumed
        if not self.config.allow_playback_repeats and len(self.consumed_indices) >= len(
            self.data.interactions
        ):
            raise ExhaustedCassetteError(
                cassette_path=str(self.path),
                total_interactions=len(self.data.interactions),
            )

        # 1. Try sequential match (first unconsumed index)
        candidate_indices: list[int] = []
        for idx in range(len(self.data.interactions)):
            if self.config.allow_playback_repeats or idx not in self.consumed_indices:
                candidate_indices.append(idx)

        all_mismatch_reasons: list[str] = []
        available_summaries: list[str] = []

        for idx in candidate_indices:
            interaction = self.data.interactions[idx]
            summary = f"[{interaction.id}] {interaction.request.method} {interaction.request.url}"
            available_summaries.append(summary)

            match_res = self.matcher.match(incoming, interaction.request)
            if match_res.is_match:
                if not self.config.allow_playback_repeats:
                    self.consumed_indices.add(idx)
                return interaction.response
            else:
                for reason in match_res.reasons:
                    if reason not in all_mismatch_reasons:
                        all_mismatch_reasons.append(f"Interaction #{interaction.id}: {reason}")

        # If we got here, no candidates matched
        raise RequestMismatchError(
            method=incoming.method,
            url=sanitized_incoming_url,
            reasons=all_mismatch_reasons[:5],  # Top actionable reasons
            available_interactions=available_summaries[:5],
        )

    def save(self) -> None:
        """Safely and atomically writes the cassette data to disk if modified."""
        if not self.is_dirty:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        json_output = self.data.to_json(indent=2)

        # Atomic file write using a temporary file in the same directory
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.path.parent),
            delete=False,
            prefix=f".{self.path.stem}_",
            suffix=".tmp",
        )
        try:
            temp_file.write(json_output)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()

            # Atomic replace
            os.replace(temp_file.name, str(self.path))
            self.is_dirty = False
        except Exception:
            if os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except OSError:
                    pass
            raise

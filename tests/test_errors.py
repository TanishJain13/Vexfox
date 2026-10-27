"""Tests verifying error handling and edge cases in Vexfox."""

from __future__ import annotations

from pathlib import Path

import pytest

import vexfox
from vexfox.exceptions import (
    InvalidCassetteError,
    NestedCassetteError,
)


def test_nested_cassettes_raise_error(tmp_path: Path) -> None:
    """Verifies that nested cassette contexts are explicitly rejected with NestedCassetteError."""
    cassette_a = tmp_path / "a.json"
    cassette_b = tmp_path / "b.json"

    with vexfox.use_cassette(cassette_a):
        with pytest.raises(NestedCassetteError) as exc_info:
            with vexfox.use_cassette(cassette_b):
                pass

    err_msg = str(exc_info.value)
    assert "Nested cassette contexts are not supported" in err_msg
    assert str(cassette_a) in err_msg
    assert str(cassette_b) in err_msg


def test_invalid_cassette_schema_raises_error(tmp_path: Path) -> None:
    """Verifies that corrupted cassette files raise InvalidCassetteError."""
    corrupted_file = tmp_path / "bad.json"
    corrupted_file.write_text('{"version": 999, "interactions": []}', encoding="utf-8")

    with pytest.raises(InvalidCassetteError) as exc_info:
        with vexfox.use_cassette(corrupted_file, mode=vexfox.RecordMode.REPLAY):
            pass

    assert "Unsupported cassette schema version: 999" in str(exc_info.value)


def test_malformed_json_raises_invalid_cassette_error(tmp_path: Path) -> None:
    """Verifies that unparseable JSON raises InvalidCassetteError."""
    malformed_file = tmp_path / "malformed.json"
    malformed_file.write_text("{ this is not json }", encoding="utf-8")

    with pytest.raises(InvalidCassetteError) as exc_info:
        with vexfox.use_cassette(malformed_file, mode=vexfox.RecordMode.REPLAY):
            pass

    assert "Malformed JSON" in str(exc_info.value)

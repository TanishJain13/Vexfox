"""Tests verifying Vexfox Typer CLI commands and exit codes."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vexfox.cli import app
from vexfox.models import CassetteData, Interaction, RecordedRequest, RecordedResponse

runner = CliRunner()


def test_cli_help() -> None:
    """Verifies that --help prints available commands and exits with code 0."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout
    assert "inspect" in result.stdout
    assert "validate" in result.stdout
    assert "list" in result.stdout


def test_cli_version() -> None:
    """Verifies that --version displays version 0.1.0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_doctor() -> None:
    """Verifies that doctor checks runtime and diagnostics."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.stdout
    assert "HTTPX" in result.stdout
    assert "Cassette Schema" in result.stdout


def test_cli_list_and_inspect_and_validate(tmp_path: Path) -> None:
    """Verifies list, inspect, and validate commands with real cassette fixtures."""
    cassette_path = tmp_path / "sample.json"

    data = CassetteData(
        interactions=[
            Interaction(
                id="1",
                recorded_at="2026-10-27T18:00:00Z",
                duration_ms=45.2,
                request=RecordedRequest(
                    method="GET",
                    url="https://api.example.com/v1/users",
                    headers={"authorization": ["[REDACTED]"]},
                ),
                response=RecordedResponse(
                    status_code=200,
                    body='{"users": []}',
                ),
            )
        ]
    )
    cassette_path.write_text(data.to_json(), encoding="utf-8")

    # 1. Test list
    list_res = runner.invoke(app, ["list", str(tmp_path)])
    assert list_res.exit_code == 0
    assert "sample.json" in list_res.stdout
    assert "1" in list_res.stdout

    # 2. Test inspect
    inspect_res = runner.invoke(app, ["inspect", str(cassette_path)])
    assert inspect_res.exit_code == 0
    assert "GET" in inspect_res.stdout
    assert "https://api.example.com" in inspect_res.stdout
    assert "200" in inspect_res.stdout
    assert "45.2ms" in inspect_res.stdout

    # 3. Test validate on valid file
    validate_res = runner.invoke(app, ["validate", str(cassette_path)])
    assert validate_res.exit_code == 0
    assert "Valid cassette" in validate_res.stdout


def test_cli_validate_corrupt_file(tmp_path: Path) -> None:
    """Verifies that validate fails on corrupt or invalid cassette schema."""
    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{ not json", encoding="utf-8")

    res = runner.invoke(app, ["validate", str(corrupt_path)])
    assert res.exit_code != 0
    assert "FAILED" in res.stdout or "FAILED" in res.stderr


def test_cli_main_module() -> None:
    """Verifies that running vexfox as a module (python -m vexfox) works."""
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, "-m", "vexfox", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "0.1.0" in res.stdout

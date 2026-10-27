"""Command-line interface for Vexfox."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vexfox.models import SCHEMA_VERSION, CassetteData

__version__ = "0.1.0"

app = typer.Typer(
    name="vexfox",
    help="Capture reality. Replay with confidence. Vexfox HTTP testing & cassette toolkit.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold #F26A2E]Vexfox[/] version [bold white]{__version__}[/]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show Vexfox version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Vexfox developer toolkit."""


@app.command()
def doctor() -> None:
    """Check Python environment, dependencies, and filesystem permissions."""
    table = Table(title="Vexfox Diagnostics", show_header=True, header_style="bold #F26A2E")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        table.add_row("Python", "[green]OK[/green]", f"Python {py_ver}")
    else:
        table.add_row("Python", "[red]FAIL[/red]", f"Python {py_ver} (requires >= 3.11)")

    # 2. HTTPX version
    httpx_ver = getattr(httpx, "__version__", "unknown")
    table.add_row("HTTPX", "[green]OK[/green]", f"httpx {httpx_ver}")

    # 3. Cassette Schema Version
    table.add_row("Cassette Schema", "[green]OK[/green]", f"Schema v{SCHEMA_VERSION}")

    # 4. Current directory writable
    try:
        test_file = Path(".vexfox_probe.tmp")
        test_file.write_text("probe", encoding="utf-8")
        test_file.unlink()
        table.add_row("Disk Permissions", "[green]OK[/green]", "Current directory is writable")
    except Exception as exc:
        table.add_row("Disk Permissions", "[red]FAIL[/red]", f"Cannot write to disk: {exc}")

    console.print(table)
    console.print("\n[bold green]Ready to capture and replay HTTP interactions.[/bold green]")


@app.command("list")
def list_cassettes(
    directory: Path = typer.Argument(
        Path("."),
        help="Directory to search for cassette files.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        "-r/-R",
        help="Recursively scan subdirectories for cassettes.",
    ),
) -> None:
    """List recorded cassette files in a directory."""
    pattern = "**/*.json" if recursive else "*.json"
    json_files = sorted(directory.glob(pattern))

    valid_cassettes: list[tuple[Path, CassetteData]] = []
    for f in json_files:
        try:
            data = CassetteData.from_json(f.read_text(encoding="utf-8"))
            valid_cassettes.append((f, data))
        except Exception:
            continue

    if not valid_cassettes:
        console.print(f"[dim]No valid Vexfox cassettes found in {directory.resolve()}[/dim]")
        return

    table = Table(
        title=f"Vexfox Cassettes ({len(valid_cassettes)} found)",
        show_header=True,
        header_style="bold #F26A2E",
    )
    table.add_column("Cassette Path", style="bold white")
    table.add_column("Interactions", justify="right", style="cyan")
    table.add_column("File Size", justify="right")
    table.add_column("Recorded At", style="dim")

    for path, data in valid_cassettes:
        size_kb = f"{path.stat().st_size / 1024:.1f} KB"
        recorded_at = data.recorded_at[:19].replace("T", " ") if data.recorded_at else "unknown"
        try:
            rel_path = path.relative_to(directory)
        except ValueError:
            rel_path = path.name
        table.add_row(str(rel_path), str(len(data.interactions)), size_kb, recorded_at)

    console.print(table)


@app.command()
def inspect(
    cassette_path: Path = typer.Argument(
        ...,
        help="Path to the cassette JSON file to inspect.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Display a readable summary of interactions in a cassette without exposing secrets."""
    try:
        content = cassette_path.read_text(encoding="utf-8")
        data = CassetteData.from_json(content)
    except Exception as exc:
        err_console.print(f"[bold red]Error reading cassette:[/] {exc}")
        raise typer.Exit(code=1) from None

    console.print(
        Panel(
            f"[bold #F26A2E]Cassette:[/] [white]{cassette_path}[/]\n"
            f"[bold cyan]Recorder:[/] {data.recorder}  |  "
            f"[bold cyan]Schema:[/] v{data.version}  |  "
            f"[bold cyan]Recorded:[/] {data.recorded_at}",
            title="[bold #F26A2E]Vexfox Cassette Inspector[/]",
            border_style="#F26A2E",
        )
    )

    if not data.interactions:
        console.print("[dim]No interactions recorded in this cassette.[/dim]")
        return

    table = Table(show_header=True, header_style="bold #F26A2E")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Method", style="bold green")
    table.add_column("URL", style="white", overflow="fold")
    table.add_column("Status", justify="center")
    table.add_column("Body Type")
    table.add_column("Duration", justify="right", style="dim")

    for interaction in data.interactions:
        status = interaction.response.status_code
        status_style = (
            "bold green"
            if 200 <= status < 300
            else ("bold yellow" if 300 <= status < 400 else "bold red")
        )

        body_info = "empty"
        if interaction.response.body:
            body_info = (
                "binary (b64)"
                if interaction.response.is_binary
                else f"text ({len(interaction.response.body)} chars)"
            )

        table.add_row(
            interaction.id,
            interaction.request.method,
            interaction.request.url,
            f"[{status_style}]{status}[/{status_style}]",
            body_info,
            f"{interaction.duration_ms:.1f}ms",
        )

    console.print(table)


@app.command()
def validate(
    cassette_path: Path = typer.Argument(
        ...,
        help="Path to the cassette JSON file to validate.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Validate cassette schema and check for corruption or missing fields."""
    try:
        content = cassette_path.read_text(encoding="utf-8")
        data = CassetteData.from_json(content)
    except Exception as exc:
        err_console.print(f"[bold red]Validation FAILED:[/] {exc}")
        raise typer.Exit(code=1) from None

    errors: list[str] = []
    if data.version != SCHEMA_VERSION:
        errors.append(f"Invalid schema version {data.version}; expected {SCHEMA_VERSION}.")

    for idx, interaction in enumerate(data.interactions):
        if not interaction.request.url:
            errors.append(f"Interaction #{idx + 1} has an empty request URL.")
        if not interaction.request.method:
            errors.append(f"Interaction #{idx + 1} has an empty request method.")
        if interaction.response.status_code < 100 or interaction.response.status_code > 599:
            errors.append(
                f"Interaction #{idx + 1} has invalid status code {interaction.response.status_code}."
            )

    if errors:
        err_console.print(f"[bold red]Validation FAILED for {cassette_path}:[/]")
        for err in errors:
            err_console.print(f"  - {err}")
        raise typer.Exit(code=1)

    console.print(
        f"[bold green]✓ Valid cassette:[/] [white]{cassette_path}[/] "
        f"({len(data.interactions)} interaction{'s' if len(data.interactions) != 1 else ''}, schema v{data.version})"
    )


if __name__ == "__main__":
    app()

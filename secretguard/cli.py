# secretguard/cli.py

import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from .detector import Detector, Finding

app = typer.Typer(
    name="secretguard",
    help="SecretGuard — detect exposed secrets in code",
    add_completion=False,
)

# Force UTF-8 so Rich output is safe inside pre-commit's subprocess on Windows
console = Console(highlight=False)

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SEVERITY_COLOR = {"critical": "red", "high": "bright_red", "medium": "yellow", "low": "white"}


def _print_findings(findings: list[Finding]) -> None:
    """Pretty-print a sorted list of findings."""
    findings.sort(key=lambda f: -SEVERITY_ORDER.get(f.severity.lower(), 0))
    for f in findings:
        color = SEVERITY_COLOR.get(f.severity.lower(), "white")
        console.print(f"[{color} bold]{f.severity.upper()}[/{color} bold] {f.description}")
        console.print(f"   File : {f.file_path}:{f.line}")
        console.print(f"   Match: [dim]{f.secret[:120]}[/dim]")
        console.print(f"   Line : {f.line_content.strip()[:120]}{'...' if len(f.line_content) > 120 else ''}")
        console.print("─" * 70)


# ── Manual scan command ────────────────────────────────────────────────────────

@app.command()
def scan(
    path: str = typer.Argument(..., help="File or directory to scan"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all matches"),
):
    """Scan a file or directory for exposed secrets."""
    detector = Detector()
    target = Path(path)
    findings: list[Finding] = []

    if target.is_file():
        findings.extend(detector.scan_file(str(target)))
    elif target.is_dir():
        for file in target.rglob("*"):
            if file.is_file():
                findings.extend(detector.scan_file(str(file)))
    else:
        console.print(f"[red]Error:[/red] Path not found: {path}")
        raise typer.Exit(code=1)

    if not findings:
        console.print("[green]OK  No secrets found[/green]")
        return

    console.print(f"[bold red]Found {len(findings)} potential secret(s):[/bold red]\n")
    _print_findings(findings)
    raise typer.Exit(code=1)


# ── Pre-commit hook entry point ────────────────────────────────────────────────
# pre-commit calls:  secretguard-hook <file1> <file2> ...

@app.command(name="hook")
def hook(
    filenames: List[str] = typer.Argument(..., help="Staged files passed by pre-commit"),
):
    """
    Pre-commit hook entry point.

    pre-commit passes all staged filenames as positional arguments.
    Exits with code 1 (blocks commit) if any secrets are found.
    """
    detector = Detector()
    all_findings: list[Finding] = []

    for filename in filenames:
        path = Path(filename)
        if path.is_file():
            found = detector.scan_file(str(path))
            all_findings.extend(found)

    if not all_findings:
        console.print("[green]OK  SecretGuard: no secrets detected[/green]")
        return  # exit 0 -> commit proceeds

    console.print(f"[bold red]BLOCKED  SecretGuard: {len(all_findings)} secret(s) found — commit rejected[/bold red]\n")
    _print_findings(all_findings)
    raise typer.Exit(code=1)  # exit 1 -> commit is blocked


# ── Version ────────────────────────────────────────────────────────────────────

@app.command()
def version():
    """Show SecretGuard version."""
    console.print("SecretGuard v1.0")


if __name__ == "__main__":
    app()
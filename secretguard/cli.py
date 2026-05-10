# secretguard/cli.py

import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from .pipeline import TriFusionPipeline, PipelineResult
from .classifier import classifier_status
from .git_history_scanner import GitHistoryScanner, GitFinding, GIT_AVAILABLE

app = typer.Typer(
    name="secretguard",
    help="SecretGuard (TriFusion) — 4-layer hybrid secret detection pipeline",
    add_completion=False,
)

# Force UTF-8 so Rich output is safe inside pre-commit's subprocess on Windows
console = Console(highlight=False)

SEVERITY_COLOR = {
    "critical": "bold red",
    "high":     "bright_red",
    "medium":   "yellow",
    "low":      "dim white",
}


def _print_result(r: PipelineResult) -> None:
    """Pretty-print a single PipelineResult with score breakdown."""
    color = SEVERITY_COLOR.get(r.severity, "white")
    console.print(f"[{color}][{r.severity.upper()}][/{color}] {r.description}")
    console.print(f"   File  : {r.file_path}:{r.line}")
    console.print(f"   Match : [dim]{r.secret[:100]}[/dim]")
    console.print(f"   Score : [bold]{r.combined_score:.3f}[/bold]  (Tier {r.tier} regex | "
                  f"entropy {r.entropy_score:.2f} | "
                  f"classifier {r.classifier_score:.2f} | "
                  f"suppressor {r.suppressor_score:.2f})")
    if r.explanation:
        for line in r.explanation:
            console.print(f"      • {line}")
    console.print("-" * 72)


def _collect_results(
    pipeline: TriFusionPipeline,
    target: Path,
    threshold: float,
    enable_l2: bool,
    enable_l3: bool,
    enable_l4: bool,
) -> List[PipelineResult]:
    """Walk a file or directory and return all results above threshold."""
    results: List[PipelineResult] = []

    if target.is_file():
        raw = pipeline.scan_file(str(target))
        results.extend(r for r in raw if r.combined_score >= threshold)

    elif target.is_dir():
        for f in target.rglob("*"):
            if not f.is_file():
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            raw = pipeline.scan_code(
                content, str(f),
                enable_l2=enable_l2,
                enable_l3=enable_l3,
                enable_l4=enable_l4,
            )
            results.extend(r for r in raw if r.combined_score >= threshold)

    results.sort(key=lambda r: -r.combined_score)
    return results


# ── Manual scan command ────────────────────────────────────────────────────────

@app.command()
def scan(
    path: str = typer.Argument(..., help="File or directory to scan"),
    threshold: float = typer.Option(
        0.30, "--threshold", "-t",
        help="Minimum combined score to report (0.0–1.0)"
    ),
    no_l2: bool = typer.Option(False, "--no-l2", help="Ablation: disable entropy layer"),
    no_l3: bool = typer.Option(False, "--no-l3", help="Ablation: disable classifier layer"),
    no_l4: bool = typer.Option(False, "--no-l4", help="Ablation: disable FP suppressor layer"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show score breakdowns"),
):
    """
    Scan a file or directory for exposed secrets using the full TriFusion pipeline.

    Use --no-l2 / --no-l3 / --no-l4 to ablate individual layers for research experiments.
    """
    pipeline = TriFusionPipeline()
    target = Path(path)

    if not target.exists():
        console.print(f"[red]Error:[/red] Path not found: {path}")
        raise typer.Exit(code=1)

    enable_l2 = not no_l2
    enable_l3 = not no_l3
    enable_l4 = not no_l4

    # Show which layers are active
    active = []
    if enable_l2: active.append("Entropy(L2)")
    if enable_l3: active.append("Classifier(L3)")
    if enable_l4: active.append("Suppressor(L4)")
    layer_str = ", ".join(active) if active else "Regex only (L1)"
    console.print(f"[dim]TriFusion — Active layers: Regex(L1), {layer_str} | threshold={threshold}[/dim]\n")

    results = _collect_results(pipeline, target, threshold, enable_l2, enable_l3, enable_l4)

    if not results:
        console.print("[green]✓ No secrets detected[/green]")
        return

    console.print(f"[bold red]⚠ {len(results)} secret(s) detected:[/bold red]\n")

    for r in results:
        if verbose:
            _print_result(r)
        else:
            color = SEVERITY_COLOR.get(r.severity, "white")
            console.print(
                f"[{color}][{r.severity.upper()}][/{color}] "
                f"[bold]{r.combined_score:.3f}[/bold]  {r.description}"
            )
            console.print(f"   {r.file_path}:{r.line}  →  [dim]{r.secret[:80]}[/dim]")
            console.print("-" * 72)

    raise typer.Exit(code=1)


# ── Pre-commit hook entry point ────────────────────────────────────────────────
# pre-commit calls:  secretguard-hook <file1> <file2> ...

@app.command(name="hook")
def hook(
    filenames: List[str] = typer.Argument(..., help="Staged files passed by pre-commit"),
    threshold: float = typer.Option(0.30, "--threshold", "-t"),
):
    """
    Pre-commit hook entry point.

    pre-commit passes all staged filenames as positional arguments.
    Exits with code 1 (blocks commit) if any secrets are found.
    Uses the full TriFusion 4-layer pipeline.
    """
    pipeline = TriFusionPipeline()
    all_results: List[PipelineResult] = []

    for filename in filenames:
        path = Path(filename)
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        raw = pipeline.scan_code(content, str(path))
        all_results.extend(r for r in raw if r.combined_score >= threshold)

    if not all_results:
        console.print("[green]✓ SecretGuard: no secrets detected[/green]")
        return  # exit 0 → commit proceeds

    console.print(
        f"[bold red]BLOCKED — SecretGuard: {len(all_results)} secret(s) found "
        f"— commit rejected[/bold red]\n"
    )
    for r in all_results:
        color = SEVERITY_COLOR.get(r.severity, "white")
        console.print(
            f"[{color}][{r.severity.upper()} {r.combined_score:.3f}][/{color}] "
            f"{r.description}  →  {r.file_path}:{r.line}"
        )
        console.print(f"   [dim]{r.secret[:100]}[/dim]")

    raise typer.Exit(code=1)  # exit 1 → commit is blocked


# ── Git history scan ──────────────────────────────────────────────────────────

@app.command(name="scan-history")
def scan_history(
    repo_path: str = typer.Argument(".", help="Path to the git repository root"),
    threshold: float = typer.Option(
        0.30, "--threshold", "-t",
        help="Minimum combined score to report (0.0–1.0)"
    ),
    max_commits: int = typer.Option(
        0, "--max-commits", "-n",
        help="Limit to the N most recent commits (0 = all)"
    ),
    no_l2: bool = typer.Option(False, "--no-l2", help="Ablation: disable entropy layer"),
    no_l3: bool = typer.Option(False, "--no-l3", help="Ablation: disable classifier layer"),
    no_l4: bool = typer.Option(False, "--no-l4", help="Ablation: disable FP suppressor layer"),
):
    """
    Scan the FULL git commit history for secrets — not just the current HEAD.

    Addresses Cabasa et al. Paper 3 finding: 62%% of student repos leak secrets
    in historical commits that a HEAD-only scan would never catch.
    """
    if not GIT_AVAILABLE:
        console.print(
            "[red]Error:[/red] GitPython is required.  "
            "Run: pip install gitpython"
        )
        raise typer.Exit(code=1)

    n = max_commits if max_commits > 0 else None
    console.print(
        f"[dim]Scanning git history at: {repo_path}  "
        f"max_commits={'all' if n is None else n}  threshold={threshold}[/dim]\n"
    )

    scanner = GitHistoryScanner(
        repo_path=repo_path,
        threshold=threshold,
        max_commits=n,
        enable_l2=not no_l2,
        enable_l3=not no_l3,
        enable_l4=not no_l4,
    )

    scanned = [0]
    total_commits = [0]

    def _progress(idx: int, total: int, sha: str):
        total_commits[0] = total
        scanned[0] = idx
        # Print progress every 10 commits to avoid flooding output
        if idx % 10 == 0 or idx == total:
            console.print(
                f"[dim]  Scanning commit {idx}/{total}  ({sha})[/dim]",
                end="\r",
            )

    findings = scanner.scan(progress_callback=_progress)
    console.print()  # newline after progress

    if not findings:
        console.print(
            f"[green]✓ No secrets found in {scanned[0]} commits.[/green]"
        )
        return

    console.print(
        f"[bold red]⚠ {len(findings)} historical secret(s) detected "
        f"across {scanned[0]} commits:[/bold red]\n"
    )

    # Group findings by commit for readable output
    from collections import defaultdict
    by_commit: dict = defaultdict(list)
    for f in findings:
        by_commit[f.commit_sha_short].append(f)

    for sha_short, commit_findings in by_commit.items():
        first = commit_findings[0]
        console.print(
            f"[bold]Commit {sha_short}[/bold]  "
            f"{first.committed_at.strftime('%Y-%m-%d')}  "
            f"by {first.author_name} — {first.commit_message[:60]}"
        )
        for f in commit_findings:
            color = SEVERITY_COLOR.get(f.severity, "white")
            console.print(
                f"  [{color}][{f.severity.upper()} {f.score:.3f}][/{color}] "
                f"{f.pipeline_result.description}"
            )
            console.print(f"    File: {f.file_path}  line ~{f.line_approx}")
            console.print(f"    [dim]{f.secret[:100]}[/dim]")
        console.print("-" * 72)

    raise typer.Exit(code=1)


# ── Status ─────────────────────────────────────────────────────────────────────

@app.command()
def status():
    """Show active TriFusion component status (classifier model, layers)."""
    st = classifier_status()
    console.print("[bold]TriFusion Component Status[/bold]")
    console.print(f"  Layer 1 (Tiered Regex)        : [green]active[/green]")
    console.print(f"  Layer 2 (Transition Entropy)  : [green]active[/green]")

    mode = st["mode"]
    if mode == "trained":
        console.print(
            f"  Layer 3 (Classifier)          : "
            f"[green]trained[/green] "
            f"(F1={st.get('cv_f1', 'n/a'):.3f}, trained {st.get('trained_at', '?')[:10]})"
        )
    elif mode == "similarity_fallback":
        console.print(
            f"  Layer 3 (Classifier)          : "
            f"[yellow]similarity fallback[/yellow] "
            f"(run train_classifier.py to train)"
        )
    else:
        console.print(
            f"  Layer 3 (Classifier)          : "
            f"[red]heuristic fallback[/red] "
            f"(install sentence-transformers + scikit-learn)"
        )
    console.print(f"  Layer 4 (FP Suppressor)       : [green]active[/green]")
    console.print(f"  Git History Scanner           : "
                  f"{'[green]available[/green]' if GIT_AVAILABLE else '[red]unavailable (pip install gitpython)[/red]'}")


# ── Version ────────────────────────────────────────────────────────────────────

@app.command()
def version():
    """Show SecretGuard version and active components."""
    console.print("SecretGuard (TriFusion) v2.0")
    console.print("Layers: Tiered Regex (L1) | Transition Entropy (L2) | "
                  "Contextual Classifier (L3) | FP Suppressor (L4)")


if __name__ == "__main__":
    app()

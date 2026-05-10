# secretguard/git_history_scanner.py
#
# P2-A — Git History Scanner (Cabasa et al. Gap: historical commits are missed)
#
# Iterates every commit reachable from HEAD, extracts added lines from diffs,
# and feeds them through the full TriFusion 4-layer pipeline.
# Returns GitFinding objects enriched with commit-level provenance metadata.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

try:
    import git  # GitPython
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

from .pipeline import TriFusionPipeline, PipelineResult

# File extensions that are never worth scanning
_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".bin", ".pyc", ".pyo",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".wav", ".avi",
    ".pkl", ".npy", ".npz", ".h5",
}

# Paths to skip even in history (lock files, vendored deps, etc.)
_SKIP_PATH_RE = re.compile(
    r"(node_modules|\.git|venv|\.venv|dist|build|__pycache__|"
    r"\.mypy_cache|\.pytest_cache|package-lock\.json|yarn\.lock|"
    r"Pipfile\.lock|poetry\.lock)",
    re.IGNORECASE,
)


@dataclass
class GitFinding:
    """A secret detection enriched with its git commit provenance."""
    # Provenance
    commit_sha: str
    commit_sha_short: str
    commit_message: str
    author_name: str
    author_email: str
    committed_at: datetime
    branch_hint: str          # branch HEAD was on when scan was run

    # File / location
    file_path: str
    line_approx: int          # approximate line number within the added hunk

    # Pipeline result
    pipeline_result: PipelineResult

    @property
    def rule_id(self) -> str:
        return self.pipeline_result.rule_id

    @property
    def secret(self) -> str:
        return self.pipeline_result.secret

    @property
    def score(self) -> float:
        return self.pipeline_result.combined_score

    @property
    def severity(self) -> str:
        return self.pipeline_result.severity

    def __str__(self) -> str:
        lines = [
            f"[{self.severity.upper()}] {self.pipeline_result.description} "
            f"(score: {self.score:.3f})",
            f"   Commit : {self.commit_sha_short}  {self.committed_at.strftime('%Y-%m-%d')}  "
            f"by {self.author_name} <{self.author_email}>",
            f"   Message: {self.commit_message[:80]}",
            f"   File   : {self.file_path}  (line ~{self.line_approx})",
            f"   Secret : {self.secret[:100]}",
        ]
        for exp in self.pipeline_result.explanation:
            lines.append(f"      • {exp}")
        return "\n".join(lines)


def _should_skip_path(path_str: str) -> bool:
    if Path(path_str).suffix.lower() in _BINARY_EXTENSIONS:
        return True
    if _SKIP_PATH_RE.search(path_str):
        return True
    return False


def _extract_added_lines(diff_text: str) -> List[tuple[int, str]]:
    """
    Parse a unified diff and return (approx_line_number, added_line) tuples.
    Only '+' lines (additions) are returned — deletions are ignored because
    a secret that was removed could still be live in another commit's tree.
    We still want to report it so the caller can decide.
    """
    lines: List[tuple[int, str]] = []
    current_new_line = 0

    for raw in diff_text.splitlines():
        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        hunk = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if hunk:
            current_new_line = int(hunk.group(1))
            continue

        if raw.startswith("+") and not raw.startswith("+++"):
            lines.append((current_new_line, raw[1:]))  # strip leading '+'
            current_new_line += 1
        elif raw.startswith("-"):
            pass  # deletion — don't advance new_line counter
        elif not raw.startswith("\\"):
            current_new_line += 1  # context line

    return lines


class GitHistoryScanner:
    """
    Scans the full git history of a repository through the TriFusion pipeline.

    Gaps addressed (Cabasa et al., Paper 3):
    - 62% of student repos leak secrets — many in historical commits that
      a HEAD-only scan would never see.
    - A commit that adds a key and a subsequent commit that removes it is still
      a leak: the key was exposed in the window between the two commits.
    """

    def __init__(
        self,
        repo_path: str = ".",
        threshold: float = 0.30,
        max_commits: Optional[int] = None,
        enable_l2: bool = True,
        enable_l3: bool = True,
        enable_l4: bool = True,
    ):
        if not GIT_AVAILABLE:
            raise ImportError(
                "GitPython is required for git history scanning. "
                "Install it with: pip install gitpython"
            )
        self.repo = git.Repo(repo_path, search_parent_directories=True)
        self.pipeline = TriFusionPipeline()
        self.threshold = threshold
        self.max_commits = max_commits
        self.enable_l2 = enable_l2
        self.enable_l3 = enable_l3
        self.enable_l4 = enable_l4

    @property
    def _branch_hint(self) -> str:
        try:
            return self.repo.active_branch.name
        except TypeError:
            return "detached-HEAD"

    def _iter_commits(self) -> Iterator[git.Commit]:
        """Yield every commit reachable from HEAD, oldest-first."""
        commits = list(self.repo.iter_commits("HEAD", reverse=True))
        if self.max_commits:
            # Take the most recent N commits (last N from the list)
            commits = commits[-self.max_commits:]
        return iter(commits)

    def _scan_commit(
        self, commit: git.Commit, branch_hint: str
    ) -> List[GitFinding]:
        """Scan all diffs introduced by one commit."""
        findings: List[GitFinding] = []

        # For the very first commit (no parents), diff against empty tree
        if not commit.parents:
            diffs = commit.diff(git.NULL_TREE, create_patch=True)
        else:
            # Compare against first parent (handles merges safely)
            diffs = commit.parents[0].diff(commit, create_patch=True)

        for diff_item in diffs:
            # Resolve path
            file_path = diff_item.b_path or diff_item.a_path or ""
            if _should_skip_path(file_path):
                continue

            # Get diff text
            try:
                diff_text = diff_item.diff
                if isinstance(diff_text, bytes):
                    diff_text = diff_text.decode("utf-8", errors="ignore")
            except Exception:
                continue

            added_lines = _extract_added_lines(diff_text)
            if not added_lines:
                continue

            # Build a pseudo-code block from the added lines for context
            code_block = "\n".join(line for _, line in added_lines)

            # Run pipeline on the entire hunk at once
            results = self.pipeline.scan_code(
                code_block,
                file_path=file_path,
                enable_l2=self.enable_l2,
                enable_l3=self.enable_l3,
                enable_l4=self.enable_l4,
            )

            for r in results:
                if r.combined_score < self.threshold:
                    continue

                # Map the result's line number back to the hunk's approx line
                approx_line = (
                    added_lines[r.line - 1][0]
                    if 0 < r.line <= len(added_lines)
                    else r.line
                )

                findings.append(
                    GitFinding(
                        commit_sha=commit.hexsha,
                        commit_sha_short=commit.hexsha[:8],
                        commit_message=commit.message.strip().splitlines()[0],
                        author_name=commit.author.name or "",
                        author_email=commit.author.email or "",
                        committed_at=datetime.fromtimestamp(commit.committed_date),
                        branch_hint=branch_hint,
                        file_path=file_path,
                        line_approx=approx_line,
                        pipeline_result=r,
                    )
                )

        return findings

    def scan(
        self,
        progress_callback=None,
    ) -> List[GitFinding]:
        """
        Full history scan.

        Args:
            progress_callback: Optional callable(commit_index, total, commit_sha)
                               for progress reporting.

        Returns:
            List of GitFinding objects sorted by (committed_at desc, score desc).
        """
        branch_hint = self._branch_hint
        all_findings: List[GitFinding] = []

        commits = list(self._iter_commits())
        total = len(commits)

        seen_secrets: set[str] = set()  # deduplicate across commits

        for idx, commit in enumerate(commits):
            if progress_callback:
                progress_callback(idx + 1, total, commit.hexsha[:8])

            try:
                findings = self._scan_commit(commit, branch_hint)
            except Exception:
                continue

            for f in findings:
                # Dedup key: same secret value in same file
                dedup_key = f"{f.file_path}::{f.secret}"
                if dedup_key in seen_secrets:
                    continue
                seen_secrets.add(dedup_key)
                all_findings.append(f)

        # Sort: most recent first, then highest score
        all_findings.sort(key=lambda f: (-f.committed_at.timestamp(), -f.score))
        return all_findings

    def scan_commit_range(
        self, start_sha: str, end_sha: str
    ) -> List[GitFinding]:
        """Scan only commits between start_sha..end_sha (inclusive)."""
        branch_hint = self._branch_hint
        all_findings: List[GitFinding] = []

        commits = list(
            self.repo.iter_commits(f"{start_sha}..{end_sha}", reverse=True)
        )

        for commit in commits:
            try:
                findings = self._scan_commit(commit, branch_hint)
            except Exception:
                continue
            all_findings.extend(
                f for f in findings if f.combined_score >= self.threshold
            )

        all_findings.sort(key=lambda f: (-f.committed_at.timestamp(), -f.score))
        return all_findings

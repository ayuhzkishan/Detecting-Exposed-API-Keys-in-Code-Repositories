# secretguard/detector.py

import re
import tomli
from pathlib import Path
from typing import List, Dict, Any
from .entropy import shannon_entropy, is_high_entropy

# Thresholds for generic high-entropy secrets
HIGH_ENTROPY_MIN_LENGTH = 20
HIGH_ENTROPY_THRESHOLD = 3.9

SECRET_KEYWORDS = {
    "key", "secret", "token", "password", "pwd", "api", "auth", "credential",
    "pass", "private", "access", "session", "jwt", "bearer", "client_id",
    "client_secret", "id_token", "refresh_token"
}

# Files/paths to skip for entropy scan (regex patterns)
SKIP_PATH_PATTERNS = [
    r'/__tests__/', r'/fixtures/',
    r'/examples?/', r'/docs?/', r'\.md$', r'\.txt$', r'\.json$',
    r'\.lock$', r'node_modules/', r'venv/', r'__pycache__/'
]

# Variable-name prefixes that mark a value as intentionally fake/test data
NEGATIVE_KEYWORDS = {
    "test", "fake", "dummy", "example", "sample", "mock", "placeholder"
}

class Finding:
    """Simple class to hold one detected secret"""
    def __init__(
        self,
        rule_id: str,
        description: str,
        secret: str,
        file_path: str,
        line: int,
        line_content: str,
        severity: str,
    ):
        self.rule_id = rule_id
        self.description = description
        self.secret = secret
        self.file_path = file_path
        self.line = line
        self.line_content = line_content.strip()
        self.severity = severity

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.description}\n"
            f"   → File: {self.file_path}:{self.line}\n"
            f"   → Match: {self.secret}\n"
            f"   → Line: {self.line_content}"
        )


def load_rules() -> List[Dict[str, Any]]:
    """Load rules from rules.toml"""
    rules_path = Path(__file__).parent / "rules.toml"
    with open(rules_path, "rb") as f:
        data = tomli.load(f)
    return data.get("rules", [])


class Detector:
    """Main secret detection engine"""

    def __init__(self):
        self.rules = load_rules()
        # Pre-compile regex for speed
        self.compiled_rules = []
        for rule in self.rules:
            pattern = rule["regex"]
            # Add word boundaries where helpful
            if not pattern.startswith("(?i)"):
                pattern = r"(?i)" + pattern
            try:
                regex = re.compile(pattern)
                self.compiled_rules.append((rule, regex))
            except re.error as e:
                print(f"Invalid regex in rule {rule['id']}: {e}")

    def scan_file(self, file_path: str) -> List[Finding]:
        """Scan a single file and return list of findings"""
        findings = []
        path = Path(file_path)

        if not path.is_file():
            return findings

        # Skip obvious binary / unwanted files
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".bin", ".exe"}:
            return findings

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.splitlines()
        except Exception:
            return findings

        # 1. Run all regex-based rules
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            # Negative-keyword guard: skip assignments that are clearly test/fake data
            if any(line_lower.lstrip().startswith(neg) for neg in NEGATIVE_KEYWORDS):
                continue

            for rule, regex in self.compiled_rules:
                for match in regex.finditer(line):
                    secret = match.group(0)
                    if len(secret) < rule.get("min_length", 8):
                        continue

                    finding = Finding(
                        rule_id=rule["id"],
                        description=rule["description"],
                        secret=secret,
                        file_path=str(path),
                        line=line_num,
                        line_content=line,
                        severity=rule.get("severity", "medium"),
                    )
                    findings.append(finding)

        # 2. Run high-entropy detector
        entropy_findings = self._scan_high_entropy(str(path), lines)
        findings.extend(entropy_findings)

        return findings


    def _scan_high_entropy(self, file_path: str, lines: list[str]) -> list[Finding]:
        """Improved high-entropy scanner with context & proximity"""
        findings = []
        path_lower = file_path.lower()

        # Skip entropy scan on ignored paths/files
        if any(re.search(pat, path_lower) for pat in SKIP_PATH_PATTERNS):
            return findings

        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()

            # Optional: skip lines that look like comments or docs
            if line.strip().startswith(('#', '//', '/*', '* ', '"""', "'''")):
                continue

            # Better candidate extraction: longer strings with mixed chars
            # Lookbehind avoids matching the tail of a data URI / base64 header.
            candidates = re.findall(
                r'(?<![A-Za-z0-9+/=._-])[A-Za-z0-9+/=._-]{' + str(HIGH_ENTROPY_MIN_LENGTH) + r',}(?![A-Za-z0-9+/=._-])',
                line
            )

            # Skip the whole line if it looks like a data URI
            if re.search(r'data:[^;]+;base64,', line):
                continue

            for candidate in candidates:
                # Quick filter: skip if too repetitive (e.g. AAAA..., 1111...)
                if len(set(candidate)) <= 4:  # very few unique chars
                    continue

                # Skip if already matched by a specific rule (no double-report)
                if any(regex.search(candidate) for _, regex in self.compiled_rules):
                    continue

                # Proximity filter: require at least one SECRET keyword nearby
                window_start = max(0, line.find(candidate) - 50)
                window_end = min(len(line), line.find(candidate) + len(candidate) + 50)
                window = line_lower[window_start:window_end]

                has_keyword = any(kw in window for kw in SECRET_KEYWORDS)

                if not has_keyword:
                    continue  # skip — no context

                # Negative-keyword guard: skip test/fake/dummy assignments
                if any(neg in window for neg in NEGATIVE_KEYWORDS):
                    continue

                ent = shannon_entropy(candidate)

                if ent >= HIGH_ENTROPY_THRESHOLD:
                    finding = Finding(
                        rule_id="high-entropy-generic",
                        description=f"High entropy string (score: {ent:.2f}) — possible secret",
                        secret=candidate,
                        file_path=file_path,
                        line=line_num,
                        line_content=line.strip()[:180] + ("..." if len(line.strip()) > 180 else ""),
                        severity="medium" if ent < 4.2 else "high",
                    )
                    findings.append(finding)

        return findings
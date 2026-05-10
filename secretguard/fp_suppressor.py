# secretguard/fp_suppressor.py
# Layer 4 — False Positive Suppressor
# Rule-based post-filter derived from Paper 1 (Saha et al.) false positive categories.

import re
from typing import Dict, List, Tuple


# Known placeholder patterns (Paper 1 Section 2.2 + Paper 2 insights)
PLACEHOLDER_PATTERNS = [
    r"(?i)your[-_\s]*(api[-_\s]*)?key[-_\s]*here",
    r"(?i)your[-_\s]*(api[-_\s]*)?secret[-_\s]*here",
    r"(?i)your[-_\s]*(api[-_\s]*)?token[-_\s]*here",
    r"(?i)your[-_\s]*password[-_\s]*here",
    r"(?i)replace[-_\s]*me",
    r"(?i)insert[-_\s]*(your[-_\s]*)?key",
    r"(?i)put[-_\s]*(your[-_\s]*)?key[-_\s]*here",
    r"(?i)^xxx+$",
    r"(?i)^placeholder",
    r"(?i)^example",
    r"(?i)^sample",
    r"(?i)^todo",
    r"(?i)^fixme",
    r"(?i)^changeme",
    r"(?i)^test[-_]?key",
    r"(?i)^test[-_]?token",
    r"(?i)^test[-_]?secret",
    r"(?i)^dummy",
    r"(?i)^fake",
    r"(?i)^mock",
]

# Weak / default passwords that should never be treated as real secrets.
# Derived from OWASP Top-10 weak passwords + Cabasa et al. student-repo findings.
WEAK_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "p@ssword",
    "admin", "admin123", "administrator",
    "root", "root123",
    "user", "user123",
    "test", "test123", "testing",
    "demo", "demo123",
    "guest", "guest123",
    "dev", "devpassword", "development",
    "local", "localhost",
    "secret", "secret123",
    "welcome", "welcome1",
    "letmein", "letmein1",
    "qwerty", "qwerty123",
    "abc123", "abcdef",
    "111111", "123456", "1234567", "12345678", "123456789", "1234567890",
    "000000", "pass", "login",
    "changeme", "change_me",
    "default", "default123",
    "blank", "empty",
    "null", "none", "undefined",
    "placeholder", "todo",
    "django-insecure",
}

# Cloud API patterns (Paper 2)
CLOUD_API_PATTERNS = [
    r"(?i)api\.", r"(?i)\.amazonaws\.com", r"(?i)googleapi", r"(?i)stripe\.com",
    r"(?i)azure", r"(?i)twilio", r"(?i)heroku", r"(?i)auth0", r"(?i)firebase"
]

# Test/mock directory patterns
TEST_DIR_PATTERNS = [
    r"[/\\]tests?[/\\]",
    r"[/\\]__tests__[/\\]",
    r"[/\\]test[-_]",
    r"[/\\]mock[s]?[/\\]",
    r"[/\\]fixture[s]?[/\\]",
    r"[/\\]example[s]?[/\\]",
    r"[/\\]spec[s]?[/\\]",
    r"[/\\]stubs?[/\\]",
]

# Readme / documentation file patterns
DOC_FILE_PATTERNS = [
    r"(?i)readme",
    r"(?i)\.md$",
    r"(?i)\.rst$",
    r"(?i)\.txt$",
    r"(?i)[/\\]docs?[/\\]",
    r"(?i)changelog",
    r"(?i)contributing",
    r"(?i)license",
]

# Null value patterns
NULL_PATTERNS = [
    r"(?i)^\s*null\s*$",
    r"(?i)^\s*none\s*$",
    r"(?i)^\s*undefined\s*$",
    r"(?i)^\s*nil\s*$",
    r'^\s*""\s*$',
    r"^\s*''\s*$",
    r"^\s*$",
]


class SuppressionResult:
    """Result of running the FP suppressor on a single candidate."""
    def __init__(self):
        self.rules_fired: List[str] = []
        self.penalties: List[float] = []
        self.explanations: List[str] = []
        self.total_penalty: float = 0.0
        self.suppressed: bool = False

    def add_rule(self, rule_name: str, penalty: float, explanation: str):
        self.rules_fired.append(rule_name)
        self.penalties.append(penalty)
        self.explanations.append(explanation)
        self.total_penalty = min(1.0, self.total_penalty + penalty)
        if self.total_penalty >= 0.8:
            self.suppressed = True

    def get_suppressor_score(self) -> float:
        """Returns 1.0 (no penalty) to 0.0 (fully suppressed)."""
        return max(0.0, 1.0 - self.total_penalty)


class FPSuppressor:
    """
    Layer 4 — Rule-based false positive suppressor.
    Applies penalty rules derived from Paper 1 (Saha et al.) Section 2.2:
    - Function calls in assignment context
    - Variable-to-variable assignments
    - Test/mock/example directories
    - README/docs/markdown files
    - Numeric-only values
    - Null/None/undefined/empty assignments
    - CSS selectors or style values
    - Commented-out code
    - Placeholder patterns
    - Low transition entropy
    """

    def __init__(self):
        self._compiled_placeholders = [re.compile(p) for p in PLACEHOLDER_PATTERNS]
        self._compiled_test_dirs = [re.compile(p) for p in TEST_DIR_PATTERNS]
        self._compiled_doc_files = [re.compile(p) for p in DOC_FILE_PATTERNS]
        self._compiled_null = [re.compile(p) for p in NULL_PATTERNS]
        self._compiled_cloud = [re.compile(p) for p in CLOUD_API_PATTERNS]
        # Normalised weak-password set for O(1) lookup
        self._weak_passwords = {p.lower() for p in WEAK_PASSWORDS}

    def suppress(
        self,
        secret_value: str,
        line_content: str,
        file_path: str = "",
        transition_entropy_val: float = None,
    ) -> SuppressionResult:
        """Run all suppression rules against a candidate detection."""
        result = SuppressionResult()

        # Rule 1: has_function_call — password = getPassword()
        self._check_function_call(line_content, secret_value, result)

        # Rule 2: is_variable_assignment — password = ui.password
        self._check_variable_assignment(line_content, secret_value, result)

        # Rule 3: in_test_directory
        self._check_test_directory(file_path, result)

        # Rule 4: in_readme_file
        self._check_readme_file(file_path, result)

        # Rule 5: is_numeric_only
        self._check_numeric_only(secret_value, line_content, result)

        # Rule 6: has_null_value — null, None, undefined, "", ''
        self._check_null_value(line_content, secret_value, result)

        # Rule 7: is_css_selector
        self._check_css_selector(line_content, result)

        # Rule 8: is_commented_out
        self._check_commented_out(line_content, result)

        # Rule 9: matches_placeholder_pattern
        self._check_placeholder(secret_value, result)

        # Rule 10: transition_entropy_below_threshold
        if transition_entropy_val is not None:
            self._check_transition_entropy(transition_entropy_val, secret_value, result)

        # Rule 11: is_empty_string
        self._check_empty_string(secret_value, result)

        # Rule 12: repeated chars in extracted value (for keyword-anchored matches)
        self._check_repeated_chars_in_value(secret_value, line_content, result)

        # Rule 13: no_cloud_api_nearby (Paper 2 category)
        self._check_cloud_api_nearby(line_content, secret_value, result)

        # Rule 14: weak/default password (Cabasa et al. student-repo finding)
        self._check_weak_password(secret_value, line_content, result)

        return result

    def _check_cloud_api_nearby(self, line: str, secret: str, result: SuppressionResult):
        """Check if any cloud API patterns appear in the line/context (Paper 2)"""
        # We only apply this penalty to generic matches, not Tier 1 prefixed ones
        # which is handled by the caller or by virtue of those having unique prefixes
        has_api = any(pat.search(line) for pat in self._compiled_cloud)
        if not has_api and len(secret) < 30:
            result.add_rule(
                "no_cloud_api_nearby", 0.30,
                "No cloud API indicators (URLs/keywords) found nearby"
            )

    def _check_function_call(self, line: str, secret: str, result: SuppressionResult):
        """Detect function call assignments like password = getPassword()"""
        # Match: keyword = functionName() or keyword = module.function()
        pattern = r"(?i)(password|secret|key|token|pwd|auth)\s*=\s*\w+[\.\w]*\([^)]*\)"
        if re.search(pattern, line):
            result.add_rule(
                "has_function_call", 0.95,
                "Value is a function call return, not a hardcoded secret"
            )

    def _check_variable_assignment(self, line: str, secret: str, result: SuppressionResult):
        """Detect variable-to-variable assignments like password = ui.password
        or environment variable lookups like secret = os.environ['SECRET']"""
        # Match: keyword = identifier.identifier (no quotes around value)
        pattern1 = r"(?i)(password|secret|key|token|pwd|auth|pass|credential)\s*=\s*([a-zA-Z_]\w*\.\w+)\s*$"
        # Match: keyword = identifier.identifier[...] or identifier['...']
        pattern2 = r"(?i)(password|secret|key|token|pwd|auth|pass|credential)\s*=\s*([a-zA-Z_]\w*[\.\[])"
        # Match: keyword = os.environ / os.getenv / config.get patterns (not quoted RHS)
        pattern3 = r"(?i)(password|secret|key|token|pwd|auth|pass|credential)\s*=\s*(os\.|config\.|settings\.|env\.|process\.)"

        stripped = line.strip()
        if re.search(pattern1, stripped) or re.search(pattern2, stripped) or re.search(pattern3, stripped):
            # Make sure RHS is not a quoted string literal
            assign = re.search(r'=\s*(.+)$', stripped)
            if assign:
                rhs = assign.group(1).strip()
                # If RHS starts with a quote, it's a literal — don't suppress
                if rhs.startswith(('"', "'", 'f"', "f'")):
                    return
            result.add_rule(
                "is_variable_assignment", 0.90,
                "Value is a variable reference or env lookup, not a literal secret"
            )

    def _check_test_directory(self, file_path: str, result: SuppressionResult):
        """Detect files in test/mock/example directories.
        Penalty raised to 0.85 so it crosses the multiplicative-gate threshold (0.80),
        meaning a file-in-test-dir is treated as a veto regardless of entropy/classifier.
        """
        if file_path:
            for pat in self._compiled_test_dirs:
                if pat.search(file_path):
                    result.add_rule(
                        "in_test_directory", 0.85,
                        "File is in a test/mock/example directory — likely fixture data"
                    )
                    return

    def _check_readme_file(self, file_path: str, result: SuppressionResult):
        """Detect files that are READMEs, docs, or markdown.
        Penalty raised to 0.85 (gate threshold) — docs are never production code.
        """
        if file_path:
            for pat in self._compiled_doc_files:
                if pat.search(file_path):
                    result.add_rule(
                        "in_readme_file", 0.85,
                        "File is documentation/README — likely example code"
                    )
                    return

    def _check_numeric_only(self, secret: str, line: str, result: SuppressionResult):
        """Detect numeric-only values.

        Bug fix (P3): The full regex match for keyword-anchored rules is something like
        'api_key = \"9876543210\"'. Stripping the outer quotes only removes the first/last
        character of the entire match string, not the value. We must extract the quoted
        RHS value first, then test if it is all-numeric.
        """
        # Priority 1: extract quoted value from full match or line
        candidates = re.findall(r'["\']([^"\']*)["\']', secret)
        if not candidates:
            candidates = re.findall(r'["\']([^"\']*)["\']', line)
        if not candidates:
            # Fallback: treat the whole secret as the value
            candidates = [secret.strip().strip("'\"")]

        for val in candidates:
            val = val.strip()
            if val and re.match(r"^\d+$", val):
                result.add_rule(
                    "is_numeric_only", 0.85,
                    f"Extracted value '{val}' is numeric-only — not a real secret"
                )
                return

    def _check_null_value(self, line: str, secret: str, result: SuppressionResult):
        """Detect null/None/undefined/empty assignments"""
        # Check if the RHS of assignment is a null-like value
        # Broader keyword list: includes db_pass, credential, etc.
        assign_match = re.search(
            r"(?i)(\w*(?:password|secret|key|token|pwd|auth|pass|credential)\w*)\s*=\s*(.+)$", line.strip()
        )
        if assign_match:
            rhs = assign_match.group(2).strip()
            for pat in self._compiled_null:
                if pat.match(rhs):
                    result.add_rule(
                        "has_null_value", 0.95,
                        f"Value is null/None/empty -- not a real secret"
                    )
                    return

    def _check_css_selector(self, line: str, result: SuppressionResult):
        """Detect CSS selectors or style values"""
        css_patterns = [
            r"{\s*[\w-]+\s*:\s*",         # { color:
            r"^\s*[\w-]+\s*:\s*[\w#]+;",  # color: #fff;
            r"@media\s",
            r"\.[\w-]+\s*{",              # .class {
            r"#[\w-]+\s*{",               # #id {
        ]
        for pat in css_patterns:
            if re.search(pat, line):
                result.add_rule(
                    "is_css_selector", 0.85,
                    "Line appears to be CSS — not a secret"
                )
                return

    def _check_commented_out(self, line: str, result: SuppressionResult):
        """Detect commented-out code (Paper 1 Section 2.2 FP category)"""
        stripped = line.strip()
        if stripped.startswith(("#", "//", "/*", "* ", "<!--")):
            result.add_rule(
                "is_commented_out", 0.85,
                "Line is commented out -- deactivated or example code"
            )

    def _check_placeholder(self, secret: str, result: SuppressionResult):
        """Detect common placeholder patterns"""
        cleaned = secret.strip().strip("'\"")
        for pat in self._compiled_placeholders:
            if pat.search(cleaned):
                result.add_rule(
                    "matches_placeholder_pattern", 0.90,
                    f"Value matches known placeholder pattern"
                )
                return

    def _check_transition_entropy(self, te_val: float, secret: str, result: SuppressionResult):
        """Flag low transition entropy (repetitive patterns)"""
        # Only apply if the string is long enough that we'd expect higher entropy
        cleaned = secret.strip().strip("'\"")
        if len(cleaned) >= 12 and te_val < 2.2:
            result.add_rule(
                "transition_entropy_below_threshold", 0.80,
                f"Transition entropy ({te_val:.2f}) below threshold — likely placeholder/dummy data"
            )

    def _check_empty_string(self, secret: str, result: SuppressionResult):
        """Detect empty string values"""
        cleaned = secret.strip()
        if cleaned in ('""', "''", ''):
            result.add_rule(
                "is_empty_string", 0.95,
                "Value is an empty string -- not a real secret"
            )

    def _check_repeated_chars_in_value(self, secret: str, line: str, result: SuppressionResult):
        """Extract the value portion from keyword=value assignments and check for repeated chars.
        This catches cases where the full regex match is 'PASSWORD = "XXXX..."' but
        the entropy is computed on the full match string (which has varied transitions)."""
        # Try to extract just the quoted value from the matched string
        quoted = re.findall(r'["\']([^"\']+)["\']', secret)
        if not quoted:
            quoted = re.findall(r'["\']([^"\']+)["\']', line)

        for val in quoted:
            # Check if value is all the same character repeated
            if len(val) >= 8 and len(set(val)) <= 2:
                result.add_rule(
                    "transition_entropy_below_threshold", 0.85,
                    f"Extracted value '{val[:20]}...' is repetitive chars -- placeholder"
                )
                return
            # Check if value matches known placeholder patterns
            from .entropy import is_known_placeholder
            if is_known_placeholder(val):
                result.add_rule(
                    "matches_placeholder_pattern", 0.90,
                    f"Extracted value matches placeholder pattern"
                )
                return

    def _check_weak_password(self, secret: str, line: str, result: SuppressionResult):
        """
        Rule 14 — Weak/default password list (Cabasa et al. gap).

        Cabasa et al. found that 'admin', 'root', 'password', 'devpassword' and
        similar defaults are the most common non-secret findings in student repos.
        These should be suppressed — they are not real credential leaks.
        """
        candidates = re.findall(r'["\']([^"\']*)["\']', secret)
        if not candidates:
            candidates = re.findall(r'["\']([^"\']*)["\']', line)

        for val in candidates:
            val_lower = val.strip().lower()
            if val_lower in self._weak_passwords:
                result.add_rule(
                    "is_weak_default_password", 0.85,
                    f"Value '{val}' is a known weak/default credential — not a real secret"
                )
                return
            for weak_prefix in ("django-insecure", "django-secret", "dev-secret", "local-secret"):
                if val_lower.startswith(weak_prefix):
                    result.add_rule(
                        "is_weak_default_password", 0.85,
                        f"Value starts with known framework default prefix '{weak_prefix}'"
                    )
                    return

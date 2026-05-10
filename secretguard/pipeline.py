# secretguard/pipeline.py
# TriFusion Combined Pipeline — Integrates all four layers into a single scoring pipeline.
#
# Detection Score = (Regex Tier Weight × 0.30) + (Entropy Score × 0.20)
#                 + (Classifier Probability × 0.35) + (FP Suppressor Score × 0.15)

import re
import tomli
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .entropy import shannon_entropy, transition_entropy, evaluate_entropy
from .fp_suppressor import FPSuppressor, SuppressionResult
from .classifier import ContextualClassifier, build_string_group, extract_string_literals


# ── Tier definitions ──────────────────────────────────────────
# Tier 1: High confidence — unique, precise prefix patterns (AKIA, AIza, sk_live, etc.)
# Tier 2: Medium confidence — keyword-anchored patterns (password=, token=, etc.)
# Tier 3: Low confidence — loose/generic patterns (twitter client id, generic hex)

TIER_WEIGHTS = {
    1: 1.0,   # Tier 1: full regex confidence
    2: 0.70,  # Tier 2: moderate regex confidence
    3: 0.40,  # Tier 3: low regex confidence — needs other layers to confirm
}

# Map rule IDs to their confidence tiers
RULE_TIERS = {
    # Tier 1 — precise prefixed patterns
    "aws-access-key": 1,
    "aws-secret-key": 1,
    "github-token": 1,
    "stripe-secret-key": 1,
    "stripe-restricted-key": 1,
    "private-key-openssh": 1,
    "private-key-rsa": 1,
    "private-key-ec": 1,
    "private-key-pgp": 1,
    "private-key-generic": 1,
    "slack-token": 1,
    "google-api-key": 1,
    "google-oauth-access-token": 1,
    "paypal-braintree-token": 1,
    "amazon-mws-auth-token": 1,
    "twilio-api-key": 1,
    "square-access-token": 1,
    "square-oauth-secret": 1,
    "facebook-access-token": 1,
    "picatic-api-key": 1,
    "auth-token-bearer": 1,

    # Tier 2 — keyword-anchored
    "generic-api-key": 2,
    "mailgun-api-key": 2,
    "mailchimp-api-key": 2,
    "google-oauth-id": 2,
    "google-oauth-auth-code": 2,
    "google-oauth-refresh-token": 2,

    # Tier 3 — loose patterns
    "twitter-access-token": 3,
    "high-entropy-generic": 3,
}

# Layer weights in the combined score
LAYER_WEIGHTS = {
    "regex": 0.30,
    "entropy": 0.20,
    "classifier": 0.35,
    "suppressor": 0.15,
}


class PipelineResult:
    """Result from a single detection through the full TriFusion pipeline."""

    def __init__(
        self,
        rule_id: str,
        description: str,
        secret: str,
        file_path: str,
        line: int,
        line_content: str,
    ):
        self.rule_id = rule_id
        self.description = description
        self.secret = secret
        self.file_path = file_path
        self.line = line
        self.line_content = line_content.strip()

        # Layer scores
        self.tier: int = 3
        self.regex_score: float = 0.0
        self.entropy_score: float = 0.0
        self.classifier_score: float = 0.0
        self.suppressor_score: float = 1.0  # 1.0 = no penalty

        # Metadata
        self.shannon: float = 0.0
        self.transition: float = 0.0
        self.is_placeholder: bool = False
        self.suppression_result: Optional[SuppressionResult] = None
        self.classifier_details: Dict = {}

        # Combined
        self.combined_score: float = 0.0
        self.explanation: List[str] = []

    def compute_combined_score(self):
        """
        Detection Score = (Regex Tier Weight * 0.30) + (Entropy Score * 0.20)
                        + (Classifier Probability * 0.35) + (FP Suppressor Score * 0.15)

        CRITICAL REFINEMENT: Layer 3 (Classifier) probability is adjusted based on Layer 1's tier.
        For low-confidence Tier 3 matches, we penalize the classifier score unless it is
        exceptionally high.
        """
        # Base classifier adjustment based on tier
        adj_classifier = self.classifier_score
        if self.tier == 3:
            # Stricter for high-FP categories
            adj_classifier *= 0.70
        elif self.tier == 1:
            # More lenient for strong prefixes
            adj_classifier = min(1.0, adj_classifier * 1.1)

        # Base score from Layers 1-3
        base_score = (
            self.regex_score * LAYER_WEIGHTS["regex"]
            + self.entropy_score * LAYER_WEIGHTS["entropy"]
            + adj_classifier * LAYER_WEIGHTS["classifier"]
        )

        if self.suppression_result and self.suppression_result.total_penalty >= 0.80:
            # MULTIPLICATIVE GATE: Confident false positive identifications
            # (function calls, placeholders, numeric-only) act as a veto.
            self.combined_score = base_score * self.suppressor_score
        else:
            # Normal: Additive model for minor penalties
            self.combined_score = base_score + self.suppressor_score * LAYER_WEIGHTS["suppressor"]

        self.combined_score = round(self.combined_score, 3)

        # Build human-readable explanation
        self.explanation = []
        self.explanation.append(
            f"Tier {self.tier} regex match ({self.regex_score:.2f} x {LAYER_WEIGHTS['regex']:.2f} = {self.regex_score * LAYER_WEIGHTS['regex']:.3f})"
        )
        self.explanation.append(
            f"Entropy score ({self.entropy_score:.2f} x {LAYER_WEIGHTS['entropy']:.2f} = {self.entropy_score * LAYER_WEIGHTS['entropy']:.3f})"
            + (f" [PLACEHOLDER detected]" if self.is_placeholder else "")
        )
        self.explanation.append(
            f"Classifier probability ({self.classifier_score:.2f} x {LAYER_WEIGHTS['classifier']:.2f} = {self.classifier_score * LAYER_WEIGHTS['classifier']:.3f})"
        )
        supp_mode = "MULTIPLICATIVE GATE" if (self.suppression_result and self.suppression_result.total_penalty >= 0.80) else "additive"
        supp_str = f"Suppressor score ({self.suppressor_score:.2f}, mode={supp_mode})"
        if self.suppression_result and self.suppression_result.rules_fired:
            supp_str += f" [Rules: {', '.join(self.suppression_result.rules_fired)}]"
        self.explanation.append(supp_str)

    @property
    def severity(self) -> str:
        if self.combined_score >= 0.70:
            return "critical"
        elif self.combined_score >= 0.50:
            return "high"
        elif self.combined_score >= 0.30:
            return "medium"
        else:
            return "low"

    def __str__(self) -> str:
        lines = [
            f"[{self.severity.upper()}] {self.description} (score: {self.combined_score:.3f})",
            f"   → File: {self.file_path}:{self.line}",
            f"   → Match: {self.secret[:80]}",
            f"   → Explanation:",
        ]
        for exp in self.explanation:
            lines.append(f"      • {exp}")
        return "\n".join(lines)


class TriFusionPipeline:
    """
    Full TriFusion detection pipeline.
    Layers:
      1. Tiered regex engine
      2. Entropy + pattern filter (Shannon + Transition)
      3. Contextual embedding classifier
      4. False positive suppressor
    """

    def __init__(self):
        self.rules = self._load_rules()
        self.compiled_rules = self._compile_rules()
        self.suppressor = FPSuppressor()
        self.classifier = ContextualClassifier()

    def _load_rules(self) -> List[Dict[str, Any]]:
        rules_path = Path(__file__).parent / "rules.toml"
        with open(rules_path, "rb") as f:
            data = tomli.load(f)
        return data.get("rules", [])

    def _compile_rules(self) -> List[tuple]:
        compiled = []
        for rule in self.rules:
            pattern = rule["regex"]
            if not pattern.startswith("(?i)"):
                pattern = r"(?i)" + pattern
            try:
                regex = re.compile(pattern)
                compiled.append((rule, regex))
            except re.error:
                pass
        return compiled

    def scan_line(
        self,
        line: str,
        line_num: int,
        file_path: str = "",
        code_lines: List[str] = None,
        enable_l2: bool = True,
        enable_l3: bool = True,
        enable_l4: bool = True,
    ) -> List[PipelineResult]:
        """Run the full 4-layer pipeline on one line of code."""
        results = []

        # Skip obviously empty lines
        stripped = line.strip()
        if not stripped:
            return results

        # ── Layer 1: Tiered Regex ──
        for rule, regex in self.compiled_rules:
            for match in regex.finditer(line):
                secret = match.group(0)
                if len(secret) < rule.get("min_length", 8):
                    continue

                rule_id = rule["id"]
                tier = RULE_TIERS.get(rule_id, 3)

                result = PipelineResult(
                    rule_id=rule_id,
                    description=rule["description"],
                    secret=secret,
                    file_path=file_path,
                    line=line_num,
                    line_content=line,
                )
                result.tier = tier
                result.regex_score = TIER_WEIGHTS.get(tier, 0.4)

                # ── Layer 2: Entropy ──
                if enable_l2:
                    entropy_result = evaluate_entropy(secret)
                    result.shannon = entropy_result["shannon"]
                    result.transition = entropy_result["transition"]
                    result.is_placeholder = entropy_result.get("is_placeholder_pattern", False)
                    result.entropy_score = entropy_result["entropy_score"]
                else:
                    # In ablation: Layer 2 gives a static neutral score
                    result.entropy_score = 0.5

                # ── Layer 3: Contextual Classifier ──
                if enable_l3:
                    if code_lines:
                        line_idx = max(0, line_num - 1)
                        classifier_result = self.classifier.classify_from_code(
                            code_lines, line_idx, secret
                        )
                    else:
                        string_group = build_string_group(line, secret)
                        classifier_result = self.classifier.classify_string_group(string_group)

                    result.classifier_score = classifier_result.get("probability", 0.5)
                    result.classifier_details = classifier_result
                else:
                    # In ablation: Layer 3 gives a static neutral score
                    result.classifier_score = 0.5

                # ── Layer 4: FP Suppressor ──
                if enable_l4:
                    suppression = self.suppressor.suppress(
                        secret_value=secret,
                        line_content=line,
                        file_path=file_path,
                        transition_entropy_val=result.transition if enable_l2 else None,
                    )
                    result.suppression_result = suppression
                    result.suppressor_score = suppression.get_suppressor_score()
                else:
                    # In ablation: Layer 4 gives a static perfect score (no suppression)
                    result.suppressor_score = 1.0

                # ── Combine ──
                result.compute_combined_score()
                results.append(result)

        return results

    def scan_code(
        self,
        code: str,
        file_path: str = "<snippet>",
        enable_l2: bool = True,
        enable_l3: bool = True,
        enable_l4: bool = True,
    ) -> List[PipelineResult]:
        """Scan a full code snippet through the pipeline."""
        lines = code.splitlines()
        all_results = []

        for i, line in enumerate(lines):
            line_results = self.scan_line(
                line=line,
                line_num=i + 1,
                file_path=file_path,
                code_lines=lines,
                enable_l2=enable_l2,
                enable_l3=enable_l3,
                enable_l4=enable_l4,
            )
            all_results.extend(line_results)

        # Sort by combined score descending
        all_results.sort(key=lambda r: -r.combined_score)
        return all_results

    def scan_file(self, file_path: str) -> List[PipelineResult]:
        """Scan a file through the full pipeline."""
        path = Path(file_path)
        if not path.is_file():
            return []

        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".bin", ".exe"}:
            return []

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return []

        return self.scan_code(content, str(path))

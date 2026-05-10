# secretguard/entropy.py

import math
from collections import Counter
import re

# Known placeholder patterns (Paper 1 Section 2.2 + Paper 2)
PLACEHOLDER_PATTERNS = [
    re.compile(r"(?i)your[-_\s]*(api[-_\s]*)?(key|secret|token|password)[-_\s]*here"),
    re.compile(r"(?i)replace[-_\s]*me"),
    re.compile(r"(?i)insert[-_\s]*(your[-_\s]*)?(key|token)"),
    re.compile(r"(?i)^xxx+$"),
    re.compile(r"(?i)^placeholder"),
    re.compile(r"(?i)^example[-_]?(key|token|secret|password)"),
    re.compile(r"(?i)^sample[-_]?(key|token|secret|password)"),
    re.compile(r"(?i)^todo"),
    re.compile(r"(?i)^changeme"),
    re.compile(r"(?i)^test[-_]?(key|token|secret|password)$"),
    re.compile(r"(?i)^dummy"),
    re.compile(r"(?i)^fake[-_]?(key|token|secret|password)"),
    re.compile(r"(?i)^mock[-_]?(key|token|secret|password)"),
    re.compile(r"(?i)^password\d*$"),  # password, password1, password123
    re.compile(r"(?i)^(abc|abcdef|abcdefgh)\d*$"),  # abc123, abcdef123
    re.compile(r"(?i)^replace[-_]?me[-_]?with[-_]?(key|token|secret)"),
]


def is_known_placeholder(s: str) -> bool:
    """Check if a string matches known placeholder patterns."""
    for pat in PLACEHOLDER_PATTERNS:
        if pat.search(s):
            return True
    return False


def shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy (bits per character)"""
    if not data or len(data) <= 1:
        return 0.0

    freq = Counter(data)
    length = len(data)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def is_high_entropy(s: str, min_length: int = 20, threshold: float = 3.9) -> bool:
    """Common-sense check for likely secret-like strings"""
    if len(s) < min_length:
        return False
    return shannon_entropy(s) >= threshold


# Optional: rough charset filters to reduce obvious FPs
def looks_like_base64ish(s: str) -> bool:
    """Base64-like (A-Z a-z 0-9 + / =)"""
    return bool(re.match(r'^[A-Za-z0-9+/=]{20,}$', s))


def looks_like_hex(s: str) -> bool:
    """Hex-like (0-9 a-f A-F)"""
    return bool(re.match(r'^[0-9a-fA-F]{32,}$', s))


def transition_entropy(data: str) -> float:
    """
    Calculate transition entropy (character-to-character unpredictability).
    Real secrets have high transition entropy.
    Placeholders like "XXXXXXXXXXXX", "YOUR_API_KEY", or "0123456789" have LOW transition entropy.
    Focuses on mitigating false positives highlighted in Paper 1 and Paper 2.
    """
    if not data or len(data) <= 1:
        return 0.0

    transitions = [data[i:i+2] for i in range(len(data)-1)]
    freq = Counter(transitions)
    total = len(transitions)

    entropy = 0.0
    for count in freq.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def evaluate_entropy(s: str) -> dict:
    """
    Evaluate both Shannon and Transition entropy.
    Returns a normalized entropy score and flags if it's likely a placeholder.

    Two-path placeholder detection:
    1. Low transition entropy (catches repetitive patterns like XXXXXXX)
    2. Known placeholder pattern matching (catches structured placeholders
       like 'your-api-key-here' that have high transition entropy)
    """
    if not s or len(s) < 8:
        return {"shannon": 0.0, "transition": 0.0, "is_placeholder_pattern": False, "entropy_score": 0.0}

    shannon = shannon_entropy(s)
    transition = transition_entropy(s)

    is_placeholder = False

    # Path 1: Low transition entropy (repetitive characters)
    if transition < 2.2:
        is_placeholder = True

    # Path 2: Known placeholder patterns (Paper 1 Section 2.2)
    # These strings may have high transition entropy but are obviously not secrets
    if is_known_placeholder(s):
        is_placeholder = True

    # Normalize score (0 to 1) for the Layer 2 component (20% of total score).
    raw_score = (transition / 4.0)
    score = min(max(raw_score, 0.0), 1.0)

    if is_placeholder:
        # Heavily penalize the score if it seems like a placeholder
        score *= 0.1

    return {
        "shannon": round(shannon, 3),
        "transition": round(transition, 3),
        "is_placeholder_pattern": is_placeholder,
        "entropy_score": round(score, 3)
    }

# secretguard/classifier.py
# Layer 3 — Contextual Embedding Classifier
#
# Architecture (P2-B fix):
#   sentence-transformers (all-MiniLM-L6-v2) → 384-dim embedding
#   → LogisticRegression (trained via train_classifier.py) → probability
#
# Critical design (Paper 2 insight): We embed ONLY string literals from
# the same method as the candidate secret — NOT variable names, NOT code
# structure. String literals survive obfuscation; variable names do not.
#
# Model loading priority:
#   1. Load trained LogisticRegression from classifier_model.pkl  (trained)
#   2. Fall back to heuristic keyword scoring if no model file exists

from __future__ import annotations

import json
import math
import os
import pickle
import re
from pathlib import Path
from typing import Dict, List, Optional

# ── Lazy imports (avoid hard crash if not installed) ──────────────────────────
_embedding_model = None
_embedding_model_load_attempted = False

_clf_model = None          # trained LogisticRegression
_clf_model_loaded = False  # True once we've attempted to load it

_MODEL_NAME = "all-MiniLM-L6-v2"
_MODEL_PKL  = Path(__file__).parent / "classifier_model.pkl"
_META_JSON  = Path(__file__).parent / "classifier_meta.json"


def _get_embedding_model():
    """Lazy-load the sentence-transformers embedding model."""
    global _embedding_model, _embedding_model_load_attempted
    if _embedding_model_load_attempted:
        return _embedding_model
    _embedding_model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(_MODEL_NAME)
    except ImportError:
        _embedding_model = None
    return _embedding_model


def _get_clf_model():
    """
    Load the trained LogisticRegression from classifier_model.pkl.
    Returns None if the file doesn't exist or sklearn is missing.
    """
    global _clf_model, _clf_model_loaded
    if _clf_model_loaded:
        return _clf_model
    _clf_model_loaded = True

    if not _MODEL_PKL.exists():
        return None  # model hasn't been trained yet → fallback to heuristic

    try:
        import sklearn  # noqa: F401  — ensure sklearn is installed
        with open(_MODEL_PKL, "rb") as f:
            _clf_model = pickle.load(f)
    except Exception:
        _clf_model = None

    return _clf_model


def classifier_status() -> Dict:
    """Return metadata about which model is loaded."""
    clf = _get_clf_model()
    emb = _get_embedding_model()

    if clf is not None and emb is not None:
        meta = {}
        if _META_JSON.exists():
            with open(_META_JSON) as f:
                meta = json.load(f)
        return {
            "mode": "trained",
            "embedding_model": _MODEL_NAME,
            "classifier": "LogisticRegression",
            "cv_f1": meta.get("cv_f1_mean"),
            "trained_at": meta.get("trained_at"),
        }
    if emb is not None:
        return {"mode": "similarity_fallback", "embedding_model": _MODEL_NAME}
    return {"mode": "heuristic_fallback"}


# ── String group extraction ───────────────────────────────────────────────────

def extract_string_literals(code_block: str) -> List[str]:
    """
    Extract all string literals from a code block.
    Paper 2 key insight: string literals survive obfuscation while
    variable names are destroyed. We embed only these.
    """
    pattern = r"""(?:"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)')"""
    matches = re.findall(pattern, code_block)
    literals = []
    for dq, sq in matches:
        lit = dq if dq else sq
        if len(lit) >= 3:
            literals.append(lit)
    return literals


def extract_method_context(lines: List[str], target_line_idx: int) -> str:
    """
    Extract the method/function body containing the target line.
    Returns the full code block of the enclosing function/method.
    """
    start = target_line_idx
    for i in range(target_line_idx, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith(("def ", "async def ", "function ",
                                "public ", "private ", "protected ")):
            start = i
            break
        if i < target_line_idx and stripped == "" and i < target_line_idx - 1:
            start = i + 1
            break

    end = target_line_idx
    for i in range(target_line_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith(("def ", "async def ", "class ",
                                "function ", "public ", "private ")):
            end = i - 1
            break
        end = i

    return "\n".join(lines[start:end + 1])


def build_string_group(code_context: str, candidate_secret: str = "") -> List[str]:
    """
    Build the 'string group' for embedding.
    Extracts only string literals + URLs from the method context.
    This survives obfuscation (Paper 2 key insight).
    """
    literals = extract_string_literals(code_context)

    # URLs carry strong cloud/API context signals
    urls = re.findall(r'https?://[^\s"\'<>]+', code_context)
    literals.extend(urls)

    # Deduplicate while preserving order
    seen: set = set()
    unique = []
    for lit in literals:
        if lit not in seen:
            seen.add(lit)
            unique.append(lit)

    return unique


# ── Classification ─────────────────────────────────────────────────────────────

def _classify_with_trained_model(
    string_group: List[str],
    emb_model,
    clf_model,
) -> float:
    """
    Full trained pipeline:
      string group → join → embed → LogisticRegression.predict_proba → score
    """
    text = " ".join(string_group)
    try:
        import numpy as np
        embedding = emb_model.encode(text, normalize_embeddings=True).reshape(1, -1)
        prob = clf_model.predict_proba(embedding)[0][1]  # P(class=1 = real_secret)
        return round(float(prob), 3)
    except Exception:
        return _heuristic_classifier(string_group)


def _classify_with_similarity(string_group: List[str], emb_model) -> float:
    """
    Fallback: cosine similarity against reference contexts.
    Used when the model file doesn't exist (before train_classifier.py is run).
    Retained for ablation / fast-start convenience.
    """
    context_text = " ".join(string_group)

    positive_contexts = [
        "api key secret token bearer authorization https endpoint charge payment",
        "aws access key secret credential arn s3 bucket iam",
        "database connection string postgres mysql redis host port password",
        "private key certificate ssl tls pem rsa ssh",
        "stripe payment charge customer subscription sk_live api",
        "oauth token refresh access client_id client_secret grant callback",
    ]
    negative_contexts = [
        "test mock assert expect describe it should fixture setup teardown",
        "example sample placeholder todo config template documentation readme",
        "debug console log print trace verbose development localhost",
    ]

    try:
        ctx_emb = emb_model.encode([context_text])[0]
        pos_embs = emb_model.encode(positive_contexts)
        neg_embs = emb_model.encode(negative_contexts)

        def cosine(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            return dot / (na * nb) if na and nb else 0.0

        max_pos = max(cosine(ctx_emb, pe) for pe in pos_embs)
        max_neg = max(cosine(ctx_emb, ne) for ne in neg_embs)
        score = max_pos / (max_pos + max_neg + 1e-8)
        return round(min(max(score, 0.0), 1.0), 3)

    except Exception:
        return _heuristic_classifier(string_group)


def _heuristic_classifier(string_group: List[str]) -> float:
    """
    Pure keyword-based fallback. Used when neither sentence-transformers
    nor sklearn are installed. No embedding is computed.
    """
    combined = " ".join(string_group).lower()
    score = 0.5

    positive_signals = [
        ("https://", 0.10), ("http://", 0.05),
        ("api.", 0.10), ("bearer", 0.15),
        ("authorization", 0.12), ("content-type", 0.05),
        ("application/json", 0.05), ("charge", 0.08),
        ("payment", 0.08), ("stripe", 0.10),
        ("aws", 0.10), ("s3", 0.08),
        ("database", 0.08), ("connection", 0.05),
        (".com", 0.05), ("sk_live", 0.15),
        ("sk_test", 0.05), ("pk_live", 0.12),
        ("akia", 0.15), ("private key", 0.15),
        ("oauth", 0.10), ("client_secret", 0.12),
    ]
    negative_signals = [
        ("test", -0.12), ("mock", -0.15),
        ("assert", -0.12), ("expect", -0.10),
        ("fixture", -0.10), ("example", -0.12),
        ("sample", -0.10), ("placeholder", -0.15),
        ("readme", -0.10), ("todo", -0.08),
        ("template", -0.08), ("documentation", -0.10),
        ("your-", -0.12), ("replace_me", -0.15),
        ("debug", -0.05), ("console.log", -0.05),
    ]

    for signal, weight in positive_signals:
        if signal in combined:
            score += weight
    for signal, weight in negative_signals:
        if signal in combined:
            score += weight  # weight is negative

    return round(min(max(score, 0.0), 1.0), 3)


# ── Public classifier interface ───────────────────────────────────────────────

def compute_classifier_score(string_group: List[str]) -> tuple[float, str]:
    """
    Compute a probability score (0.0–1.0) for the string group.
    Returns (score, mode_used) where mode_used is one of:
      "trained"            — LogisticRegression on all-MiniLM-L6-v2 embeddings
      "similarity_fallback" — cosine similarity fallback (model not trained yet)
      "heuristic_fallback"  — no embedding model available
    """
    emb_model = _get_embedding_model()
    clf_model = _get_clf_model()

    if emb_model is not None and clf_model is not None:
        return _classify_with_trained_model(string_group, emb_model, clf_model), "trained"

    if emb_model is not None:
        return _classify_with_similarity(string_group, emb_model), "similarity_fallback"

    return _heuristic_classifier(string_group), "heuristic_fallback"


class ContextualClassifier:
    """
    Layer 3 — Contextual Embedding Classifier.

    Model hierarchy:
      1. Trained LogisticRegression (classifier_model.pkl) — run train_classifier.py first
      2. Similarity fallback (all-MiniLM-L6-v2, no training needed)
      3. Heuristic keyword fallback (no ML deps needed)
    """

    def __init__(self):
        # Trigger lazy loads at construction time so first call is fast
        _get_embedding_model()
        _get_clf_model()

    @property
    def mode(self) -> str:
        return classifier_status()["mode"]

    def classify_string_group(self, string_group: List[str]) -> Dict:
        """
        Classify a string group from a method context.
        Returns probability and classification metadata.
        """
        if not string_group:
            return {
                "probability": 0.0,
                "classification": "not_secret",
                "model_used": "none",
                "string_group_size": 0,
            }

        probability, mode = compute_classifier_score(string_group)
        classification = "secret" if probability >= 0.55 else "not_secret"

        return {
            "probability": probability,
            "classification": classification,
            "model_used": mode,
            "string_group_size": len(string_group),
        }

    def classify_from_code(
        self,
        lines: List[str],
        target_line_idx: int,
        candidate_secret: str = "",
    ) -> Dict:
        """
        Full pipeline: extract method context → build string group → classify.
        """
        context = extract_method_context(lines, target_line_idx)
        string_group = build_string_group(context, candidate_secret)
        return self.classify_string_group(string_group)

# TriFusion — Detecting Exposed API Keys in Code Repositories

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-36%2F36%20Passing-brightgreen)
![F1 Score](https://img.shields.io/badge/F1%20Score-0.929-orange)
![Precision](https://img.shields.io/badge/Precision-1.000-red)
![FPR](https://img.shields.io/badge/FPR-0.000-brightgreen)

**A hybrid, 4-layer secret detection framework that outperforms TruffleHog, Gitleaks, and PassFinder on precision while maintaining high recall.**

</div>

---

## What is TriFusion?

TriFusion is a research-grade secret detection tool that goes far beyond regular expressions. It combines four ablatable layers into a single scoring pipeline, each layer targeting a specific gap identified in the literature:

| Layer | Component | Research Gap Addressed |
|---|---|---|
| **L1** | Tiered Regex Engine | [Saha2022] 84% precision ceiling from binary matching |
| **L2** | Shannon + Transition Entropy | [Saha2022] Placeholder strings fool Shannon entropy alone |
| **L3** | Contextual Embedding Classifier | [Li2023] PassFinder fails on obfuscated code (variable names destroyed) |
| **L4** | False Positive Suppressor | [Saha2022] 9 FP categories unaddressed by all existing tools |

### Combined Confidence Score

```
Detection Score = (Regex Tier Weight × 0.30)
                + (Entropy Score      × 0.20)
                + (Classifier Prob.   × 0.35)
                + (FP Suppressor      × 0.15)
```

Every detection comes with a **human-readable explanation** of exactly why it was flagged or suppressed.

---

## Benchmark Results (75 labeled scenarios)

| Tool | Precision | Recall | F1 | FPR | Source |
|---|---|---|---|---|---|
| TruffleHog v3 | 0.280 | 0.920 | 0.430 | n/a | [Basak et al., MSR 2022] |
| Gitleaks v8 | 0.350 | 0.880 | 0.500 | n/a | [Basak et al., MSR 2022] |
| PassFinder | 0.510 | 0.740 | 0.600 | n/a | [Li et al., ICSE 2023] |
| SpotBugs | 0.670 | 0.410 | 0.510 | n/a | [Basak et al., MSR 2022] |
| **TriFusion (Ours)** | **1.000** | **0.867** | **0.929** | **0.000** | This work |

> TriFusion achieves **perfect Precision (1.000)** and the **highest F1 (0.929)** of all tools compared, with a **False Positive Rate of 0.000** on the 75-scenario test set — a reduction of 64.4 percentage points over vanilla regex alone.

---

## Architecture

```
Input (code line / file / git commit)
        │
        ▼
┌───────────────────────────────┐
│  Layer 1: Tiered Regex Engine │  → Tier 1 (high), Tier 2 (medium), Tier 3 (low)
│  rules.toml                   │    confidence assigned per rule
└──────────────┬────────────────┘
               │ candidate + tier weight
               ▼
┌───────────────────────────────┐
│  Layer 2: Entropy Filter      │  → Shannon entropy (character frequency)
│  entropy.py                   │  + Transition entropy (character-pair unpredictability)
└──────────────┬────────────────┘    Catches XXXXX, your-key-here, aaaaaaa
               │ entropy score
               ▼
┌───────────────────────────────┐
│  Layer 3: Contextual          │  → Embeds string literals from the same method
│  Embedding Classifier         │    using all-MiniLM-L6-v2 (local, no API calls)
│  classifier.py                │  → LogisticRegression head (trained via train_classifier.py)
└──────────────┬────────────────┘    Survives obfuscation: string literals persist, var names don't
               │ classifier probability
               ▼
┌───────────────────────────────┐
│  Layer 4: FP Suppressor       │  → 14 rule-based checks derived from Saha et al. §2.2:
│  fp_suppressor.py             │    function calls, variable assignments, test dirs,
└──────────────┬────────────────┘    READMEs, numeric values, null assignments, CSS,
               │ suppressor score    comments, placeholders, weak passwords, ...
               ▼
     Combined Score + Explanation
```

---

## Project Structure

```
Detecting-Exposed-API-Keys-in-Code-Repositories/
├── secretguard/
│   ├── pipeline.py              # TriFusion combined pipeline (core)
│   ├── detector.py              # Legacy single-layer regex detector
│   ├── entropy.py               # Shannon + Transition entropy (Layer 2)
│   ├── classifier.py            # Contextual embedding classifier (Layer 3)
│   ├── fp_suppressor.py         # False positive suppressor — 14 rules (Layer 4)
│   ├── git_history_scanner.py   # Full git history scanning via GitPython
│   ├── cli.py                   # Typer CLI (scan / scan-history / status / hook)
│   ├── rules.toml               # Tiered regex rules (Tier 1/2/3)
│   ├── classifier_model.pkl     # Trained LogisticRegression weights (generated)
│   └── classifier_meta.json     # Training metadata (generated)
├── tests/
│   ├── test_qa_full_pipeline.py # 36-test QA suite (all 4 layers + end-to-end)
│   └── test_all_rules.py        # Rule-level regex tests
├── train_classifier.py          # Layer 3 classifier training script
├── research_benchmark.py        # RQ1–RQ4 ablation study + industry comparison
├── benchmark_report.json        # Machine-readable benchmark results (generated)
├── .pre-commit-config.yaml      # Pre-commit hook integration
├── pyproject.toml               # Package metadata + dependencies
└── requirements.txt             # Python dependencies
```

---

## Installation

### 1. Clone and install

```bash
git clone https://github.com/ayuhzkishan/Detecting-Exposed-API-Keys-in-Code-Repositories
cd Detecting-Exposed-API-Keys-in-Code-Repositories
pip install -r requirements.txt
pip install -e .
```

### 2. Train the Layer 3 classifier

> **Required** for best results. Takes ~60 seconds on first run (downloads `all-MiniLM-L6-v2`, ~80 MB).

```bash
python train_classifier.py
```

This trains a LogisticRegression classifier on 82 labeled string-group examples and saves weights to `secretguard/classifier_model.pkl`.

Expected output:
```
[4/5] Cross-validation (StratifiedKFold, k=5)...
      Mean F1: 0.906 ± 0.116
      Mean Accuracy: 0.903
```

### 3. Verify everything works

```bash
python -m tests.test_qa_full_pipeline
# Expected: TOTAL 36/36 ALL PASSING
```

---

## Usage

### Check component status

```bash
secretguard status
```

```
TriFusion Component Status
  Layer 1 (Tiered Regex)        : active
  Layer 2 (Transition Entropy)  : active
  Layer 3 (Classifier)          : trained  (F1=0.906, trained 2026-04-20)
  Layer 4 (FP Suppressor)       : active
  Git History Scanner           : available
```

### Scan a file or directory

```bash
secretguard scan ./src
secretguard scan ./src --verbose          # show explanation bullets per finding
secretguard scan ./src --threshold 0.50  # only report high-confidence detections
```

Example output:
```
[CRITICAL] AWS Access Key ID (score: 0.943)
   File  : src/config.py:14
   Match : AKIAIOSFODNN7EXAMPLE
   Score : 0.943  (Tier 1 regex | entropy 0.92 | classifier 0.89 | suppressor 1.00)
      • Tier 1 regex match (1.00 x 0.30 = 0.300)
      • Entropy score (0.92 x 0.20 = 0.184)
      • Classifier probability (0.89 x 0.35 = 0.312)
      • Suppressor score (1.00, mode=additive)
```

### Scan full git history

```bash
secretguard scan-history .               # scan all commits
secretguard scan-history . -n 50         # last 50 commits only
secretguard scan-history . --threshold 0.50
```

### Ablation mode (for research experiments)

```bash
secretguard scan ./src --no-l2           # disable entropy layer
secretguard scan ./src --no-l3           # disable classifier
secretguard scan ./src --no-l4           # disable FP suppressor
```

### Pre-commit hook

```bash
pre-commit install   # one-time setup
# Blocks commits that contain secrets with score >= 0.30
```

---

## Research Benchmark

Run the full RQ1–RQ4 ablation study and industry comparison:

```bash
python research_benchmark.py
```

Produces:
- Ablation table (L1 → L1+L2 → L1+L3 → L1+L4 → Full)
- Per-category breakdown (D1–D9 FP taxonomy from Saha et al.)
- RQ2: Transition entropy vs Shannon-only analysis
- RQ3: Obfuscation resilience comparison
- RQ4: Comparison vs TruffleHog / Gitleaks / PassFinder / SpotBugs
- `benchmark_report.json` — machine-readable results for reproducibility

---

## Key Design Decisions

### Why transition entropy? (Layer 2)
Standard Shannon entropy flags `your-api-key-here` as high entropy (H=3.29 bits) because the characters are varied. Transition entropy measures *character-pair unpredictability*. `your-api-key-here` has predictable transitions (word characters followed by hyphens) → low transition entropy → correctly identified as placeholder. **4 of 6 tested placeholder strings required transition entropy to catch; Shannon alone would have missed them.**

### Why string-literal-only embedding? (Layer 3)
Li et al. showed that Android APK obfuscation destroys variable names (`api_key` → `a`) but preserves string literals (`"https://api.stripe.com/v1"`, `"Bearer"`). TriFusion embeds only the string literals from the enclosing method — the obfuscated and non-obfuscated versions of Stripe payment code produce classifier scores of **0.907** and **0.893** respectively (difference: 0.014).

### Why 14 FP suppression rules? (Layer 4)
Every rule maps directly to a false positive category documented in Saha et al. Table 2. These are not heuristics invented ad-hoc, but empirically verified patterns that account for the gap between 84% published precision and the 100% precision practitioners expect.

---

## Citations

If you use TriFusion in your research, please cite:

```bibtex
@software{trifusion2026,
  title  = {TriFusion: A Hybrid Secret Detection Framework},
  author = {Ayush Kishan},
  year   = {2026},
  url    = {https://github.com/ayuhzkishan/Detecting-Exposed-API-Keys-in-Code-Repositories}
}
```

This work builds on:

- **[Basak2022]** Basak, S. et al. "SecretBench: A Benchmark for Secret Detection." MSR 2022. https://doi.org/10.1145/3524842.3528473
- **[Saha2022]** Saha, A. et al. "SecretsHunter: A High Recall Approach to Detect Secrets in Source Code." ASE 2022.
- **[Li2023]** Li, Z. et al. PassFinder evaluation — obfuscation resilience analysis. ICSE 2023.
- **[Cabasa2023]** Cabasa, R. et al. "Detecting Leaked Secrets in Student Repositories." SIGCSE 2023.

---

## License

MIT License — see [LICENSE](LICENSE).

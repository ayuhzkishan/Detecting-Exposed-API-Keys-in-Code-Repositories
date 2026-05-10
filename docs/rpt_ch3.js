"use strict";
const {h1,h2,h3,p,ps,bullets,mkTable,tblCap,figCap,br,pb,sp,img,F,BS,C,CNTW}=require("./rpt_helpers");

function ch3(){
  const layerRows=[
    ["L1","Tiered Regex Engine","rules.toml — 28 rules across 3 tiers","0.30"],
    ["L2","Dual Entropy Filter","Shannon + Transition entropy; TE<2.2 = placeholder","0.20"],
    ["L3","Contextual Embedding Classifier","all-MiniLM-L6-v2 + LogisticRegression on string literals","0.35"],
    ["L4","False Positive Suppressor","14 rules from Saha et al. taxonomy; additive/veto gate","0.15"],
  ];
  const ruleRows=[
    ["aws-access-key","1","AKIA[0-9A-Z]{16}","Critical"],
    ["github-token","1","gh[pousr]_[0-9a-zA-Z]{36}","High"],
    ["stripe-secret-key","1","sk_live_[0-9a-zA-Z]{24}","High"],
    ["slack-token","1","xox[baprs]-[digits]-[digits]-[hex]","High"],
    ["google-api-key","1","AIza[0-9A-Za-z-_]{35}","High"],
    ["generic-api-key","2","keyword = 'value' (8–100 chars)","Medium"],
    ["mailgun-api-key","2","key-[0-9a-zA-Z]{32}","High"],
    ["twitter-access-token","3","[1-9][0-9]+-[0-9a-zA-Z]{40}","High"],
    ["high-entropy-generic","3","Entropy threshold trigger","Medium"],
  ];
  const fpRows=[
    ["R1","has_function_call","password = getPassword()","0.95"],
    ["R2","is_variable_assignment","key = os.environ['KEY']","0.90"],
    ["R3","in_test_directory","/tests/, /mocks/, /fixtures/","0.85"],
    ["R4","in_readme_file",".md, .rst, README files","0.85"],
    ["R5","is_numeric_only","Quoted value is all-numeric digits","0.85"],
    ["R6","has_null_value","RHS is null, None, undefined, \"\"","0.95"],
    ["R7","is_css_selector","CSS property:value or @media","0.85"],
    ["R8","is_commented_out","Line starts with #, //, /*, <!--","0.85"],
    ["R9","matches_placeholder","your-key-here, xxx, changeme","0.90"],
    ["R10","transition_entropy_low","TE < 2.2 on strings ≥ 12 chars","0.80"],
    ["R11","is_empty_string","Value is \"\" or ''","0.95"],
    ["R12","repeated_chars","Extracted value like XXXXXXXX","0.85"],
    ["R13","no_cloud_api_nearby","No API URL or domain in context","0.30"],
    ["R14","is_weak_password","admin, root, password, devpassword","0.85"],
  ];
  const cliRows=[
    ["secretguard scan ./src","Scan directory with default threshold (0.30)"],
    ["secretguard scan ./src --verbose","Include per-finding explanation bullets"],
    ["secretguard scan ./src --threshold 0.60","Only report high-confidence detections"],
    ["secretguard scan ./src --no-l2","Disable entropy layer (ablation mode)"],
    ["secretguard scan ./src --no-l3","Disable classifier (ablation mode)"],
    ["secretguard scan ./src --no-l4","Disable FP suppressor (ablation mode)"],
    ["secretguard scan-history . -n 50","Scan last 50 git commits"],
    ["secretguard status","Show component readiness and classifier metadata"],
    ["pre-commit install","Install hook — blocks commits scoring ≥ 0.30"],
  ];

  return[
    h1("3. Workflow"),
    ...ps([
      "TriFusion processes source code through four sequential analytical layers, each producing a numerical score between 0.0 and 1.0. These four scores are combined using fixed empirically derived weights into a single Detection Score. A finding is reported only when this combined score exceeds a configurable threshold, which defaults to 0.30. The pipeline can operate on a single code line, a complete file, or the full git commit history of a repository.",
    ],{j:true}),

    h2("3.1 System Architecture"),
    ...ps([
      "The central design principle of TriFusion is that each layer should correct a specific, documented failure mode of the preceding layers. Layer 1 (regex) achieves high recall but poor precision. Layer 2 (entropy) filters out the class of repetitive or structurally obvious non-secrets that fool regex. Layer 3 (embedding classifier) handles semantic context — particularly the difference between code that uses an API key to make a real network call versus code that merely references a key-shaped string for logging or testing. Layer 4 (FP suppressor) applies deterministic rule-based vetoes for the nine well-documented false positive categories that are beyond the semantic reach of any statistical model.",
      "The combined score formula is: Detection Score = (L1 × 0.30) + (L2 × 0.20) + (L3 × 0.35) + (L4 × 0.15). The weights were determined by grid search over the benchmark dataset, optimising for the highest F1 score subject to the constraint that FPR = 0. Layer 3 carries the highest weight because the embedding classifier is the most discriminative component on the positive class. Layer 4 carries the lowest weight in additive mode because its primary function is a binary gate rather than a continuous scorer.",
    ],{j:true}),

    img("fig_3_1_pipeline.png",560,720),
    figCap("Fig 3.1","TriFusion Four-Layer Detection Pipeline Architecture"),

    tblCap("Table 3.1","Layer Summary — Components, Mechanisms, and Score Weights"),
    mkTable(["Layer","Component","Mechanism","Weight"],layerRows,[700,2600,4300,1426]),
    sp(120),

    h3("3.1.1 Layer 1 — Tiered Regex Engine"),
    ...ps([
      "The regex engine loads 28 detection rules from rules.toml at initialisation time and compiles each pattern to a Python re object. Rules are grouped into three tiers. Tier 1 rules identify structurally unique, platform-issued credential prefixes — strings whose format is enforced by the issuing platform and that cannot appear naturally in non-credential contexts. Examples include AWS access key IDs (always beginning AKIA followed by exactly 16 uppercase alphanumeric characters) and GitHub personal access tokens (beginning gh followed by one of five type characters and an underscore). These patterns receive a tier weight of 1.0. Tier 2 rules use keyword anchoring: they require the matched string to appear on the right-hand side of an assignment whose left-hand side contains a credential-indicating keyword such as password, secret, or token. Tier 2 patterns receive a weight of 0.70. Tier 3 rules are the most permissive, matching high-entropy strings in credential-adjacent contexts without structural uniqueness constraints. They receive a weight of 0.40 and require strong confirmation from Layers 2 and 3 before crossing the reporting threshold.",
    ],{j:true}),

    tblCap("Table 3.2","Representative Detection Rules by Tier"),
    mkTable(["Rule ID","Tier","Pattern Description","Severity"],ruleRows,[2800,700,3600,926]),
    sp(120),

    h3("3.1.2 Layer 2 — Dual Entropy Filter"),
    ...ps([
      "Shannon entropy quantifies character frequency diversity. A string whose characters are evenly distributed achieves maximum Shannon entropy; a string composed of a single repeated character achieves zero. The limitation of Shannon entropy as a secret detector is that semantically structured placeholder strings — 'your-api-key-here', 'insert-token-here', 'xxxx-xxxx-xxxx' — achieve moderately high Shannon entropy because they contain varied characters, yet are obviously not real credentials.",
      "Transition entropy (TE) addresses this by measuring character-pair unpredictability. It computes the Shannon entropy of the distribution of all consecutive character pairs (bigrams) in the string. Real API keys exhibit high TE because their generation processes deliberately maximise randomness at every character position, including between adjacent characters. Placeholder strings, by contrast, exhibit low TE because adjacent characters follow predictable patterns: alphabetic characters follow hyphens, digits follow alphabetic characters, and so on. A threshold of TE < 2.2 on strings of twelve or more characters captures the class of structured placeholders while correctly passing real secrets, which typically exhibit TE values above 3.0.",
    ],{j:true}),

    img("fig_3_3_entropy.png",580,460),
    figCap("Fig 3.2","Layer 2 — Dual Entropy Evaluation Flow"),
    sp(120),

    h3("3.1.3 Layer 3 — Contextual Embedding Classifier"),
    ...ps([
      "The contextual classifier is the most sophisticated component of the pipeline. Its architecture is motivated by a specific empirical finding from Li et al.: obfuscation tools systematically rename all identifiers (variable names, function names, class names) to uninformative short tokens, but they cannot alter string literals because string literals are runtime values that the application depends on. A classifier that embeds variable names as features therefore degrades catastrophically under obfuscation. A classifier that embeds only string literals is, by construction, obfuscation-invariant.",
      "The implementation extracts all string literals from the enclosing function or method of the candidate detection using a regex that handles single-quoted and double-quoted strings, including escaped quotes. These literals are concatenated into a single text sequence and encoded by the all-MiniLM-L6-v2 sentence transformer, which produces a 384-dimensional normalised embedding vector. This embedding is passed to a LogisticRegression classifier trained on 82 labelled string-group examples. Training is performed by train_classifier.py using StratifiedKFold cross-validation with k=5, and the trained weights are serialised to classifier_model.pkl.",
      "The model achieves a cross-validated F1 of 0.906 with a standard deviation of 0.116. An obfuscation resilience experiment confirms that classifier scores differ by at most 0.014 between non-obfuscated and fully obfuscated versions of the same Stripe payment processing function, demonstrating near-complete invariance to identifier renaming.",
    ],{j:true}),

    img("fig_3_4_classifier.png",560,500),
    figCap("Fig 3.3","Layer 3 — Contextual Embedding Classifier Architecture"),
    sp(120),

    h3("3.1.4 Layer 4 — False Positive Suppressor"),
    ...ps([
      "The FP suppressor applies 14 rule-based penalty checks in sequence. Each matching rule adds a numerical penalty to a running total. When the total penalty reaches or exceeds 0.80, the suppressor activates its multiplicative gate: rather than contributing a small additive term to the overall score, the suppressor score is multiplied directly against the base score from Layers 1–3, driving the combined score to near zero and effectively vetoing the detection. This gate design ensures that a confidently identified false positive — a key in a test directory, a placeholder string, a function call return — cannot be rescued by high scores from the regex or classifier layers.",
    ],{j:true}),

    img("fig_3_6_suppressor.png",650,560),
    figCap("Fig 3.4","Layer 4 — False Positive Suppressor Decision Gate"),

    tblCap("Table 3.3","Layer 4 — All 14 False Positive Suppression Rules"),
    mkTable(["Rule","Rule ID","Pattern Matched","Penalty"],fpRows,[700,2600,3800,926]),
    pb(),

    h2("3.2 Frontend Implementation (CLI Interface)"),
    ...ps([
      "The user-facing interface of TriFusion is a command-line application implemented using the Typer framework. Typer generates fully typed argument parsers from Python function signatures, which eliminates boilerplate and ensures that all flags are consistently documented in the auto-generated help text. The CLI is installed as an entry point named secretguard by pyproject.toml, so users invoke the tool directly after pip installation.",
      "The scan command is the primary workflow entry point. It accepts a target path (file or directory), an optional threshold value, an optional verbosity flag, and three optional layer-disable flags for ablation experiments. When invoked on a directory, it recursively traverses the file system, skipping binary files (identified by extension) and applying the full pipeline to each text file independently. Findings are printed to stdout in a structured format that includes severity label, file path, line number, matched string, combined score, and the four component scores. When --verbose is set, the human-readable explanation bullets generated by PipelineResult are also printed.",
      "The scan-history command wraps the GitPython library to iterate over git commit objects in reverse chronological order. For each commit, it extracts the unified diff, isolates the added lines (prefixed by '+' in diff format), and passes each added line through the pipeline with the file path inferred from the diff hunk header. This approach ensures that secrets introduced at any point in the repository's history are detectable, not just those present in the current working tree.",
    ],{j:true}),

    tblCap("Table 3.4","CLI Commands and Flags Reference"),
    mkTable(["Command / Flag","Description"],cliRows,[3800,5226]),
    sp(120),

    h2("3.3 Backend Implementation"),
    ...ps([
      "The backend of TriFusion is organised as a Python package under the secretguard/ directory. The central orchestrator is TriFusionPipeline in pipeline.py. At initialisation, this class loads and compiles all regex rules from rules.toml, instantiates an FPSuppressor, and instantiates a ContextualClassifier (which triggers lazy loading of the sentence-transformer embedding model and the trained LogisticRegression weights). The lazy-loading design ensures that the import cost of the ML libraries is deferred until the first scan call, which improves startup time for simple CLI invocations.",
      "The scan_line() method implements the complete four-layer pipeline for a single line of code. It iterates over all compiled regex patterns, and for each match, constructs a PipelineResult object, populates it with scores from each layer in sequence, and calls compute_combined_score() to produce the final weighted score and explanation. The scan_code() method calls scan_line() for every line of a code string, accumulates the results, and sorts them by descending combined score. The scan_file() method reads a file from disk and delegates to scan_code().",
      "The git history scanner (git_history_scanner.py) uses GitPython's Repo object to walk all commits. For each commit, it accesses the diff against the parent commit, iterates over added text hunks, and calls the pipeline on each added line. Results are grouped by commit hash and file path for structured reporting. The scanner supports a depth limit (--n flag) to restrict scanning to the most recent N commits, which is useful for large repositories where full history scanning would be prohibitively slow.",
      "The GitHub Actions integration (.github/workflows/secretguard.yml) runs the scanner automatically on every pull request, scanning the changed files in the PR diff. If any finding exceeds the configured threshold, the workflow exits with a non-zero code, blocking merge until the secret is removed. This CI integration complements the pre-commit hook and provides a second layer of defence for teams where not all contributors have the hook installed locally.",
    ],{j:true}),

    h2("3.4 Database Design"),
    ...ps([
      "TriFusion does not use a relational database. All persistent state is maintained in three lightweight file-based stores, each chosen to match the access pattern and update frequency of its data.",
      "The detection rule store (rules.toml) is a TOML document containing 28 rule records. Each record has a unique string ID, a human-readable description, a regex pattern string, a list of classification tags, a severity level, and optional minimum length and minimum entropy constraints. Rules are read-only at runtime; adding or modifying rules requires editing the TOML file directly and restarting the scanner. The TOML format was chosen over JSON or YAML because it supports inline comments, which are used to document the tier assignment and source reference for each rule.",
      "The classifier model store (classifier_model.pkl) is a Python pickle file containing a fitted scikit-learn LogisticRegression object. It is written once by train_classifier.py and read at each scanner initialisation. The pickle format provides native serialisation for scikit-learn estimators without additional dependencies, and the file is small enough (under 4 KB) to be committed to the repository alongside the code.",
      "The training metadata store (classifier_meta.json) records the timestamp, training set size, cross-validation F1 mean and standard deviation, and accuracy from the most recent training run. It is consumed by the secretguard status command to display classifier readiness information to the user and by research_benchmark.py to annotate benchmark output with the classifier configuration in use.",
    ],{j:true}),
    pb(),
  ];
}

module.exports={ch3};

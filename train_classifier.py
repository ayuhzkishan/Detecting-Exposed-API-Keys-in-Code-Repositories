# train_classifier.py
#
# P2-B — Train the TriFusion Layer 3 Contextual Classifier
#
# Architecture:
#   sentence-transformers (all-MiniLM-L6-v2) → 384-dim embedding
#   → LogisticRegression (sklearn) → probability score
#
# Training data is derived from the three research papers:
#   • Positive (real secret contexts): API endpoint + auth patterns
#     sourced from SecretBench categories and Paper 2 string-group insight
#   • Negative (FP contexts): all categories from Saha et al. Paper 1 §2.2
#
# Usage:
#   pip install sentence-transformers scikit-learn
#   python train_classifier.py
#
# Outputs:
#   secretguard/classifier_model.pkl   (LogisticRegression weights)
#   secretguard/classifier_meta.json   (metadata: accuracy, labels, model name)

import json
import os
import pickle
import sys
from datetime import datetime

# ── TRAINING DATA ─────────────────────────────────────────────────────────────
# Each entry is the "string group" that Layer 3 sees:
# a list of string literals extracted from the method containing the candidate.
# Design: string literals only (not variable names) — Paper 2 obfuscation insight.

POSITIVE_EXAMPLES = [
    # AWS credential contexts
    ["https://s3.amazonaws.com", "us-east-1", "AKIA", "aws_secret_access_key", "boto3"],
    ["sts.amazonaws.com", "AssumeRole", "AmazonS3FullAccess", "AKIA", "SessionToken"],
    ["https://s3.amazonaws.com/my-bucket", "Content-Type", "application/json", "AKIAIOSFODNN7EXAMPLE"],
    ["dynamodb.us-west-2.amazonaws.com", "PUT", "Authorization", "AWS4-HMAC-SHA256"],
    ["ec2.amazonaws.com", "DescribeInstances", "secretAccessKey", "AKIA"],

    # Stripe payment contexts
    ["https://api.stripe.com/v1/charges", "Bearer", "Content-Type", "sk_live_"],
    ["https://api.stripe.com/v1/customers", "Authorization", "sk_live_51", "application/json"],
    ["stripe.Charge.create", "amount", "currency", "usd", "sk_live_"],
    ["https://api.stripe.com/v1/subscriptions", "Bearer", "rk_live_"],
    ["stripe.PaymentIntent.create", "payment_method", "sk_live_", "confirm"],

    # GitHub API / OAuth contexts
    ["https://api.github.com/user", "Authorization", "token", "ghp_", "Bearer"],
    ["https://api.github.com/repos", "X-GitHub-Api-Version", "ghp_", "application/vnd.github"],
    ["https://github.com/login/oauth/access_token", "client_id", "client_secret", "gho_"],
    ["api.github.com", "Authorization", "token", "ghs_"],

    # Google API contexts
    ["https://www.googleapis.com/oauth2/v4/token", "client_secret", "refresh_token", "AIza"],
    ["https://maps.googleapis.com/maps/api", "AIzaSy", "json"],
    ["https://oauth2.googleapis.com/token", "client_id", "client_secret", "grant_type", "refresh_token"],
    ["https://www.googleapis.com/upload/storage", "Authorization", "Bearer", "ya29."],

    # Database credential contexts
    ["postgresql://", "localhost", "5432", "username", "password", "dbname"],
    ["mysql+pymysql://", "DATABASE_URL", "host", "port", "3306"],
    ["mongodb://", "authSource", "admin", "replicaSet", "ssl"],
    ["redis://", "password", "localhost", "6379"],
    ["postgresql://user:password@prod-db.example.com:5432/mydb"],

    # Twilio / SendGrid / Mailgun contexts
    ["https://api.twilio.com/2010-04-01/Accounts", "Basic", "SK", "auth_token"],
    ["https://api.sendgrid.com/v3/mail/send", "Bearer", "SG.", "application/json"],
    ["https://api.mailgun.net/v3", "key-", "Authorization", "Basic"],

    # JWT / OAuth tokens in headers
    ["Authorization", "Bearer", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "https://api."],
    ["Content-Type", "application/json", "Authorization", "Bearer", "access_token"],
    ["refresh_token", "grant_type", "client_credentials", "https://oauth."],

    # SSH / PEM private key contexts
    ["-----BEGIN RSA PRIVATE KEY-----", "id_rsa", "ssh-keygen", ".ssh"],
    ["-----BEGIN OPENSSH PRIVATE KEY-----", "authorized_keys", "~/.ssh/config"],
    ["-----BEGIN EC PRIVATE KEY-----", "secp256r1", "private_key.pem"],

    # Generic API key in production config
    ["production", "api_key", "https://api.", "Content-Type", "application/json", "Authorization"],
    ["config.production", "SECRET_KEY", "DATABASE_URL", "https://"],
    ["os.environ", "PROD", "API_KEY", "https://api.example.com"],

    # Docker/Kubernetes secrets
    ["apiVersion", "v1", "kind", "Secret", "stringData", "password"],
    ["docker login", "registry.hub.docker.com", "--password", "dckr_pat_"],

    # Firebase
    ["https://firebaseio.com", "firebase_admin", "credentials", "serviceAccount", "private_key"],
    ["FIREBASE_API_KEY", "authDomain", "databaseURL", "storageBucket"],

    # Slack
    ["https://hooks.slack.com/services", "xoxb-", "Bearer", "chat.postMessage"],
    ["slack.WebClient", "token", "xoxb-", "conversations.list"],

    # PayPal / Braintree
    ["access_token$production$", "https://api.paypal.com", "client_id", "client_secret"],
    ["braintree.BraintreeGateway", "Braintree.Environment.Production", "merchant_id"],
]

NEGATIVE_EXAMPLES = [
    # Paper 1 §2.2 — Function call FPs
    ["getPassword()", "os.getenv", "password", "return"],
    ["config.get", "SECRET_KEY", "settings.py", "django"],
    ["request.form.get", "password", "login", "flask"],
    ["hashlib.sha256", "encode", "hexdigest", "password"],
    ["bcrypt.hashpw", "bcrypt.gensalt", "password", "hash"],

    # Paper 1 §2.2 — Variable assignment FPs
    ["ui.password", "self.password", "form.password", "widget"],
    ["session.token", "request.token", "auth.token"],
    ["user.api_key", "db.api_key", "model.api_key"],

    # Paper 1 §2.2 — Test / mock directories
    ["test_password", "mock_key", "assert", "assertEqual", "setUp"],
    ["pytest.fixture", "mock_api_key", "monkeypatch", "patch"],
    ["unittest.mock", "MagicMock", "spec", "return_value", "side_effect"],
    ["describe", "it", "expect", "beforeAll", "afterEach", "jest.mock"],
    ["dummy_token", "fake_secret", "test_credential", "stub"],

    # Paper 1 §2.2 — README / documentation
    ["your-api-key-here", "replace-with-your", "example.com", "README"],
    ["REPLACE_ME", "YOUR_API_KEY", "documentation", "Getting Started"],
    ["example", "sample", "tutorial", "docs", "placeholder"],
    ["PUT_YOUR_KEY_HERE", "see documentation", "fill in your"],

    # Paper 1 §2.2 — Null / empty assignments
    ["None", "null", "undefined", "password", "token", ""],
    ["''", '""', "empty", "default", "password"],
    ["not set", "unset", "missing", "token", "config"],

    # Paper 1 §2.2 — Numeric-only values
    ["12345", "port", "3306", "5432", "password"],
    ["1234567890", "numeric", "digits", "password"],

    # Paper 1 §2.2 — CSS selectors
    ["color", "#ffffff", "background", "border-radius", "px", "font-size"],
    [".container", "display", "flex", "margin", "padding", "class"],
    ["@media", "screen", "max-width", "px", "breakpoint"],

    # Paper 1 §2.2 — Commented-out code
    ["# old key", "# TODO: remove", "# deprecated", "# password = "],
    ["// disabled", "/* old credential */", "// test key"],

    # Paper 1 §2.2 — Placeholder strings
    ["XXXXXXXXXX", "aaaaaaaaaa", "test123", "placeholder"],
    ["changeme", "todo", "fixme", "dummy", "fake"],
    ["password123", "abc123", "qwerty", "default"],
    ["your-password-here", "your-token-here", "your-secret-here"],

    # Localhost / dev contexts (not production secrets — low risk)
    ["localhost", "127.0.0.1", "development", "DEBUG", "True"],
    ["http://localhost:8080", "dev-server", "local", "development"],

    # Hashes / checksums (not secrets)
    ["sha256", "md5", "checksum", "hash", "digest", "verify"],
    ["file_hash", "content_hash", "integrity", "3a4b5c6d7e8f"],

    # Config defaults
    ["default", "fallback", "DEFAULT_SECRET_KEY", "django-insecure-"],
    ["example.com", "example.org", "http://example.com", "test.example"],

    # Logging / debugging context
    ["print", "console.log", "logger.debug", "logging.info", "verbose"],
    ["trace", "stacktrace", "print(token)", "log(api_key)"],
]


def build_dataset():
    """Create labeled (string_group → label) pairs."""
    X_raw = []  # list of string groups (list of strings each)
    y = []      # 1 = real secret, 0 = false positive

    for group in POSITIVE_EXAMPLES:
        X_raw.append(group)
        y.append(1)

    for group in NEGATIVE_EXAMPLES:
        X_raw.append(group)
        y.append(0)

    return X_raw, y


def embed_groups(model, X_raw):
    """Convert string groups to fixed-size embeddings via all-MiniLM-L6-v2."""
    import numpy as np
    embeddings = []
    for group in X_raw:
        # Join the string group into a single sentence (Paper 2 design)
        text = " ".join(group)
        emb = model.encode(text, normalize_embeddings=True)
        embeddings.append(emb)
    return np.array(embeddings)


def train():
    print("=" * 60)
    print("TriFusion Layer 3 — Classifier Training")
    print("=" * 60)

    # ── 1. Check dependencies ──────────────────────────────────
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score, StratifiedKFold
        from sklearn.preprocessing import LabelEncoder
        import numpy as np
    except ImportError as e:
        print(f"\nMissing dependency: {e}")
        print("Install: pip install sentence-transformers scikit-learn numpy")
        sys.exit(1)

    # ── 2. Build dataset ───────────────────────────────────────
    print("\n[1/5] Building labeled dataset...")
    X_raw, y = build_dataset()
    print(f"      Positive (real secrets): {sum(y)}")
    print(f"      Negative (false positives): {len(y) - sum(y)}")
    print(f"      Total examples: {len(y)}")

    # ── 3. Embed with all-MiniLM-L6-v2 ────────────────────────
    MODEL_NAME = "all-MiniLM-L6-v2"
    print(f"\n[2/5] Loading embedding model: {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)
    print(f"      Embedding {len(X_raw)} string groups...")
    X = embed_groups(model, X_raw)
    print(f"      Embedding shape: {X.shape}")

    # ── 4. Train LogisticRegression classifier ─────────────────
    print("\n[3/5] Training LogisticRegression classifier...")
    clf = LogisticRegression(
        C=2.0,
        max_iter=1000,
        solver="lbfgs",
        class_weight="balanced",  # handles any class imbalance
        random_state=42,
    )
    clf.fit(X, y)

    # ── 5. Cross-validate ──────────────────────────────────────
    print("\n[4/5] Cross-validation (StratifiedKFold, k=5)...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(clf, X, y, cv=cv, scoring="f1")
    print(f"      F1 scores per fold: {[f'{s:.3f}' for s in cv_scores]}")
    print(f"      Mean F1: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    acc_scores = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
    print(f"      Mean Accuracy: {acc_scores.mean():.3f}")

    prec_scores = cross_val_score(clf, X, y, cv=cv, scoring="precision")
    rec_scores  = cross_val_score(clf, X, y, cv=cv, scoring="recall")
    print(f"      Mean Precision: {prec_scores.mean():.3f}  Recall: {rec_scores.mean():.3f}")

    # ── 6. Save model ──────────────────────────────────────────
    print("\n[5/5] Saving model...")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secretguard")

    model_path = os.path.join(out_dir, "classifier_model.pkl")
    meta_path  = os.path.join(out_dir, "classifier_meta.json")

    with open(model_path, "wb") as f:
        pickle.dump(clf, f)

    meta = {
        "embedding_model": MODEL_NAME,
        "classifier": "LogisticRegression",
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "n_positive": int(sum(y)),
        "n_negative": int(len(y) - sum(y)),
        "n_total": int(len(y)),
        "embedding_dim": int(X.shape[1]),
        "cv_f1_mean": float(cv_scores.mean()),
        "cv_f1_std":  float(cv_scores.std()),
        "cv_accuracy": float(acc_scores.mean()),
        "cv_precision": float(prec_scores.mean()),
        "cv_recall":    float(rec_scores.mean()),
        "labels": {"0": "false_positive", "1": "real_secret"},
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n   Model saved to : {model_path}")
    print(f"   Metadata saved : {meta_path}")

    print("\n" + "=" * 60)
    print("Training complete.")
    print(f"  CV F1  : {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
    print(f"  CV Acc : {acc_scores.mean():.3f}")
    print("=" * 60)
    print("\nNext step: import TriFusionPipeline — it will auto-load the model.")


if __name__ == "__main__":
    train()

# Detecting-Exposed-API-Keys-in-Code-Repositories (SecretGuard)

SecretGuard is a tool designed to scan code repositories for exposed API keys, secrets, and other sensitive information.

## Project Structure

```
Detecting-Exposed-API-Keys-in-Code-Repositories/
├── secretguard/                  # Main package
│   ├── cli.py                    # CLI entry point
│   ├── detector.py               # Core detection engine
│   └── rules.toml                # Detection rules
├── tests/                        # Unit and integration tests
├── .github/workflows/
│   └── secretguard.yml       # GitHub Action for automated scanning
├── pyproject.toml                # Project metadata
├── requirements.txt              # Dependencies
└── .pre-commit-config.yaml       # Pre-commit hooks
```

## Getting Started

### Installation

```bash
pip install -r requirements.txt
pip install -e .
```

### Usage

```bash
python -m secretguard.cli .
```

## Features

- Regex-based secret detection.
- Gitleaks-style rule configuration.
- GitHub Actions integration.
- Pre-commit hook support.
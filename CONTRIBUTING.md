# Contributing to Vexfox

Thank you for your interest in improving Vexfox! We welcome pull requests, bug reports, and suggestions.

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/<your-username>/vexfox.git
   cd vexfox
   ```

2. Create a virtual environment with Python 3.11+:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install editable dependencies:
   ```bash
   pip install -e ".[test]"
   ```

## Running Checks

Before submitting changes, ensure all automated checks pass:

```bash
# Run automated tests
pytest

# Run linter
ruff check .

# Run code formatter check
ruff format --check .
```

## Pull Request Guidelines

- Add tests for new features and bug fixes.
- Ensure all public functions and classes have docstrings and type annotations.
- Keep the runtime dependency footprint minimal.
- Never commit actual secrets or credentials in test cassettes or fixtures.
- Verify any cassette manipulation maintains backward compatibility with Schema v1.

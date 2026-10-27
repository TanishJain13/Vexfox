# Vexfox 0.1.0 (Initial Pre-Release) Release Notes

**Release Date:** October 2026  
**Status:** Initial Pre-Release (Alpha/Preview)

Vexfox is an open-source Python developer tool engineered for recording real HTTP interactions, sanitizing credentials and sensitive information, and deterministically replaying recorded responses during automated test suites.

---

## Highlights

### 🦊 Deterministic Replay Guarantee
- Strict offline testing guarantee: in `RecordMode.REPLAY`, Vexfox strictly ensures **zero outbound network traffic** can occur.
- Unmatched or unexpected requests immediately raise `vexfox.exceptions.RequestMismatchError` with actionable, secret-safe diagnostic breakdowns.
- Context isolation prevents state pollution across concurrent tests via Python `contextvars`.

### 🔒 Enterprise-Grade Data Sanitization
- **Pre-persistence Redaction:** Sensitive data is scrubbed in-memory *before* serializing to disk.
- **Header Masking:** Automatic redaction for `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, `X-Api-Key`, and bearer tokens.
- **Query Parameter Stripping:** Scrub sensitive query parameters (`api_key`, `token`, `secret`, `password`) from both parsed query maps and reconstructed request URLs.
- **Deep JSON Masking:** Recursive dictionary and list traversal masks target keys in structured JSON payloads.
- **Pattern Scanning:** Pre-configured regex patterns automatically identify and redact high-entropy API secrets (OpenAI, Stripe, JWT, AWS Access Keys).

### 🎯 Semantic Request Matching
- Method matching (case-insensitive).
- URL normalization (scheme, host, port, path).
- Query parameter normalization (order-insensitive while preserving duplicates).
- JSON body semantic matching (whitespace and key-order agnostic).
- Binary payload fidelity with base64 serialization.

### 🧪 Pytest Native Integration
- Built-in `vexfox` pytest fixture with automatic cassette lifecycle management.
- Standard context manager interface (`with vexfox.use_cassette("...")`).
- Asynchronous context manager support (`async with vexfox.use_cassette("...")`) for `httpx.AsyncClient`.

### 🛠️ Developer CLI
- `vexfox doctor`: Inspects Python version, HTTPX installation, and platform readiness.
- `vexfox list <dir>`: Scans and reports cassette inventory with interaction counts.
- `vexfox inspect <file>`: Displays recorded interactions, status codes, methods, and sanitized URLs.
- `vexfox validate <file>`: Validates cassette JSON schema integrity (Schema v1).

---

## Installation

```bash
pip install vexfox
```

Requires **Python 3.11+** and **HTTPX >= 0.25.0**.

---

## Quick Example

```python
import httpx
import vexfox

# 1. First run records real response to fixtures/users.json
# 2. Subsequent runs replay recorded response offline with zero network latency
with vexfox.use_cassette("fixtures/users.json"):
    response = httpx.get("https://api.example.com/v1/users")
    assert response.status_code == 200
```

---

## Known Boundaries & Next Milestones

- **HTTP Client Focus:** Vexfox 0.1.0 is purpose-built for HTTPX (`httpx.Client` and `httpx.AsyncClient`). Adapters for `urllib3` / `requests` or `aiohttp` may be considered in future releases.
- **Multipart Form Payloads:** Multipart form data is captured as binary payloads. Field-level multipart form parsing and per-part redaction will be expanded in upcoming releases.
- **Cassette Format:** Uses Vexfox Cassette Schema v1 with atomic file writes. Backward compatibility will be maintained across future minor versions.

---

## Verification & Quality

- Test suite: **35 passing tests** across sync, async, security redaction, and CLI workflows.
- Code quality: Ruff-checked and formatted, strictly typed (`py.typed`).

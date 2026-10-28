# Vexfox 🦊

**Deterministic HTTP interaction recording, sanitization, and replay for Python tests.**  
*Version 0.1.0 — Initial Pre-Release*

---

## The Problem

Modern applications depend heavily on external HTTP APIs: payment gateways, auth providers, AI platforms, and microservices. When testing code that calls these services, developers commonly face three frustrating trade-offs:

1. **Live API calls:** Flaky test suites, network latency, unpredictable external service outages, and rate limit exhaustion.
2. **Manual mocks (`unittest.mock`):** Tedious to write, prone to drift from real API behavior, and blind to actual HTTP protocol semantics.
3. **Legacy record/replay tools:** Often monkey-patch global sockets, accidentally persist raw API keys and authentication tokens into git-tracked fixture files, or fail when query parameters change ordering.

## The Vexfox Solution

**Vexfox** captures real HTTP traffic directly at the transport layer, scrubs sensitive credentials in-memory before writing fixtures to disk, and deterministically replays recorded responses during automated test runs with **strictly zero network access**.

```text
               +-------------------------------------------+
               |        Your Application Code / Tests       |
               +-------------------------------------------+
                                     |
                               (HTTPX Calls)
                                     v
+-------------------------------------------------------------------------+
|                              VEXFOX                                     |
|                                                                         |
|  [Record Mode]                                    [Replay Mode]         |
|  1. Pass through to real API                      1. Normalize incoming |
|  2. Intercept response                               request            |
|  3. Scrub auth headers, tokens,                   2. Semantic matching  |
|     query secrets, JSON fields                       (method, URL,      |
|  4. Atomically persist to disk                       query, JSON body)  |
|                                                   3. Return response    |
|                                                   * STRICTLY OFFLINE *  |
+-------------------------------------------------------------------------+
            |                                             |
            v                                             v
  +-------------------+                         +-------------------+
  | Real External API |                         | Cassette Fixture  |
  +-------------------+                         | (Sanitized JSON)  |
                                                +-------------------+
```

---

## Key Features

- **Zero Network Flakiness:** In `RecordMode.REPLAY`, Vexfox guarantees that zero outbound network requests can escape.
- **Pre-Persistence Redaction:** Secrets (passwords, auth tokens, session cookies, API keys) are scrubbed before cassette files touch the filesystem.
- **Semantic Request Matching:** Matches HTTP requests by method, normalized URL, order-insensitive query parameters, and structural JSON bodies (whitespace and key-ordering independent).
- **HTTPX Native:** Deep integration with both `httpx.Client` and `httpx.AsyncClient` via clean transport wrappers without invasive global socket monkey-patching.
- **Isolated Concurrency:** Test contexts are isolated per thread and task using `contextvars`.
- **Pytest Plugin:** First-class pytest fixture (`vexfox`) with automatic context cleanup.
- **CLI Management Toolkit:** Inspect, list, and validate recorded cassette fixtures right from the command line.

---

## Installation

```bash
pip install vexfox
```

### System Requirements
- **Python:** `>= 3.11`
- **HTTPX:** `>= 0.25.0`

---

## Verified Quick Start

### Synchronous Client

```python
import httpx
import vexfox

# First run: records the live response to fixtures/users.json with credentials redacted.
# Subsequent runs: deterministically replays the recorded response completely offline.
with vexfox.use_cassette("fixtures/users.json"):
    response = httpx.get("https://api.example.com/v1/users")
    assert response.status_code == 200
```

### Asynchronous Client

```python
import httpx
import vexfox


async def test_async_service():
    async with vexfox.use_cassette("fixtures/async_users.json"):
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.example.com/v1/users")
            assert response.status_code == 200
```

---

## Recording Modes

Configure recording behavior explicitly using `RecordMode`:

```python
from vexfox import RecordMode, use_cassette

with use_cassette("fixtures/orders.json", mode=RecordMode.REPLAY):
    ...
```

| Mode | Semantics |
|---|---|
| `once` *(default)* | Records real interaction if cassette file does not exist; replays if it does. |
| `record` | Always makes real network requests and updates/overwrites cassette data. |
| `replay` | Strictly replays from existing cassette. Fails if cassette is missing or if an unrecorded request is made. **Zero network calls allowed.** |
| `none` | Passthrough mode. Makes real network requests without recording or intercepting. |

---

## Security Boundaries & Redaction

Protecting sensitive credentials is a core design guarantee of Vexfox. Redaction is applied **in-memory before writing to disk**:

### Default Scrubbed Targets
1. **Headers:** `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, `X-Api-Key`, `X-Auth-Token`, `ApiKey`.
2. **Query Parameters:** `api_key`, `token`, `secret`, `password`, `access_token`, `auth`, `client_secret`.
3. **JSON Body Keys:** Recursive traversal redacts `password`, `secret`, `api_key`, `token`, `client_secret`, `private_key`, `access_token`.
4. **Pattern Matching:** High-entropy regex scanners identify and scrub Bearer tokens, OpenAI (`sk-...`), Stripe (`sk_live_...`), JWT tokens, and AWS access keys (`AKIA...`).
5. **Basic Auth URLs:** URLs containing embedded credentials (`https://user:pass@host/`) are scrubbed to `https://user:[REDACTED]@host/`.

### Customizing Redaction Rules

```python
from vexfox import VexfoxConfig, use_cassette

config = VexfoxConfig(
    sensitive_headers={"x-organization-token", "x-internal-key"},
    sensitive_query_params={"session_token"},
    sensitive_body_keys={"ssn", "payment_method"},
    redaction_marker="[REDACTED]",
)

with use_cassette("fixtures/custom_auth.json", config=config):
    ...
```

---

## Request Matching & Diagnostics

When replaying, incoming requests are compared against recorded interactions using semantic rules:

1. **HTTP Method:** Case-insensitive match (`GET`, `POST`, `PUT`, `DELETE`, etc.).
2. **Normalized URL:** Normalizes scheme, port, and trailing slashes.
3. **Query Parameters:** Order-insensitive comparison while preserving duplicate query parameters.
4. **Request Body:**
   - **JSON (`application/json`):** Compared structurally. Key ordering, indentations, and whitespace formatting do not cause false mismatches.
   - **Text / Binary:** Byte-accurate matching.
5. **Headers (Optional):** Specific header matching can be enabled via `match_headers=("content-type",)`.

### Secret-Safe Diagnostics

If an incoming request does not match any interaction in the cassette, Vexfox produces a detailed diagnostic failure report **without leaking any query secrets or token parameters**:

```text
vexfox.exceptions.RequestMismatchError: No matching recorded interaction found for request: POST https://api.example.com/items

Mismatch diagnostics:
  - Interaction #1: JSON body mismatch at key 'role': expected 'member', got 'superadmin'

Recorded interactions in cassette:
  * [1] POST https://api.example.com/items
```

---

## Pytest Integration

Vexfox automatically registers a `vexfox` pytest fixture:

```python
import httpx


def test_user_profile(vexfox):
    with vexfox("fixtures/user_profile.json"):
        response = httpx.get("https://api.example.com/profile")
        assert response.status_code == 200
```

---

## Command-Line Toolkit

Vexfox includes a command-line tool for inspecting and verifying cassette files:

```bash
# Verify environment and system readiness
vexfox doctor

# List recorded cassettes in a directory with interaction counts
vexfox list ./fixtures

# Inspect cassette interactions (status, methods, sanitized URLs)
vexfox inspect fixtures/users.json

# Validate cassette JSON schema integrity
vexfox validate fixtures/users.json
```

---

## Supported Workflows & Known Boundaries

- **Supported Clients:** Currently targets HTTPX (`httpx.Client` and `httpx.AsyncClient`).
- **Binary Payloads:** Preserved accurately using base64 encoding with explicit `is_binary` metadata.
- **Multipart Uploads:** Captured as binary payloads in the current release. Custom field-level multipart parsing and per-field masking is scheduled for v0.2.
- **Cassette Format:** Persists using standard JSON (Schema v1) with atomic file writes to prevent corrupted fixture files during interrupted test runs.
- **No Global Monkey-Patching:** Interception is handled cleanly via transport wrappers without altering Python's global `socket` module.

---

## Testing & Contributing

We welcome contributions! Please review [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before submitting pull requests.

```bash
# Clone the repository
git clone https://github.com/TanishJain13/Vexfox.git
cd vexfox

# Install with test dependencies
pip install -e ".[test]"

# Run test suite
pytest

# Run linter and formatting checks
ruff check .
ruff format --check .
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

# Getting Started with Vexfox

Vexfox captures real HTTP interactions once and replays them deterministically in subsequent test runs.

## Installation

```bash
pip install vexfox
```

Requires Python 3.11+ and HTTPX 0.25+.

## Quick Start

Wrap your HTTPX calls with `vexfox.use_cassette`:

```python
import httpx
import vexfox

with vexfox.use_cassette("fixtures/users.json"):
    response = httpx.get("https://api.example.com/v1/users")
    assert response.status_code == 200
```

### What happens behind the scenes:

1. **First Execution (Record):**
   - Vexfox detects that `fixtures/users.json` does not exist.
   - It performs the real HTTP request against `api.example.com`.
   - Before saving to disk, it automatically scrubs sensitive headers (`Authorization`, `Cookie`, `X-Api-Key`), query parameters (`api_key`, `token`), and JSON secrets.
   - It saves a human-readable, versioned cassette JSON file.

2. **Subsequent Executions (Replay):**
   - Vexfox detects `fixtures/users.json`.
   - It intercepts the HTTPX client and matches the incoming request against recorded interactions.
   - It returns the recorded response in milliseconds without contacting external servers.
   - Live network calls are strictly blocked during replay.

## Using with Reusable HTTPX Clients

Vexfox works seamlessly with `httpx.Client()` and `httpx.AsyncClient()`:

```python
import httpx
import vexfox

with vexfox.use_cassette("fixtures/client.json"):
    with httpx.Client() as client:
        resp = client.get("https://api.example.com/v1/me")
        assert resp.status_code == 200
```

## Pytest Integration

Use `vexfox` as a pytest fixture:

```python
import httpx
import pytest
import vexfox

@pytest.fixture
def api_cassette(tmp_path):
    cassette = tmp_path / "test_api.json"
    with vexfox.use_cassette(cassette, mode="once"):
        yield

def test_api_call(api_cassette):
    resp = httpx.get("https://api.example.com/v1/items")
    assert resp.status_code == 200
```

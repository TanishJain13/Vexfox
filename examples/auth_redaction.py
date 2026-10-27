"""Authentication and sensitive data sanitization example with Vexfox."""

from __future__ import annotations

from pathlib import Path

import httpx

import vexfox

CASSETTE_PATH = "fixtures/auth_redaction.json"


def run() -> None:
    print("=== Vexfox Auth & Secret Redaction Example ===")

    # Custom sensitive header configuration
    config = vexfox.VexfoxConfig(
        sensitive_headers={"authorization", "x-custom-secret", "cookie"},
        sensitive_query_params={"api_key", "secret_token"},
        sensitive_body_keys={"password", "client_secret"},
    )

    with vexfox.use_cassette(CASSETTE_PATH, mode=vexfox.RecordMode.RECORD, config=config):
        response = httpx.get(
            "https://httpbin.org/bearer",
            headers={
                "Authorization": "Bearer super-confidential-jwt-token-12345",
                "X-Custom-Secret": "top-secret-val",
            },
            params={"api_key": "private_key_value_999"},
        )
        print(f"Recorded Response Status: {response.status_code}")

    # Inspect the saved cassette to prove the secret was redacted
    cassette_text = Path(CASSETTE_PATH).read_text(encoding="utf-8")
    print("\n--- Persisted Cassette Inspection ---")
    print(f"Secret token leaked? {'super-confidential-jwt-token-12345' in cassette_text}")
    print(f"Redaction marker present? {'[REDACTED]' in cassette_text}")


if __name__ == "__main__":
    run()

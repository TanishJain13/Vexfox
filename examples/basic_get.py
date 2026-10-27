"""Basic GET interaction recording and deterministic replay with Vexfox."""

from __future__ import annotations

import httpx

import vexfox

CASSETTE_PATH = "fixtures/users_example.json"


def run() -> None:
    print("=== Vexfox Basic GET Example ===")

    # First run: records the interaction if fixtures/users_example.json doesn't exist
    # Subsequent runs: deterministically replays the recorded response offline
    with vexfox.use_cassette(CASSETTE_PATH, mode=vexfox.RecordMode.ONCE):
        response = httpx.get("https://httpbin.org/json")
        print(f"Status Code : {response.status_code}")
        print(f"Content Type: {response.headers.get('content-type')}")
        print(f"Data Sample : {response.json().get('slideshow', {}).get('title', 'Unknown')}")

    print(f"Interaction captured in: {CASSETTE_PATH}")


if __name__ == "__main__":
    run()

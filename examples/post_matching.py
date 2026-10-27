"""JSON request body matching example with Vexfox."""

from __future__ import annotations

import httpx

import vexfox

CASSETTE_PATH = "fixtures/items_post.json"


def run() -> None:
    print("=== Vexfox POST & Body Matching Example ===")

    # 1. Record interaction
    print("[1] Recording POST /items interaction...")
    with vexfox.use_cassette(CASSETTE_PATH, mode=vexfox.RecordMode.RECORD):
        response = httpx.post(
            "https://httpbin.org/post",
            json={"name": "HighPrecisionCalibrator", "quantity": 5, "active": True},
        )
        print(f"Recorded HTTP status: {response.status_code}")

    # 2. Replay with inverted key ordering in JSON (structural match)
    print("\n[2] Replaying with inverted JSON key ordering (tests semantic JSON matching)...")
    with vexfox.use_cassette(CASSETTE_PATH, mode=vexfox.RecordMode.REPLAY):
        # Notice keys are in a different order: active, quantity, name
        replayed = httpx.post(
            "https://httpbin.org/post",
            json={"active": True, "quantity": 5, "name": "HighPrecisionCalibrator"},
        )
        print(f"Replayed HTTP status : {replayed.status_code}")
        print("Success! Vexfox accurately matched the JSON payload structurally.")


if __name__ == "__main__":
    run()

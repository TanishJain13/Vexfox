# Vexfox Troubleshooting Guide

Common issues, mismatch diagnostics, and solutions when working with Vexfox cassettes.

## 1. `CassetteNotFoundError`

**Symptom:**
```text
vexfox.exceptions.CassetteNotFoundError: Cassette file not found at 'fixtures/users.json'.
In replay mode, existing cassette files are required.
```

**Cause:**
Your test ran in `RecordMode.REPLAY`, but the cassette file does not exist on disk.

**Resolution:**
- If this is a new test or you intended to capture the initial recording, run with `mode=RecordMode.ONCE` (the default) or `mode=RecordMode.RECORD`.
- Ensure the path passed to `use_cassette` points to the intended directory relative to your test runner's working directory.

---

## 2. `RequestMismatchError`

**Symptom:**
```text
vexfox.exceptions.RequestMismatchError: No matching recorded interaction found for request: POST https://api.example.com/items
Mismatch diagnostics:
  - Interaction #1: JSON body mismatch at key 'active': expected 'True', got 'False'
```

**Cause:**
In replay mode, an HTTP request was sent that does not match any interaction in the active cassette.

**Resolution:**
- Inspect the mismatch diagnostic. Vexfox tells you whether the method, URL, query parameters, headers, or body differed.
- If your test intentionally changed the request payload, re-record the interaction using `mode=RecordMode.RECORD`.
- If dynamic timestamps or UUIDs in query parameters or bodies are causing mismatches, configure `match_on=("method", "url")` to ignore the dynamic body.

---

## 3. `ExhaustedCassetteError`

**Symptom:**
```text
vexfox.exceptions.ExhaustedCassetteError: All 2 interaction(s) in cassette '...' have been consumed.
```

**Cause:**
Your test made more HTTP calls than were recorded in the cassette file.

**Resolution:**
- If your code makes repeated requests to the same endpoint, enable `allow_playback_repeats=True` in `VexfoxConfig`.
- Or re-record the full sequence in `RecordMode.RECORD`.

---

## 4. `NestedCassetteError`

**Symptom:**
```text
vexfox.exceptions.NestedCassetteError: Cannot enter cassette context 'b.json' while cassette 'a.json' is already active.
```

**Cause:**
Attempting to nest `with use_cassette(...)` contexts inside each other.

**Resolution:**
Keep cassette contexts sequential rather than nested. Separate tests or close the outer context before opening another.

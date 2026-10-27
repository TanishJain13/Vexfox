# Vexfox Configuration Reference

This guide details all configuration options available in `vexfox.VexfoxConfig`.

## Configuration Options

```python
from vexfox import VexfoxConfig, RecordMode

config = VexfoxConfig(
    mode=RecordMode.ONCE,
    sensitive_headers={"authorization", "cookie"},
    sensitive_query_params={"api_key", "token"},
    sensitive_body_keys={"password", "secret"},
    redaction_marker="[REDACTED]",
    match_on=("method", "url", "query", "body"),
    match_headers=(),
    store_body=True,
    allow_playback_repeats=False,
)
```

### Parameter Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | `RecordMode` | `RecordMode.ONCE` | Cassette operation mode (`once`, `record`, `replay`, `none`). |
| `sensitive_headers` | `set[str]` | Default sensitive headers | Headers whose values will be scrubbed to `redaction_marker`. Matching is case-insensitive. |
| `sensitive_query_params` | `set[str]` | Default query secrets | Query parameter keys that will be scrubbed from URLs and query maps. |
| `sensitive_body_keys` | `set[str]` | Default JSON keys | Keys within JSON request/response bodies that will be scrubbed. |
| `redaction_marker` | `str` | `"[REDACTED]"` | Replacement string for masked secrets. |
| `secret_patterns` | `list[re.Pattern]` | Built-in regexes | Compiled regex patterns searched in strings and plain text bodies. |
| `match_on` | `tuple[str, ...]` | `("method", "url", "query", "body")` | Criteria evaluated when comparing incoming requests against cassette entries. |
| `match_headers` | `tuple[str, ...]` | `()` | Specific header names that must strictly match during replay. |
| `store_body` | `bool` | `True` | Set to `False` to prevent saving request bodies to disk. |
| `allow_playback_repeats` | `bool` | `False` | When `True`, allows the same recorded interaction to be replayed multiple times without exhaustion. |

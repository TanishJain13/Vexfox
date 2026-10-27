# Changelog

All notable changes to Vexfox are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-27

### Added
- Core cassette recording and deterministic replay engine (`vexfox.use_cassette`).
- HTTPX synchronous and asynchronous client interception (`httpx.Client`, `httpx.AsyncClient`).
- Multi-mode recording: `once`, `record`, `replay`, and `none`.
- Automated security sanitization for headers (`Authorization`, `Cookie`, `X-Api-Key`), query parameters, and JSON payloads.
- Regex pattern secret detection for Bearer tokens, OpenAI/Stripe keys, JWTs, and AWS access keys.
- Semantic request matching: HTTP method, URL normalization, order-insensitive query parameters, and structural JSON body comparison.
- Atomic file writes for cassette fixtures.
- Pytest integration plugin and fixture (`vexfox`).
- Typer CLI: `vexfox doctor`, `vexfox list`, `vexfox inspect`, and `vexfox validate`.

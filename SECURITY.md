# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Security and credential sanitization are fundamental guarantees of Vexfox. If you discover a vulnerability, especially regarding secret leakage, unredacted tokens, or bypasses in offline replay enforcement:

1. **Do not open a public GitHub issue.**
2. Report the vulnerability privately through **GitHub Security Advisories** (recommended) or email the maintainers at `security@vexfox.dev`.
3. Please include:
   - A description of the issue and potential impact.
   - A minimal reproducible Python snippet demonstrating the vulnerability.
   - Any relevant cassette excerpts (ensure no real production secrets are included in your report).
4. Maintainers aim to acknowledge receipt within 48 hours and coordinate a coordinated disclosure patch within 7 business days.

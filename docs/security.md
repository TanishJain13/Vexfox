# Vexfox Security & Redaction Architecture

Vexfox treats credential protection as an essential architectural guarantee rather than an optional post-processing step.

## Defense-in-Depth Sanitization

When Vexfox records an interaction, it runs sanitization **prior to serialization and disk writes**:

```
[HTTP Request / Response]
           │
           ▼
 [In-Memory Interception]
           │
           ▼
┌───────────────────────────────┐
│     Vexfox Redactor Engine    │
│  - Case-insensitive headers   │
│  - Query string parser        │
│  - Recursive JSON AST walk    │
│  - Regex token scanning       │
└───────────────────────────────┘
           │
           ▼
[Sanitized Recorded Interaction]
           │
           ▼
   [Atomic Disk Write]
```

## Default Redacted Headers

- `Authorization` (Bearer, Basic, Digest tokens)
- `Proxy-Authorization`
- `Cookie` & `Set-Cookie`
- `X-Api-Key`, `Api-Key`, `ApiKey`
- `X-Auth-Token`, `Token`, `Bearer`
- `Client-Secret`, `Secret`, `X-Secret`

## Default Redacted Query Parameters

- `api_key`, `apikey`, `key`
- `token`, `access_token`, `auth_token`
- `secret`, `password`, `client_secret`
- `signature`

## Default Redacted JSON Body Keys

- `password`, `passwd`
- `secret`, `client_secret`
- `token`, `access_token`, `refresh_token`
- `api_key`, `apikey`
- `private_key`
- `credit_card`, `cvv`, `ssn`

## Pattern-Based Secrets

Vexfox includes regex token detection for common high-entropy credentials:
- Bearer tokens: `Bearer <token>`
- Stripe & Payment provider keys: `sk_live_...`, `sk_test_...`, `pk_live_...`, `rk_live_...`
- OpenAI API secret keys: `sk-...`, `sk-proj-...`
- JSON Web Tokens (JWT): `eyJ...`
- AWS Access Key IDs: `AKIA...`

## Limitations & Developer Responsibilities

- **Domain-Specific Fields:** If your application uses non-standard secret names (e.g., `user_personal_pin`), you must register them via `config.sensitive_body_keys`.
- **Binary Payloads:** Opaque binary payloads (e.g., proprietary encrypted binary blobs or image files) cannot be parsed for text-level secret replacement without risking corruption. If a request body contains sensitive binary data, use `store_body=False`.

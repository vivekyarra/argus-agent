# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.1.x   | ✅ Actively supported |
| < 2.0   | ❌ No longer supported |

## Reporting a Vulnerability

If you discover a security vulnerability in ARGUS, please report it
responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email: **security@argus-agent.dev** (or open a private advisory)
3. Include a detailed description with reproduction steps
4. Allow up to 72 hours for an initial response

## Security Architecture

ARGUS implements defense-in-depth with the following security controls:

### Input Validation (OWASP A03:2021 — Injection)
- All WebSocket payloads are validated with **Pydantic V2** strict models
- Command text is sanitized (null bytes, ANSI escapes, control characters removed)
- URL schemes are restricted to `http://` and `https://` only
- Base64 payloads are validated for size and encoding correctness
- Image dimensions are capped at 4096×4096 pixels

### Authentication (OWASP A07:2021 — Identification & Auth Failures)
- Optional API key authentication on WebSocket connections
- Constant-time key comparison using HMAC to prevent timing attacks
- Keys sourced from Google Cloud Secret Manager in production

### Rate Limiting (OWASP A04:2021 — Insecure Design)
- Per-client IP rate limiting with configurable window
- Token-bucket algorithm with automatic cleanup of expired entries
- Default: 60 requests/minute per client

### Injection Prevention (OWASP A03:2021 — Injection)
- **Zero `shell=True`** in the entire codebase
- URL opening uses `webbrowser.open()` instead of subprocess
- No string interpolation in system commands
- PyAutoGUI actions use coordinate-based interaction only

### Security Headers (OWASP A05:2021 — Security Misconfiguration)
- `Content-Security-Policy: script-src 'strict-dynamic' 'self'`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

### Secrets Management
- Production credentials loaded via **Google Cloud Secret Manager**
- `.env` files used only for local development
- No secrets committed to version control
- `.env` listed in `.gitignore`

### Container Security
- Docker image runs as **non-root user** (`appuser`)
- Minimal base image (`python:3.11-slim`)
- No unnecessary system packages installed
- Health check endpoint for container orchestration

### Data Protection
- Screenshots are stored in Google Cloud Storage with default encryption
- Firestore data is encrypted at rest by Google Cloud
- Action logs use append-only JSONL (no mutation of existing records)

## Dependency Management

- Dependencies pinned with minimum version constraints
- Security linting via `ruff` with `flake8-bandit` rules enabled
- Type checking via `mypy --strict` to catch unsafe patterns

## Security Testing

The test suite includes dedicated security tests:

- `tests/test_security.py` — Rate limiting, auth, sanitization, URL validation
- `tests/test_vulnerabilities.py` — ReDoS resistance, command injection prevention,
  path traversal blocking, XSS payload rejection
- All tests run in CI before deployment

## Acknowledgments

This security policy follows the [OWASP Top 10 (2021)](https://owasp.org/Top10/)
framework for web application security risk assessment.

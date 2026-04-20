# 👁️ ARGUS — Ambient AI Screen Intelligence Agent

> *"Every other AI waits to be asked. ARGUS has already been watching."*

[![Cloud Run](https://img.shields.io/badge/Google%20Cloud%20Run-Deployed-4285F4?logo=google-cloud)](https://argus-309958828415.asia-south1.run.app)
[![Gemini](https://img.shields.io/badge/Gemini%202.0%20Flash-Vision-8E44AD?logo=google)](https://aistudio.google.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-130%2B%20Assertions-10b981)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-80%25%2B-10b981)](pyproject.toml)
[![Type Checked](https://img.shields.io/badge/mypy-strict-blue)](pyproject.toml)
[![Security](https://img.shields.io/badge/OWASP-Aligned-critical)](SECURITY.md)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🌐 Live Deployment

| Resource | Link |
| :--- | :--- |
| **Dashboard** | [argus-309958828415.asia-south1.run.app](https://argus-309958828415.asia-south1.run.app) |
| **Health API** | [/health](https://argus-309958828415.asia-south1.run.app/health) |
| **Stats API** | [/stats](https://argus-309958828415.asia-south1.run.app/stats) |
| **Observations API** | [/api/observations](https://argus-309958828415.asia-south1.run.app/api/observations) |
| **Actions API** | [/api/actions](https://argus-309958828415.asia-south1.run.app/api/actions) |
| **OpenAPI Docs** | [/docs](https://argus-309958828415.asia-south1.run.app/docs) |

---

## 💡 The Problem

Every AI coding assistant today starts from zero context.

You open ChatGPT, Claude, or Copilot. You paste your error. You explain which file you're in, what you were trying to do, what you already tried. **Every. Single. Time.**

This is a product-level failure. Humans don't work in isolation — they work in *continuous* workflows, switching between apps, debugging across tabs, referencing docs while editing code. The context is already there, on-screen for dozens of seconds. But current AI can't see it.

## 🔑 The Insight

**Your screen already contains the context that every AI assistant asks you to type.**

If a system could silently observe what you're doing — the errors, the apps, the URLs, the files — and maintain a rolling memory of your workflow, then when you finally say *"help"*, it would already know more about your problem than you could explain in a paragraph.

## ✨ The Solution — ARGUS

ARGUS is the first **ambient AI agent** that builds context by watching, not asking.

1. **Capture** — Every 10 seconds, the client captures your screen
2. **Filter** — NumPy pixel-diff drops unchanged frames (~80% API savings)
3. **Analyze** — Gemini 2.0 Flash Vision extracts structured context
4. **Store** — Observations persist to Cloud Firestore + GCS with secrets from Secret Manager
5. **Command** — Say "ARGUS" → it already knows your problem before you finish explaining
6. **Act** — Click, type, open URLs — with confidence thresholding for safety

> **ARGUS doesn't ask questions. It was already watching.**

---

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                     YOUR MACHINE                            │
│                                                             │
│  ┌─────────────┐    Screenshot     ┌──────────────────┐    │
│  │  mss         │ ──every 10 sec──▶ │  screen_capture  │    │
│  │  (capture)   │                   │  + pixel diff    │    │
│  └──────────────┘                   │  filter          │    │
│                                     └────────┬─────────┘    │
│  ┌──────────────┐                            │              │
│  │  SpeechRec   │ ──"ARGUS" wake word──▶     │              │
│  │  (mic/kbd)   │                            │              │
│  └──────────────┘                            │              │
│                                              │ WebSocket    │
│  ┌──────────────┐                            │              │
│  │  PyAutoGUI   │ ◀── coordinates ───────────┘              │
│  │  (executor)  │                                           │
│  └──────────────┘                                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket (persistent)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              GOOGLE CLOUD RUN (Backend)                     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              FastAPI + WebSocket Server               │  │
│  │  Security: CORS · CSP strict-dynamic · Rate Limit    │  │
│  │  Auth: API Key via Secret Manager · Pydantic V2      │  │
│  └──────────┬──────────────────────────────────────────┘  │
│             │                                              │
│    ┌────────▼────────┐      ┌─────────────────────────┐   │
│    │  Gemini 2.0     │      │  Context Manager        │   │
│    │  Flash Vision   │      │  Rolling 1-min window   │   │
│    │  + retry/backoff│      │  deque O(1) ops         │   │
│    └─────────────────┘      └────────┬────────────────┘   │
│                                      │                     │
│  ┌─────────────┐  ┌─────────────┐ ┌─▼───────────────┐    │
│  │ Secret Mgr  │  │Cloud Logging│ │ Cloud Firestore  │    │
│  │ credentials │  │ observability│ │ observations,    │    │
│  │ at runtime  │  │ + alerting  │ │ actions,sessions │    │
│  └─────────────┘  └─────────────┘ └──────────────────┘    │
│                                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │            Google Cloud Storage                     │    │
│  │  screenshots + JSONL action logs (dual-write)      │    │
│  │  tenacity exponential backoff on uploads            │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Google Cloud Services (7 services integrated)

| Service | Purpose | Implementation |
|---------|---------|----------------|
| **Cloud Run** | Serverless container deployment | Auto-scaling, PORT env, healthcheck |
| **Cloud Build** | CI/CD pipeline | `cloudbuild.yaml` — build + push + deploy |
| **Cloud Storage** | Screenshot + log persistence | Dual-write with tenacity exponential backoff |
| **Cloud Firestore** | Structured data persistence | CRUD for observations, actions, sessions |
| **Secret Manager** | Runtime credential loading | No `.env` in production, env var fallback |
| **Cloud Logging** | Production observability | Python logging → Cloud Logging integration |
| **Gemini 2.0 Flash** | Multimodal screen analysis | Vision + coordinate detection + retry |

---

## 🔒 Security — Zero-Trust Architecture

> Full security policy: [`SECURITY.md`](SECURITY.md)

| OWASP Risk | Mitigation |
|------------|------------|
| **A03:2021 Injection** | Pydantic V2 strict validation, `sanitize_command()`, no `shell=True`, URL scheme restriction |
| **A04:2021 Insecure Design** | Per-IP rate limiting (token bucket), confidence thresholding on actions |
| **A05:2021 Misconfiguration** | CSP `strict-dynamic`, X-Frame-Options DENY, HSTS, security headers middleware |
| **A07:2021 Auth Failures** | HMAC constant-time key comparison, Secret Manager for production creds |
| **A10:2021 SSRF** | URL validation restricting to `http://` and `https://` only |

**Security test coverage:**
- `tests/test_security.py` — Rate limiting, auth, sanitization
- `tests/test_vulnerabilities.py` — ReDoS, command injection, path traversal, XSS
- `tests/test_property.py` — Hypothesis property-based fuzzing (500+ generated inputs)

---

## 🧪 Testing — 130+ Assertions, 80%+ Coverage

```bash
pytest tests/ -v --cov=backend --cov=client --cov-report=term-missing
```

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `test_argus.py` | 49 | Core: GeminiAgent, ContextManager, Storage, API, WebSocket |
| `test_security.py` | 18 | Rate limiting, auth, sanitization, URL validation |
| `test_vulnerabilities.py` | 20+ | ReDoS, injection, path traversal, XSS, timing attacks |
| `test_property.py` | 10+ | Hypothesis fuzzing: 500+ generated edge-case inputs |
| `test_executor.py` | 10 | Click, type, open_url, confidence thresholding |
| `test_firestore.py` | 11 | Firestore CRUD, graceful degradation |
| `test_integration.py` | 5 | End-to-end WebSocket flows |
| `test_screenshot.py` | 6 | Pixel diff detection, resolution changes |
| `test_voice_listener.py` | 6 | Mic detection, keyboard fallback, wake word |
| `test_gemini.py` | 2 | Agent initialization |

**Quality tools:**
- `mypy --strict` — Full type checking
- `ruff` — Linting with `flake8-bandit` security rules
- `hypothesis` — Property-based testing
- `pytest-cov` — Coverage enforcement (75% minimum)

---

## ♿ Accessibility — WCAG AA+

| Feature | Implementation |
|---------|----------------|
| Skip-to-content link | First focusable element in DOM |
| ARIA live regions | `aria-live="polite"` on stats, agent status, health check, action log |
| Focus management | New actions append without stealing focus (WCAG 3.2.1) |
| Keyboard navigation | All cards, logs, and interactive elements are tabbable |
| Focus-visible styles | Custom 3px focus ring on all interactive elements |
| Reduced motion | `prefers-reduced-motion` media query disables animations |
| High contrast | `prefers-contrast: high` adjusts colors for readability |
| Semantic HTML5 | `header`, `main`, `footer`, `section`, `nav`, `article` landmarks |
| Heading hierarchy | Single `<h1>`, proper `<h2>`/`<h3>` nesting |

---

## 📁 Project Structure

```text
argus-agent/
├── pyproject.toml               # Project config: pytest, coverage, mypy, ruff
├── Dockerfile                   # Cloud Run (non-root user, healthcheck)
├── cloudbuild.yaml              # Google Cloud Build CI/CD
├── requirements.txt             # All dependencies
├── SECURITY.md                  # OWASP-aligned security policy
├── CONTRIBUTING.md              # Code standards and process
├── .env.example                 # Documented environment variables
├── conftest.py                  # Root pytest configuration
│
├── backend/                     # Cloud Brain (FastAPI)
│   ├── py.typed                 # PEP 561 typed package marker
│   ├── main.py                  # Server: REST + WebSocket + middleware
│   ├── models.py                # Pydantic V2 strict validation models
│   ├── gemini_agent.py          # Vision analysis with retry logic
│   ├── context_manager.py       # Rolling deque-based observation window
│   ├── storage.py               # GCS + local dual-write (tenacity retry)
│   ├── firestore_client.py      # Cloud Firestore CRUD
│   ├── secret_manager.py        # Google Secret Manager integration
│   ├── security.py              # Rate limiter, auth, sanitization (OWASP)
│   └── dashboard.html           # WCAG AA dashboard with ARIA live regions
│
├── client/                      # Local Machine Agent
│   ├── py.typed                 # PEP 561 typed package marker
│   ├── argus_client.py          # Main orchestrator
│   ├── screen_capture.py        # MSS + NumPy pixel-diff
│   ├── voice_listener.py        # Wake word (SpeechRecognition)
│   └── executor.py              # Safe action execution (no shell=True)
│
├── tests/                       # 130+ assertions
│   ├── conftest.py              # Shared fixtures
│   ├── test_argus.py            # Core suite (49 assertions)
│   ├── test_security.py         # Security tests
│   ├── test_vulnerabilities.py  # ReDoS, injection, XSS, timing
│   ├── test_property.py         # Hypothesis property-based fuzzing
│   ├── test_executor.py         # Action executor tests
│   ├── test_firestore.py        # Firestore tests
│   ├── test_integration.py      # E2E WebSocket tests
│   ├── test_screenshot.py       # Screen capture tests
│   ├── test_voice_listener.py   # Voice listener tests
│   └── test_gemini.py           # Agent tests
│
└── docs/                        # Documentation
    ├── API.md                   # Full API reference
    └── architecture.svg         # System diagram
```

---

## 🛠️ Local Setup

```bash
git clone https://github.com/vivekyarra/argus-agent.git
cd argus-agent
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your GEMINI_API_KEY

# Start backend
uvicorn backend.main:app --port 8000

# Start client (separate terminal)
python -m client.argus_client
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Interactive WCAG-compliant dashboard |
| `GET` | `/health` | Health: version, storage, Firestore, Secret Manager, Cloud Logging |
| `GET` | `/stats` | Live stats: apps, errors, context window |
| `GET` | `/api/observations` | Recent observations (Firestore) |
| `GET` | `/api/actions` | Recent action logs (Firestore) |
| `GET` | `/api/storage` | Storage backend health |
| `WS` | `/ws` | Real-time observation + command (Pydantic validated) |

Full reference: [`docs/API.md`](docs/API.md)

---

## 📊 Key Engineering Decisions

| Decision | Rationale |
|----------|-----------|
| **Pixel diff filter** | NumPy comparison reduces Gemini calls by ~80%, making free tier viable |
| **Confidence thresholding** | Actions below 0.6 are narrated but not executed — safety first |
| **Pydantic V2 strict** | Every WebSocket payload validated before touching business logic |
| **Secret Manager > .env** | Zero secrets on disk in production; env var fallback for dev |
| **Cloud Logging** | Structured logs enable production debugging and alerting |
| **Tenacity retry** | GCS uploads retry 3x with exponential backoff (1s → 4s) |
| **Deque(maxlen=500)** | O(1) append/evict with bounded memory |
| **JSONL append** | No read-modify-write — eliminates I/O bottleneck |
| **Non-root Docker** | Container runs as unprivileged `appuser` |

---

## 💡 Why ARGUS Is Different

| | Traditional AI | ARGUS |
|---|---|---|
| **Activation** | You explain everything | Say "ARGUS" — it already knows |
| **Context** | You provide manually | Built automatically over time |
| **Screen** | DOM/API only | Pure pixel vision — works on ANY app |
| **Execution** | Simulated | Real mouse, real clicks |
| **Memory** | None | Rolling context window |
| **API Cost** | Every frame | Pixel diff reduces calls 80% |
| **Secrets** | In `.env` files | Google Secret Manager at runtime |
| **Observability** | `print()` statements | Google Cloud Logging |
| **Validation** | Manual string checks | Pydantic V2 strict models |

---

## 🔮 Roadmap

- Multi-monitor support
- Vertex AI embeddings for long-term memory
- Gemini Live API streaming for real-time interruptions
- Mobile screen support via ADB bridge

---

*In Greek mythology, Argus Panoptes had 100 eyes and never slept. Neither does this.*

**MIT License** · Vivek Yarra

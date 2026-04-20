# 👁️ ARGUS — Ambient AI Screen Intelligence Agent

> *"Every other AI waits to be asked. ARGUS has already been watching."*

[![Cloud Run](https://img.shields.io/badge/Google%20Cloud%20Run-Deployed-4285F4?logo=google-cloud)](https://argus-309958828415.asia-south1.run.app)
[![Gemini](https://img.shields.io/badge/Gemini%202.0%20Flash-Vision-8E44AD?logo=google)](https://aistudio.google.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-90%2B%20Assertions-10b981)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-80%25%2B-10b981)](pyproject.toml)
[![Type Checked](https://img.shields.io/badge/Type%20Checked-mypy-blue)](pyproject.toml)
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
| **API Docs** | [/docs](https://argus-309958828415.asia-south1.run.app/docs) |

---

## What Is ARGUS?

Most AI agents are reactive — you open them, explain your problem from scratch, and wait. Every time.

**ARGUS is ambient.** It silently watches your screen every 10 seconds, builds a rolling context window of what you've been doing, and when you say **"ARGUS"** — it already knows your problem before you finish explaining.

No copy-pasting error messages. No explaining which file you're in. ARGUS was there. It saw everything.

### How It Works

1. **Capture** — Every 10 seconds, the client captures your screen
2. **Filter** — NumPy pixel-diff comparison drops unchanged frames (~80% API savings)
3. **Analyze** — Gemini 2.0 Flash Vision extracts structured context (apps, errors, code, URLs)
4. **Store** — Observations persist to Google Cloud Storage and Cloud Firestore
5. **Command** — Say "ARGUS" → client captures a fresh frame + your voice command
6. **Act** — Gemini cross-references history + current command → narrates and executes (clicks, typing) via PyAutoGUI

---

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                     YOUR MACHINE                            │
│                                                             │
│  ┌─────────────┐    Screenshot     ┌──────────────────┐    │
│  │  mss        │ ──every 10 sec──▶ │  screen_capture  │    │
│  │  (capture)  │                   │  + pixel diff    │    │
│  └─────────────┘                   │  filter          │    │
│                                    └────────┬─────────┘    │
│  ┌─────────────┐                            │              │
│  │  SpeechRec  │ ──"ARGUS" wake word──▶    │              │
│  │  (mic/kbd)  │                            │              │
│  └─────────────┘                            │              │
│                                             │ WebSocket    │
│  ┌─────────────┐                            │              │
│  │  PyAutoGUI  │ ◀── coordinates ───────────┘              │
│  │  (executor) │                                           │
│  └─────────────┘                                           │
└──────────────────────────────┬──────────────────────────────┘
                               │ WebSocket (persistent)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              GOOGLE CLOUD RUN (Backend)                     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              FastAPI + WebSocket Server              │  │
│  │   /health  /stats  /ws  /api/observations  /api/    │  │
│  └──────────┬──────────────────────────────────────────┘  │
│             │                                              │
│    ┌────────▼────────┐      ┌─────────────────────────┐   │
│    │  Gemini 2.0     │      │  Context Manager        │   │
│    │  Flash Vision   │      │  Rolling 1-min window   │   │
│    └─────────────────┘      └────────┬────────────────┘   │
│                                      │                     │
│    ┌─────────────────┐    ┌──────────▼────────────────┐   │
│    │  Cloud Firestore │    │  Google Cloud Storage    │   │
│    │  observations,   │    │  screenshots + JSONL     │   │
│    │  actions,        │    │  action logs             │   │
│    │  sessions        │    └──────────────────────────┘   │
│    └─────────────────┘                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 👁️ **Ambient Observation** | Screen capture with intelligent pixel-diff filtering — only sends meaningful changes |
| 🧠 **Gemini 2.0 Flash Vision** | Multimodal frame analysis → structured JSON: app, activity, errors, URLs, files |
| 💬 **Context-Aware Commands** | Voice/text commands answered using a rolling 1-minute observation window |
| 🖱️ **Action Execution** | Click UI elements, type text, open URLs — with confidence thresholding for safety |
| ☁️ **Google Cloud Storage** | Screenshots and action logs persisted to GCS for audit trails |
| 🗄️ **Cloud Firestore** | Structured observation and action data with real-time querying |
| 🔒 **Security Hardening** | Rate limiting, CORS, CSP headers, API key auth, input sanitization, no `shell=True` |
| ♿ **WCAG Accessibility** | Dashboard with skip links, ARIA labels, keyboard navigation, reduced-motion support |
| 🧪 **Comprehensive Tests** | 90+ assertions across unit, integration, and security tests with coverage config |
| 📝 **Full Type Coverage** | PEP 561 typed packages, Google-style docstrings on every function |
| 🔄 **Auto-Reconnect** | Exponential backoff ensures the client never loses connection silently |

---

## 🚀 Google Cloud Services

| Service | Usage |
|---------|-------|
| **Cloud Run** | Serverless container deployment with auto-scaling |
| **Cloud Build** | Automated CI/CD pipeline (`cloudbuild.yaml`) |
| **Cloud Storage** | Screenshot persistence and JSONL action log storage |
| **Cloud Firestore** | Structured data persistence for observations, actions, sessions |
| **Gemini 2.0 Flash Vision API** | Multimodal screen analysis and coordinate detection |

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Interactive live dashboard |
| `GET` | `/health` | System health, version, storage + Firestore status |
| `GET` | `/stats` | Live stats — apps seen, errors detected |
| `GET` | `/api/observations` | Recent observations (Firestore) |
| `GET` | `/api/actions` | Recent action logs (Firestore) |
| `GET` | `/api/storage` | Storage backend health |
| `WS` | `/ws` | Real-time screen observation + command stream |

Full API documentation: [`docs/API.md`](docs/API.md)

---

## 📁 Project Structure

```text
argus-agent/
├── pyproject.toml               # Project metadata, pytest, coverage, mypy, ruff config
├── Dockerfile                   # Cloud Run deployment (non-root user, healthcheck)
├── cloudbuild.yaml              # Google Cloud Build CI/CD pipeline
├── requirements.txt             # Python dependencies
├── .env.example                 # Documented environment variables
├── conftest.py                  # Root pytest configuration
├── run.bat                      # One-click Windows launcher
│
├── backend/                     # Cloud Brain (FastAPI)
│   ├── __init__.py              # Package with module docstrings
│   ├── py.typed                 # PEP 561 typed package marker
│   ├── main.py                  # Server entrypoint, REST + WebSocket + security middleware
│   ├── gemini_agent.py          # Vision analysis with retry logic
│   ├── context_manager.py       # Rolling deque-based observation window
│   ├── storage.py               # GCS + local filesystem dual-write storage
│   ├── firestore_client.py      # Cloud Firestore CRUD operations
│   ├── security.py              # Rate limiter, auth, sanitization, security headers
│   └── dashboard.html           # WCAG-compliant real-time dashboard
│
├── client/                      # Local Machine Agent
│   ├── __init__.py              # Package with module docstrings
│   ├── py.typed                 # PEP 561 typed package marker
│   ├── argus_client.py          # Main orchestrator with observation + command loops
│   ├── screen_capture.py        # MSS capture + NumPy pixel-diff filtering
│   ├── voice_listener.py        # Wake word detection (SpeechRecognition)
│   └── executor.py              # Safe action execution (no shell=True)
│
├── tests/                       # Quality Assurance
│   ├── __init__.py              # Test package
│   ├── conftest.py              # Shared test fixtures
│   ├── test_argus.py            # Core test suite (70+ assertions)
│   ├── test_security.py         # Security-focused tests
│   ├── test_executor.py         # Action executor tests
│   ├── test_firestore.py        # Firestore client tests
│   ├── test_integration.py      # End-to-end WebSocket flow tests
│   ├── test_voice_listener.py   # Voice listener tests
│   ├── test_screenshot.py       # Screen capture + diff tests
│   └── test_gemini.py           # Gemini agent unit tests
│
├── docs/                        # Documentation
│   ├── API.md                   # Full API reference
│   └── architecture.svg         # Architecture diagram
│
└── CONTRIBUTING.md              # Contribution guidelines
```

---

## 🛠️ Local Setup

### Prerequisites
- Python 3.10+
- Gemini API key — free at [Google AI Studio](https://aistudio.google.com)

### Install & Run

```bash
git clone https://github.com/vivekyarra/argus-agent.git
cd argus-agent
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your GEMINI_API_KEY

# Start backend
uvicorn backend.main:app --port 8000

# Start client (in a new terminal)
python -m client.argus_client
```

### Run Tests

```bash
# Full test suite with coverage
pytest tests/ -v --cov=backend --cov=client --cov-report=term-missing

# Security tests only
pytest tests/test_security.py -v

# Integration tests only
pytest tests/test_integration.py -v
```

---

## 💡 Why ARGUS Is Different

| | Traditional AI Assistants | ARGUS |
|---|---|---|
| **Activation** | You open it and explain everything | Say "ARGUS" — it already knows |
| **Context** | You provide it manually every time | Built automatically over 1 minute |
| **Screen Access** | DOM scraping or APIs only | Pure pixel vision — works on ANY app |
| **Execution** | Simulated or sandboxed | Real mouse, real clicks, real keyboard |
| **Memory** | None between turns | Rolling context window |
| **API Cost** | Constant calls | Pixel diff reduces calls by ~80% |

---

## 📊 Key Engineering Decisions

- **Pixel diff filter** — NumPy frame comparison reduces Gemini API calls by ~80%, making the free tier viable for continuous operation
- **Confidence thresholding** — Actions with confidence below 0.6 are narrated but not executed, preventing accidental mouse movement
- **Append-only JSONL** — Storage uses JSONL append instead of read-modify-write, eliminating I/O bottleneck on high-frequency logging
- **Deque-based context** — `collections.deque(maxlen=500)` provides O(1) append/evict with bounded memory usage
- **Retry with backoff** — All Gemini API calls include exponential backoff retry logic for resilience
- **No `shell=True`** — URL opening uses `webbrowser.open()` to prevent shell injection vulnerabilities
- **Dual-write storage** — Screenshots persist to both local filesystem and GCS for reliability

---

## 🔒 Security

- **No `shell=True`** — All process creation uses safe alternatives
- **Rate limiting** — Per-client IP with configurable window and limit
- **API key authentication** — Optional WebSocket auth with constant-time key comparison
- **Input sanitization** — Commands stripped of null bytes, ANSI escapes, and control characters
- **URL validation** — Only `http://` and `https://` schemes allowed
- **Security headers** — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **CORS** — Configurable allowed origins
- **Non-root container** — Docker image runs as unprivileged user

---

## 🔮 Roadmap

- Multi-monitor support
- Persistent long-term memory via Vertex AI embeddings
- Native Gemini Live API streaming for real-time interruption handling
- Mobile screen support via ADB bridge

---

*In Greek mythology, Argus Panoptes had 100 eyes and never slept. Neither does this.*

**MIT License** · Vivek Yarra

# ARGUS API Reference

## REST Endpoints

### `GET /`
Serves the interactive ARGUS dashboard with real-time health monitoring.

**Response:** HTML page

---

### `GET /health`
Returns system health information including version, model, storage
status, and Firestore connectivity.

**Response:**
```json
{
  "status": "operational",
  "version": "2.2.0",
  "observations": 12,
  "timestamp": "2025-01-15T10:30:00.000000",
  "model": "gemini-2.0-flash-lite",
  "storage": {
    "local_storage": true,
    "screenshots_dir": true,
    "gcs_available": true,
    "gcs_bucket": "argus-agent-storage"
  },
  "firestore": {
    "available": true,
    "project_id": "my-project",
    "observations_count": 150,
    "status": "connected"
  },
  "secret_manager": {
    "available": true,
    "project_id": "my-project",
    "library_installed": true
  },
  "cloud_logging": true
}
```

---

### `GET /stats`
Returns live observation statistics.

**Response:**
```json
{
  "total_observations": 12,
  "unique_apps": ["VSCode", "Chrome"],
  "errors_detected": 2,
  "context_window_minutes": 1,
  "timestamp": "2025-01-15T10:30:00.000000"
}
```

---

### `GET /api/observations`
Retrieves recent observations from Cloud Firestore.

**Response:**
```json
{
  "observations": [
    {
      "id": "abc123",
      "app_detected": "VSCode",
      "activity_summary": "Editing Python file",
      "errors_seen": null,
      "stored_at": "2025-01-15T10:30:00.000000"
    }
  ],
  "count": 1,
  "source": "firestore"
}
```

---

### `GET /api/actions`
Retrieves recent action logs from Cloud Firestore.

**Response:**
```json
{
  "actions": [
    {
      "id": "def456",
      "command": "help me debug",
      "response": {
        "narration": "I see the null reference error...",
        "action_required": false
      },
      "stored_at": "2025-01-15T10:30:00.000000"
    }
  ],
  "count": 1,
  "source": "firestore"
}
```

---

### `GET /api/storage`
Returns storage backend health status.

**Response:**
```json
{
  "local_storage": true,
  "screenshots_dir": true,
  "gcs_available": true,
  "gcs_bucket": "argus-agent-storage"
}
```

---

## WebSocket Protocol

### Endpoint: `WS /ws`

Optional authentication via query parameter: `/ws?api_key=your_key`

### Message Types

#### Observe (client → server)
```json
{
  "type": "observe",
  "screenshot_b64": "<base64_encoded_png>"
}
```

**Response:**
```json
{
  "type": "observe_ack",
  "observation": {
    "app_detected": "VSCode",
    "activity_summary": "Editing main.py",
    "errors_seen": null,
    "urls_visited": null,
    "files_open": "main.py",
    "important_context": null,
    "timestamp": "2025-01-15T10:30:00.000000"
  },
  "total_observations": 5
}
```

#### Command (client → server)
```json
{
  "type": "command",
  "text": "help me fix this error",
  "screenshot_b64": "<optional_base64_png>"
}
```

**Response:**
```json
{
  "type": "command_response",
  "narration": "I saw you hit a null reference error twice...",
  "action_required": true,
  "action_type": "click",
  "action_target": "Apply Fix button",
  "confidence": 0.92,
  "coordinates": {
    "found": true,
    "x": 450,
    "y": 320,
    "confidence": 0.95,
    "description": "Blue 'Apply Fix' button"
  }
}
```

### Error Responses
```json
{
  "error": "Invalid JSON"
}
```

```json
{
  "error": "Rate limit exceeded. Try again later.",
  "retry_after_seconds": 60
}
```

### Rate Limiting
- Default: 60 requests per minute per client IP
- Configurable via `RATE_LIMIT_PER_MINUTE` environment variable

### Authentication
- Optional API key authentication via `api_key` query parameter
- Production: credentials loaded from **Google Cloud Secret Manager**
- Development: configured via `ARGUS_API_KEY` environment variable
- Disabled when `ARGUS_API_KEY` is not set

### Input Validation (Pydantic V2)

All WebSocket messages are validated against **Pydantic V2 strict models**
before processing:

- `ObserveMessage`: `screenshot_b64` must be 100–10MB, valid base64 only
- `CommandMessage`: `text` must be 1–1000 chars, sanitized of control chars
- Unknown `type` fields are rejected immediately
- Invalid JSON raises `ValueError`

## Security Headers

All HTTP responses include:
- `Content-Security-Policy: script-src 'strict-dynamic' 'self'` (OWASP A05:2021)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`
- `base-uri: 'self'`
- `form-action: 'self'`

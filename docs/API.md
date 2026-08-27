# StudyAgent API Reference

Base URL: `http://localhost:8000`

## Chat

### POST /api/chat
Send a message and get a response.

**Request:**
```json
{
  "message": "O que é fotosíntese?",
  "session_id": "optional-session-id",
  "use_screen": false,
  "image_b64": null,
  "monitor": 1,
  "doc_id": null
}
```

**Response:**
```json
{
  "response": "Fotosíntese é o processo...",
  "session_id": "abc123",
  "tools_used": ["web_search"],
  "evidence": {
    "intent": "generic",
    "has_screen": false,
    "has_ocr": false,
    "pipeline_stages": ["PLAN", "RESPOND"]
  }
}
```

### GET /api/health
Health check with component status.

**Response:**
```json
{
  "status": "ok",
  "timestamp": 1693123456.789,
  "components": [
    {"name": "ollama", "status": "ok", "message": "", "latency_ms": 12.3},
    {"name": "tesseract", "status": "ok", "message": "", "latency_ms": 5.1},
    {"name": "database", "status": "ok", "message": "", "latency_ms": 1.2},
    {"name": "screen_capture", "status": "ok", "message": "", "latency_ms": 8.4},
    {"name": "tool_registry", "status": "ok", "message": "5 tools registered", "latency_ms": 0.3},
    {"name": "caches", "status": "ok", "message": "ocr=0 vision=0 doc=0 hit_rate=0.0", "latency_ms": 0.1}
  ]
}
```

### GET /api/sessions
List all chat sessions.

### GET /api/sessions/{session_id}/messages
Get messages for a session.

## Screen

### POST /api/screen/capture
Capture a screen region.

### GET /api/screen/monitors
List available monitors.

### GET /api/screen/preview?monitor=0
Get a JPEG preview of a monitor.

### POST /api/screen/analyze
Analyze a screen capture with a question.

## Documents

### POST /api/documents/upload
Upload a PDF/TXT/MD document.

### GET /api/documents
List uploaded documents.

### GET /api/documents/{doc_id}
Get document metadata.

## Exercises

### POST /api/exercises/generate
Generate exercises for a topic.

### POST /api/exercises/generate/adaptive
Generate exercises based on adaptive difficulty.

### POST /api/exercises/generate/review
Generate review exercises from error notebook.

### POST /api/exercises/grade
Grade exercise answers.

## Audio

### POST /api/audio/transcribe
Transcribe audio (webm) to text.

### POST /api/audio/speak
Convert text to speech (returns audio blob).

## Tutor

### Flashcards
- `GET /api/flashcards/decks` — List decks
- `POST /api/flashcards/generate` — Generate flashcards
- `POST /api/flashcards/review` — Review a card

### Study Plans
- `POST /api/study-plans/generate` — Generate study plan

### Profile
- `GET /api/profile` — Get student profile
- `PUT /api/profile` — Update profile

### Stats
- `GET /api/stats/dashboard` — Get dashboard data

### Achievements
- `GET /api/achievements` — List achievements

### Permissions
- `PUT /api/permissions/group/{group}` — Set permission group
- `POST /api/permissions/{name}/temporary` — Grant temporary permission
- `GET /api/permissions/audit` — Get audit log

## Error Responses

All endpoints return errors in the format:
```json
{
  "detail": "Error message"
}
```

Status codes:
- `400` — Bad request
- `403` — Permission denied
- `404` — Not found
- `500` — Internal server error

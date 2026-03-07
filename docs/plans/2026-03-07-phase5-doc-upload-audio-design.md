# Phase 5: Document Upload + Audio Digests — Design Document

**Goal:** Two killer features competitors charge for — upload briefs for precedent mapping, listen to judgment summaries on the go.

**Architecture:** Celery + Redis worker for background processing. TTSProvider Protocol with Sarvam AI implementation (mock for dev). Full analysis pipeline for document uploads.

**Tech Stack additions:** Celery 5.x, Flower (monitoring), Sarvam AI SDK (TTS)

---

## 1. Document Upload Pipeline

### 1.1 Upload Flow

```
User uploads PDF → POST /documents/upload
  → Validate (PDF, ≤50MB)
  → Store to LocalStorage (dev) / GCS (prod)
  → Create Document record (status: "pending")
  → Enqueue Celery task: analyze_document(document_id)
  → Return { document_id, status: "pending" }
```

### 1.2 Background Analysis Pipeline (Celery Worker)

```
analyze_document(document_id):
  1. status → "extracting"
     Extract text (PDFParser via DocumentParser interface)

  2. status → "analyzing"
     Issue identification (Gemini Pro → structured JSON)
     Extract: legal issues, parties, relief sought, key facts

  3. status → "searching"
     Per-issue precedent search (hybrid search, parallel)
     For each issue:
       - Find supporting precedents (top 5)
       - Find opposing/distinguishing precedents (top 3)
       - Identify relevant statutes

  4. status → "generating"
     Counter-argument identification (Gemini Pro)
     Research memo generation (structured, with citations)

  5. status → "completed"
     Store analysis results as JSON in document_analyses table
```

### 1.3 Data Model Changes

**New table: `document_analyses`**
```
document_analyses:
  id: UUID PK
  document_id: UUID FK → documents.id (CASCADE)
  extracted_text: Text
  issues: JSONB  # [{issue, description, supporting_precedents[], opposing_precedents[], statutes[]}]
  parties: JSONB  # {petitioner, respondent, ...}
  key_facts: Text
  relief_sought: Text
  counter_arguments: JSONB  # [{argument, response, precedent}]
  research_memo: Text  # Formatted memo
  created_at, updated_at
```

**Modify `documents` table (migration 002):**
- Add `processing_step` column (varchar, nullable) — current step name
- Add `processing_started_at` (timestamp, nullable)
- Add `processing_completed_at` (timestamp, nullable)
- Expand status CHECK to include: 'pending', 'extracting', 'analyzing', 'searching', 'generating', 'completed', 'failed'

### 1.4 API Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `POST /documents/upload` | Any user | Upload PDF, enqueue analysis |
| `GET /documents` | Any user | List user's documents (paginated) |
| `GET /documents/{id}` | Owner only | Document detail + analysis results |
| `DELETE /documents/{id}` | Owner only | Delete document + analysis |
| `GET /documents/{id}/memo` | Owner only | Download research memo as text |

### 1.5 Prompts (added to prompts.py)

1. **DOCUMENT_ISSUE_EXTRACTION** — Extract legal issues, parties, facts, relief from uploaded document
2. **DOCUMENT_COUNTER_ARGUMENTS** — Given issues + precedents, identify counter-arguments
3. **DOCUMENT_RESEARCH_MEMO** — Generate structured research memo from analysis results

---

## 2. Audio Digests Pipeline

### 2.1 Generation Flow

```
POST /cases/{id}/audio/generate (language: "en" | "hi")
  → Check if audio already exists (cached) → return if yes
  → Enqueue Celery task: generate_audio(case_id, language)
  → Return { status: "generating" }
```

### 2.2 Background Audio Generation (Celery Worker)

```
generate_audio(case_id, language):
  1. Fetch case full_text from DB
  2. Generate summary (Gemini Pro, optimized for spoken delivery, 2-3 min)
  3. TTS via TTSProvider (Sarvam AI for Hindi, mock for dev)
  4. Store MP3 to LocalStorage/GCS
  5. Create audio_digests record
```

### 2.3 Data Model

**New table: `audio_digests`**
```
audio_digests:
  id: UUID PK
  case_id: UUID FK → cases.id (CASCADE)
  language: String (not null) — "en" or "hi"
  summary_text: Text — generated summary
  audio_storage_path: String — path to MP3
  duration_seconds: Integer (nullable)
  status: String — CHECK IN ('generating', 'completed', 'failed')
  error_message: Text (nullable)
  created_at, updated_at
  UNIQUE(case_id, language)
```

### 2.4 API Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `POST /cases/{id}/audio/generate` | Any user | Trigger async generation |
| `GET /cases/{id}/audio/status` | Any user | Check availability per language |
| `GET /cases/{id}/audio` | Any user | Stream MP3 (query param: language) |

### 2.5 TTSProvider Interface

```python
class TTSProvider(Protocol):
    async def synthesize(self, text: str, language: str) -> bytes:
        """Convert text to audio bytes (MP3)."""
        ...

    async def get_supported_languages(self) -> list[str]:
        """Return supported language codes."""
        ...
```

Implementations:
- `SarvamTTS` — Sarvam AI API (22 Indian languages)
- `MockTTS` — Returns silent MP3 bytes for testing

### 2.6 Prompts

1. **AUDIO_SUMMARY_GENERATION** — Generate spoken-delivery summary of a judgment (2-3 min length, conversational tone)

---

## 3. Celery Infrastructure

### 3.1 Setup

- Broker: Redis (reuse existing `redis_url`)
- Result backend: Redis
- Worker: `celery -A app.worker worker --loglevel=info`
- Monitor: Flower (optional, dev only)

### 3.2 Configuration

```python
# config.py additions
celery_broker_url: str = "redis://localhost:6379/1"  # DB 1 (separate from cache on DB 0)
celery_result_backend: str = "redis://localhost:6379/1"
```

### 3.3 Task Definitions

```
app/worker.py          — Celery app instance
app/tasks/
  __init__.py
  document_tasks.py    — analyze_document task
  audio_tasks.py       — generate_audio task
```

---

## 4. Frontend

### 4.1 Upload Page (`/upload`)

- Drag-and-drop zone (or click to browse)
- File validation (PDF only, ≤50MB)
- Upload progress bar
- After upload: redirect to document detail with status polling

### 4.2 Document Detail Page (`/documents/[id]`)

- Processing status with step indicator (extracting → analyzing → searching → generating → complete)
- Polling every 3 seconds while processing
- Once complete: display analysis results
  - Issues identified (accordion)
  - Per-issue: supporting precedents, opposing precedents, statutes
  - Counter-arguments
  - Research memo (full text, copy button)

### 4.3 Documents List Page (`/documents`)

- Table of user's uploaded documents
- Status badge, upload date, file name
- Click → document detail

### 4.4 Audio Player (on `/case/[id]`)

- Play/pause button, progress bar
- Playback speed selector (0.5x, 1x, 1.5x, 2x)
- Download button
- Language selector (EN / HI) — generate if not available
- Shows "Generating..." with spinner while processing

### 4.5 New Types (lib/types.ts)

```typescript
interface DocumentUploadResponse { document_id: string; status: string; }
interface DocumentListItem { id: string; filename: string; status: string; created_at: string; }
interface DocumentAnalysis { issues: Issue[]; parties: Record<string, string>; key_facts: string; ... }
interface AudioDigestStatus { available: boolean; languages: string[]; generating: string[]; }
```

### 4.6 New API Functions (lib/api.ts)

```typescript
uploadDocument(file: File): Promise<DocumentUploadResponse>
getDocuments(): Promise<DocumentListItem[]>
getDocument(id: string): Promise<DocumentDetail>
deleteDocument(id: string): Promise<void>
generateAudio(caseId: string, language: string): Promise<void>
getAudioStatus(caseId: string): Promise<AudioDigestStatus>
getAudioUrl(caseId: string, language: string): string
```

---

## 5. Testing Strategy

### Backend Tests
- Document analysis pipeline (mock Gemini, mock search) — ~15 tests
- Audio generation pipeline (mock Gemini, mock TTS) — ~10 tests
- Celery task unit tests (mock all external services) — ~8 tests
- API route tests (mock Celery task dispatch) — ~10 tests

### Frontend Tests
- Upload page (drag-drop, validation, upload flow) — ~6 tests
- Document detail page (status polling, results display) — ~6 tests
- Audio player component (play/pause, speed, download) — ~5 tests

---

## 6. File Structure

```
backend/
  app/
    worker.py                              # Celery app
    tasks/
      __init__.py
      document_tasks.py                    # analyze_document
      audio_tasks.py                       # generate_audio
    core/
      interfaces/tts.py                    # TTSProvider Protocol
      providers/tts/
        __init__.py
        sarvam.py                          # SarvamTTS
        mock_tts.py                        # MockTTS (dev/test)
      analysis/
        __init__.py
        document_analyzer.py               # Issue extraction + memo generation
        precedent_mapper.py                # Per-issue search + mapping
    api/routes/
      documents.py                         # Document upload/list/detail/delete
      audio.py                             # Audio generation/status/stream
    models/
      document_analysis.py                 # DocumentAnalysis ORM model
      audio_digest.py                      # AudioDigest ORM model
  migrations/versions/
    002_documents_audio.py                 # New tables + document status expansion
  tests/unit/
    test_document_analyzer.py
    test_precedent_mapper.py
    test_audio_pipeline.py
    test_document_routes.py
    test_audio_routes.py
    test_celery_tasks.py

frontend/src/
  app/
    upload/page.tsx                        # Upload page
    documents/page.tsx                     # Documents list
    documents/[id]/page.tsx                # Document detail + analysis
  components/
    audio-player.tsx                       # Reusable audio player
    file-upload.tsx                        # Drag-and-drop upload component
    processing-status.tsx                  # Step-by-step status indicator
  __tests__/
    upload-page.test.tsx
    document-detail-page.test.tsx
    audio-player.test.tsx
```

---

## 7. Dependencies to Add

**Backend (pyproject.toml):**
- `celery[redis]==5.4.0` — Task queue
- `flower==2.0.1` — Celery monitoring (dev optional)

**Frontend (package.json):**
- No new dependencies needed (using native `<audio>` element + existing shadcn components)

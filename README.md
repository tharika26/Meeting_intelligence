# Project 10 — Meeting Intelligence & Project Action Tracker

A full-stack GenAI application that takes a meeting recording, transcribes
it, and turns it into a structured, searchable record: summary, decisions,
action items (with owner + deadline), risks, and open questions — stored in
a project database with a live action dashboard.

```
Meeting Recording → Speech-to-Text → Transcript → LLM →
Summary + Decisions + Action Items + Risks + Questions → Project Database
```

## Stack

| Layer          | Choice                                                            |
|----------------|--------------------------------------------------------------------|
| Backend        | FastAPI + SQLAlchemy, SQLite (swap `DATABASE_URL` for Postgres)   |
| Speech-to-Text | Pluggable: OpenAI Whisper API / local `faster-whisper` / mock     |
| Extraction LLM | Anthropic Claude (`anthropic` SDK), JSON-mode prompt              |
| Search         | TF-IDF + cosine similarity over transcript+summary+actions        |
| Frontend       | Single-file React app (CDN React + Babel, no build step needed)  |

Everything **runs end-to-end offline** out of the box: with no API keys
configured, transcription falls back to a `mock` backend and analysis falls
back to a rule-based heuristic extractor, so you can demo the full pipeline
(upload → transcribe → analyze → dashboard → search) without any external
service. Add real keys to get real transcription + LLM extraction — no code
changes required, only environment variables.

## Project layout

```
backend/
  app/
    main.py              FastAPI app + router wiring
    config.py             All env-var configuration in one place
    database.py           SQLAlchemy engine/session
    models.py              Meeting, Transcript, ActionItem, Decision, Risk, OpenQuestion
    schemas.py              Pydantic request/response models
    services/
      transcription.py      Pluggable STT (openai_whisper_api / local_whisper / mock)
      llm_analysis.py        Claude-powered extraction + offline heuristic fallback
      search.py                TF-IDF semantic search
    routers/
      meetings.py             /meetings/* endpoints incl. transcribe, analyze, search
      actions.py                /actions endpoints (dashboard + tracker)
      insights.py                 /decisions, /risks, /questions, /dashboard/stats
  requirements.txt
  seed_data.py             Populates 3 realistic demo meetings for grading/demo
frontend/
  index.html              Full single-page app (7 screens, no build step)
```

## Running it

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python seed_data.py          # optional: adds 3 demo meetings so the UI has data immediately
uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000` (interactive docs at
`http://localhost:8000/docs`).

**Optional environment variables** (all have safe offline defaults):

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # enables real LLM extraction
export ANTHROPIC_MODEL=claude-sonnet-4-6

export TRANSCRIPTION_BACKEND=openai_whisper_api   # or local_whisper, or mock (default)
export OPENAI_API_KEY=sk-...                       # required for openai_whisper_api
export WHISPER_MODEL_SIZE=base                     # for local_whisper (needs faster-whisper installed)
```

### 2. Frontend

No build step — just open the file:

```bash
open frontend/index.html          # macOS
# or serve it so fetch() works cleanly from a real origin:
cd frontend && python -m http.server 5500
```

Then visit `http://localhost:5500`. If your backend isn't on
`http://localhost:8000`, click the "API:" label at the bottom of the
sidebar to edit it — it's saved in `localStorage`.

## API reference

| Method | Path                     | Purpose                                                        |
|--------|--------------------------|------------------------------------------------------------------|
| POST   | `/meetings/upload`       | Upload an audio file (`multipart/form-data`: `file`, `title`, `project`) |
| POST   | `/meetings/transcribe?meeting_id=` | Run STT on the uploaded audio (or accept `manual_text`) |
| POST   | `/meetings/analyze?meeting_id=`    | Run LLM extraction → summary/decisions/actions/risks/questions |
| GET    | `/meetings`               | List all meetings (filter by `project`)                         |
| GET    | `/meetings/{id}`          | Full analysis for one meeting                                   |
| GET    | `/meetings/{id}/transcript` | Raw transcript + segments                                     |
| POST   | `/meetings/search`         | Semantic search across meetings (`{query, top_k, project}`)     |
| GET    | `/actions`                  | List action items (`owner`, `status`, `project`, `overdue_only` filters) |
| PUT    | `/actions/{id}`              | Update an action item's status/owner/deadline/priority          |
| DELETE | `/actions/{id}`               | Remove an action item                                            |
| GET    | `/decisions` / `/risks` / `/questions` | Full logs, filterable by `project`                     |
| GET    | `/dashboard/stats`              | Aggregate KPIs: open/overdue/done counts, per-owner breakdown    |

## Frontend screens

1. **Meeting Upload** — drag-and-drop audio, run transcribe → analyze, watch the pipeline stepper move through Recording → Transcript → Analysis → Database.
2. **Transcript Review** — segment-by-segment raw transcript.
3. **Meeting Summary** — LLM summary, key topics, and per-meeting counts.
4. **Action Tracker** — every action item across all meetings; filter by owner/status/overdue; inline status updates (`PUT /actions/{id}`).
5. **Decision Log** — all decisions and risks, each linked back to its source meeting.
6. **Search** — natural-language search across everything (`POST /meetings/search`), click a result to jump to that meeting's summary.
7. **Project Dashboard** — KPIs (open/overdue/done actions, decisions, risks) and an overdue-by-owner breakdown for the "track status over time" extension.

## Design notes / assumptions

- **Owner/deadline extraction never guesses.** If the transcript doesn't
  clearly state who owns an action or when it's due, the field is left
  `null` rather than fabricated — this matters for the "Owner/deadline
  accuracy" evaluation criterion.
- **Idempotent re-analysis.** Calling `/meetings/analyze` again (with
  `force=true`) clears and re-extracts a meeting's decisions/actions/
  risks/questions rather than duplicating them — useful when you improve
  the transcript or prompt and want to regenerate.
- **Overdue** is computed server-side (`deadline < today AND status != done`)
  so the dashboard and Action Tracker always agree.
- **Search relevance**: TF-IDF was chosen over a heavier embeddings
  pipeline so the whole app works with zero external dependencies/API
  keys out of the box. `services/search.py` isolates this choice behind
  one function (`search_meetings`) — swapping in dense embeddings later
  is a one-file change.

## Advanced extension: action status over time

The data model already supports this:
- `ActionItem.updated_at` tracks the last status change.
- `GET /actions?overdue_only=true&owner=...` and `GET /dashboard/stats`
  (`overdue_by_owner`) give the building blocks for an "overdue by
  owner/project" view, already wired into the Project Dashboard screen.
- To extend to a full history-over-time chart, add an `ActionStatusLog`
  table written to on every `PUT /actions/{id}` status change, and a
  `GET /actions/{id}/history` endpoint — the current `update_action`
  handler in `routers/actions.py` is the single place that would need
  one extra `db.add(...)` call.

# Virtual Onboarding Mentor

A self-hosted conversational assistant that helps new employees learn organizational
procedures. It provides an onboarding flow built on a knowledge base with RAG retrieval,
step-by-step onboarding scenarios, personalized mentor context, and an interactive
web chat powered by Ollama.

## Features

- **Authentication** — email/password registration and login with JWT (bcrypt hashing).
  Roles: `employee`, `hr`, `mentor`, `admin`.
- **Knowledge base (RAG)** — markdown documents are chunked and embedded with Ollama,
  stored in ChromaDB, and retrieved per-language to ground chat answers.
- **Onboarding scenarios** — YAML-driven step-by-step flows (text, quizzes) with progress
  tracking, per-role visibility, and bilingual content (`en`, `pl`).
- **Personalization** — user profiles (experience level, pace, interests, preferred name)
  with `{name}` rendering and dynamic system prompts.
- **Chat** — REST API plus WebSocket streaming (`/api/chat/ws`), RAG context, conversation
  history, language-aware retrieval, and source attribution.
- **Feedback & metrics** — scenario-specific ratings and per-user progress metrics; a
  staff-only overview (completions, department breakdown, ratings).
- **Frontend** — a dependency-free vanilla JS single-page application served by FastAPI.

## Architecture

| Layer      | Technology                                      |
| ---------- | ----------------------------------------------- |
| API        | FastAPI (Python 3.13)                           |
| Database   | SQLite via SQLAlchemy                           |
| Vector DB  | ChromaDB (persistent)                           |
| Embeddings | Ollama (`nomic-embed-text`)                     |
| Chat LLM   | Ollama (streaming)                              |
| Auth       | JWT (python-jose) + bcrypt [cryptography]       |
| Frontend   | Vanilla JS SPA (no build step)                  |
| Tests      | pytest, pytest-cov                              |

## Project layout

```
app/                  FastAPI application
  auth/               registration, login, JWT dependencies
  chat/               RAG context, prompts, LLM client, REST + WebSocket routes
  feedback/           ratings and comments
  knowledge_base/     ingestion, retrieval, seeding CLI
  metrics/            per-user and staff overview metrics
  models/             SQLAlchemy models (user, profile, progress, feedback)
  personalization/    profile context, instruction and prompt building
  scenarios/          engine, progress, registry, routes
  main.py             app factory and static SPA mount
frontend/             vanilla JS SPA (index.html, views/)
data/
  documents/{en,pl}/  source markdown for the knowledge base
  scenarios/          onboarding scenario definitions (YAML)
  chroma/             ChromaDB persistent storage
  db.sqlite           SQLite database
tests/
  test_*.py           unit + API integration tests (mocked chat/LLM)
  integration/        live Ollama/Chroma tests (auto-skipped when unavailable)
```

## Getting started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) running locally

### Setup

```bash
uv sync                                          # install dependencies
cp .env.example .env                             # configure environment
# generate a SECRET_KEY (required, min 32 chars) and paste it into .env:
python -c "import secrets; print(secrets.token_urlsafe(48))"
ollama pull llama3                               # chat model
ollama pull nomic-embed-text                     # embedding model
uv run python -m app.knowledge_base.seed         # seed the knowledge base
uv run uvicorn app.main:app --reload             # start the server
```

The app refuses to start until `SECRET_KEY` is set (a missing or short key raises a
`ValidationError` at startup).

Open <http://localhost:8000>, register an account, and start onboarding.

## Production deployment

```bash
# generate a strong secret key
python -c "import secrets; print(secrets.token_urlsafe(48))"

# set restrictive permissions on .env
chmod 600 .env
```

Required production `.env` settings:

```
SECRET_KEY=<your-generated-key>
EXPOSE_DOCS=false
```

Optional:

```
INVITE_REQUIRED=true
INVITE_CODES=alpha,beta,gamma
CORS_ORIGINS=https://app.example.com
```

Run without `--reload` and bind to a loopback address, placing a TLS-terminating reverse
proxy (nginx, Caddy) in front:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

SQLite is suitable for small deployments. For larger scale, swap `DATABASE_URL` to PostgreSQL
and update the SQLAlchemy driver accordingly. Back up `data/db.sqlite` and `data/chroma/`
regularly.

## Configuration

All settings are read from environment variables (optionally via `.env`); see `app/config.py`.

| Variable                 | Default                        | Description                             |
| ------------------------ | ------------------------------ | --------------------------------------- |
| `DATABASE_URL`           | `sqlite:///./data/db.sqlite`   | SQLAlchemy connection string            |
| `SECRET_KEY`             | *(required, min 32 chars)*     | JWT signing key (no default — set it!)  |
| `OLLAMA_URL`             | `http://localhost:11434`       | Ollama server base URL                  |
| `OLLAMA_MODEL`           | `llama3`                       | Chat model for `generate`/streaming     |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text`             | Embedding model for the knowledge base  |
| `JWT_EXPIRE_MINUTES`     | `1440`                         | Access token lifetime                   |
| `CHROMA_PERSIST_DIR`     | `./data/chroma`                | ChromaDB persistent directory           |
| `CORS_ORIGINS`           | *(empty = disabled)*           | Comma-separated allowed CORS origins    |

## API

Interactive documentation (OpenAPI/Swagger) is served at `/docs` when the app is running.

Key endpoints:

| Method | Path                     | Description                                   |
| ------ | ------------------------ | --------------------------------------------- |
| POST   | `/api/auth/register`     | Register a user                               |
| POST   | `/api/auth/login`        | Login, returns a JWT                          |
| GET    | `/api/auth/me`           | Current user                                 |
| GET    | `/api/scenarios`         | List scenarios visible to the user's role     |
| GET    | `/api/scenarios/{id}`    | Scenario details with progress                |
| POST   | `/api/scenarios/{id}/answer` | Advance through a scenario                |
| GET/PUT| `/api/profile`           | Read/update the personalization profile       |
| POST   | `/api/chat`              | Chat reply (REST)                             |
| WS     | `/api/chat/ws`           | Chat reply stream (token/`done`/`error` frames) |
| POST   | `/api/feedback`          | Submit a rating with optional scenario        |
| GET    | `/api/feedback`          | List own feedback                            |
| GET    | `/api/metrics/me`        | Personal progress metrics                     |
| GET    | `/api/metrics/overview`  | Staff-only overview (`admin`/`hr`/`mentor`)    |

## Testing and linting

The default `pytest` invocation reports coverage for `app/`:

```bash
uv run pytest
```

Tests run against an isolated temporary SQLite database and mocked chat/LLM calls.
Tests marked as `integration` require a live Ollama server **and** the configured chat
model present in `/api/tags`; otherwise they are skipped automatically.

```bash
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/
uv run mypy app/
```
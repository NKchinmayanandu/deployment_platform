# Deployment Platform

A mini deployment platform for running Docker containers — inspired by Render/Railway.

## Tech Stack

- **FastAPI** — async API framework
- **SQLAlchemy 2.0** — async ORM with asyncpg
- **PostgreSQL** — primary database (Supabase-hosted)
- **Redis** — Celery broker and result backend
- **Celery** — background task processing
- **Alembic** — database migrations
- **JWT** — authentication via OAuth2 password flow

## Project Structure

```
app/
├── api/              # Route handlers and FastAPI dependencies
├── core/             # Config, security, and exception classes
├── db/               # SQLAlchemy engine and session setup
├── models/           # ORM models (User, Application, Deployment)
├── schemas/          # Pydantic request/response schemas
├── services/         # Business logic layer
├── workers/          # Celery app and task definitions
└── utils/            # Logging and shared helpers
```

## Setup

```bash
# Clone and enter the project
cd deployment_platform

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your database credentials

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

## Local Infrastructure

```bash
# Start Postgres + Redis for local development
docker compose up -d
```

## Celery Worker

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login (OAuth2 password form) |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/applications/` | Create an application |
| GET | `/api/applications/` | List your applications |
| GET | `/api/applications/{id}` | Get an application |
| DELETE | `/api/applications/{id}` | Delete an application |
| POST | `/api/deployments/{id}/deploy` | Deploy (not implemented) |
| POST | `/api/deployments/{id}/stop` | Stop (not implemented) |
| POST | `/api/deployments/{id}/restart` | Restart (not implemented) |
| DELETE | `/api/deployments/{id}` | Remove (not implemented) |
| GET | `/api/deployments/{id}` | Status (not implemented) |
| GET | `/health` | Health check |

## Interactive Docs

Once running, visit: `http://localhost:8000/docs`

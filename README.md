# Deployment Platform

A self-hosted mini deployment platform for running Docker containers — inspired by Render/Railway.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [How Requests Flow](#how-requests-flow)
5. [Environment Variables](#environment-variables)
6. [Local Development](#local-development)
7. [Production Deployment](#production-deployment)
8. [API Reference](#api-reference)

---

## Architecture Overview

```
Internet
   │
   ▼
Cloudflare (TLS termination)
   │  (encrypted tunnel, no open ports needed)
   ▼
cloudflared  ──────────────────────────────────────┐
(Cloudflare Tunnel daemon)                         │ Docker network: proxy
   │                                               │
   ▼                                               │
Traefik (reverse proxy, HTTP :80)                  │
   │  routes by Host header                        │
   ▼                                               │
backend container                                  │
 ├── uvicorn (FastAPI, :8000)  ◄────────────────────┘
 └── arq worker  ←── Redis (on host machine)
        │
        ▼
   Docker socket  →  manages user containers
```

**Key design decisions:**

- **Cloudflare handles TLS** — Traefik only speaks plain HTTP internally. Zero port-forwarding or firewall changes needed on the host.
- **Redis runs on the host** — reached from containers via `host.docker.internal:6379`. Keeps Redis outside Docker's lifecycle.
- **Supervisord runs inside the single `backend` container** — it starts and supervises both the FastAPI process and the ARQ worker so only one image needs to be built and deployed.
- **ARQ (not Celery)** — all background tasks (deploy, stop, restart, remove containers) are async-native ARQ jobs. No Celery workers, no beat scheduler.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| API framework | **FastAPI** | Async, OpenAPI docs built-in |
| ORM | **SQLAlchemy 2.0** | Async sessions with `asyncpg` |
| Database | **PostgreSQL** | Supabase-hosted (no local container) |
| Task queue | **ARQ** | Async Redis-backed job queue (replaced Celery) |
| Cache / broker | **Redis** | Runs on host, not in Docker |
| Migrations | **Alembic** | Schema versioning |
| Auth | **JWT** | OAuth2 password flow |
| Process manager | **Supervisord** | Runs uvicorn + arq inside one container |
| Reverse proxy | **Traefik v3** | Docker-label based routing |
| Tunnel | **Cloudflare Tunnel** | Exposes the platform without opening firewall ports |
| Container SDK | **Docker Python SDK** | Platform manages user containers via the socket |

---

## Project Structure

```
deployment_platform/
├── app/
│   ├── api/                # Route handlers and FastAPI dependencies
│   │   ├── auth.py         # Register / login / me
│   │   ├── applications.py # CRUD for applications
│   │   ├── deployments.py  # Deploy / stop / restart / remove / status
│   │   └── dependencies.py # Auth & session injection
│   ├── core/               # Config, security, exception classes
│   ├── db/                 # SQLAlchemy engine and async session setup
│   ├── models/             # ORM models (User, Application, Deployment)
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/           # Business logic layer
│   ├── repositories/       # Data access layer (DB queries)
│   ├── infrastructure/     # Docker container management helpers
│   ├── cache/              # Redis client and caching helpers
│   ├── workers/
│   │   ├── arq_worker.py       # ARQ WorkerSettings (queue config)
│   │   └── deployment_worker.py # Async task definitions (deploy, stop, etc.)
│   └── utils/              # Logging and shared helpers
│
├── frontend/               # React + TypeScript UI
├── performance/            # k6 load tests and benchmark scripts
├── alembic/                # Migration files
│
├── Dockerfile              # Multi-stage build (builder + runtime)
├── supervisord.conf        # Runs uvicorn + arq inside the container
├── docker-compose.yml      # Orchestrates: cloudflared, traefik, backend
├── .env.example            # Template for all required environment variables
└── pyproject.toml
```

---

## How Requests Flow

### API request (e.g. create application)

```
Browser → Cloudflare CDN → cloudflared tunnel → Traefik (:80)
       → backend:8000 (FastAPI) → service layer → repository → Supabase DB
```

### Deployment job (e.g. deploy a container)

```
POST /api/deployments/{id}/deploy
  → FastAPI handler
    → enqueues ARQ job (stored in Redis)
      → ARQ worker picks up job
        → deployment_worker.py runs Docker SDK commands
          → pulls image, creates/starts container
            → updates Deployment status in DB
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | Supabase asyncpg connection string (`postgresql+asyncpg://...`) |
| `SECRET_KEY` | Long random string for JWT signing |
| `ALGORITHM` | JWT algorithm (default: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL in minutes (default: `60`) |
| `REDIS_URL` | Redis URL for local dev (`redis://localhost:6379/0`) |
| `CLOUDFLARE_TUNNEL_TOKEN` | Token from Cloudflare Zero Trust → Tunnels |
| `API_DOMAIN` | Public domain routed by Traefik (e.g. `api.thechinmay.in`) |

> **Note:** `REDIS_URL` in `.env` is used for local development outside Docker.
> Inside Docker, `docker-compose.yml` hard-codes `redis://host.docker.internal:6379/0`
> so the container reaches Redis running on the host machine.

---

## Local Development

> Prerequisites: Python 3.12+, Redis running locally, Docker (for managing user containers)

```bash
# 1. Clone and enter the project
cd deployment_platform

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env
# Edit .env — fill in DATABASE_URL, SECRET_KEY, etc.

# 5. Run database migrations
alembic upgrade head

# 6. Start the API server
uvicorn app.main:app --reload

# 7. Start the ARQ worker (separate terminal)
arq app.workers.arq_worker.WorkerSettings
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

---

## Production Deployment

The full stack runs as three Docker containers on a single VPS.

### Prerequisites

- Docker and Docker Compose installed on the VPS
- A Cloudflare account with a configured tunnel
- Redis running on the host (`sudo systemctl start redis`)

### One-time setup

```bash
# Create the shared Docker network that Traefik and the backend share
docker network create proxy

# Configure environment
cp .env.example .env
nano .env   # fill in all values
```

### Start everything

```bash
docker compose up -d --build
```

This starts three containers:

| Container | Role |
|---|---|
| `cloudflared` | Maintains the Cloudflare Tunnel; forwards traffic to Traefik |
| `traefik` | Reads Docker labels; routes `api.thechinmay.in` → `backend:8000` |
| `deployment-platform-backend` | Runs supervisord, which manages uvicorn + arq |

### Inside the backend container

Supervisord starts two processes on container boot:

```
supervisord
 ├── [priority=10] uvicorn app.main:app --host 0.0.0.0 --port 8000
 └── [priority=20] arq app.workers.arq_worker.WorkerSettings
```

Both processes log to stdout/stderr (visible via `docker logs deployment-platform-backend`).

### Verify deployment

```bash
# Check all containers are running
docker compose ps

# Tail logs
docker compose logs -f backend

# Hit the health endpoint
curl https://api.thechinmay.in/health
```

---

## API Reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login — returns JWT access token |
| `GET` | `/api/auth/me` | Get the current authenticated user |

### Applications

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/applications/` | Create a new application |
| `GET` | `/api/applications/` | List your applications |
| `GET` | `/api/applications/{id}` | Get a specific application |
| `DELETE` | `/api/applications/{id}` | Delete an application |

### Deployments

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/deployments/{id}/deploy` | Pull image and start container (async ARQ job) |
| `POST` | `/api/deployments/{id}/stop` | Stop the running container |
| `POST` | `/api/deployments/{id}/restart` | Restart the container |
| `DELETE` | `/api/deployments/{id}` | Stop and remove the container |
| `GET` | `/api/deployments/{id}` | Get deployment status and logs |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check (used by Docker healthcheck) |

All protected endpoints require `Authorization: Bearer <token>` header.

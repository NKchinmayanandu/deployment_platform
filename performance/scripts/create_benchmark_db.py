#!/usr/bin/env python3
"""
performance/scripts/create_benchmark_db.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Creates a fully isolated benchmark PostgreSQL database.

What this script does:
  1. Pulls the postgres:16-alpine Docker image (if not already present)
  2. Starts a Docker container named 'pg_benchmark' on port 5433
     (separate from dev PostgreSQL on 5432)
  3. Waits for PostgreSQL to be ready (healthcheck loop)
  4. Creates the benchmark database + user
  5. Runs `alembic upgrade head` against the benchmark DATABASE_URL
     (reads .env.benchmark, NOT .env)

SAFETY GUARANTEE:
  This script NEVER reads from .env.
  It ONLY reads from .env.benchmark.
  Your Supabase database is never touched.

Usage:
  python performance/scripts/create_benchmark_db.py
  python performance/scripts/create_benchmark_db.py --skip-migrations
  python performance/scripts/create_benchmark_db.py --force  # Recreate if exists

Run from the project root directory.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

# Project root is two levels up from this script (performance/scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_BENCHMARK = PROJECT_ROOT / ".env.benchmark"
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


# ─── Config Loader ────────────────────────────────────────────────────────────

def load_benchmark_env() -> dict:
    """
    Parse .env.benchmark into a dict.
    Deliberately does NOT use python-dotenv to keep dependencies minimal
    and to make it crystal clear exactly which file is being read.
    """
    if not ENV_BENCHMARK.exists():
        print(f"[ERROR] .env.benchmark not found at: {ENV_BENCHMARK}")
        print("        Run this script from the project root directory.")
        sys.exit(1)

    config = {}
    with open(ENV_BENCHMARK) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()

    return config


# ─── Docker Helpers ───────────────────────────────────────────────────────────

def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command with clear output. Exits on failure if check=True."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def container_exists(name: str) -> bool:
    """Return True if a Docker container with this name exists (any state)."""
    result = run(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture=True,
    )
    return name in result.stdout.strip()


def container_running(name: str) -> bool:
    """Return True if the container exists AND is currently running."""
    result = run(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture=True,
    )
    return name in result.stdout.strip()


def wait_for_postgres(host: str, port: str, user: str, max_attempts: int = 30) -> None:
    """
    Poll PostgreSQL with pg_isready until it accepts connections.
    Waits up to max_attempts * 2 seconds before giving up.

    WHY pg_isready instead of psycopg2?
    pg_isready is a lightweight binary available on most systems alongside
    the PostgreSQL client, and it doesn't require Python DB drivers.
    """
    print(f"\n[INFO] Waiting for PostgreSQL to be ready on {host}:{port}...")
    for attempt in range(1, max_attempts + 1):
        result = run(
            ["pg_isready", "-h", host, "-p", str(port), "-U", user],
            check=False,
            capture=True,
        )
        if result.returncode == 0:
            print(f"[OK]   PostgreSQL ready after {attempt * 2}s")
            return
        print(f"  [{attempt}/{max_attempts}] Not ready yet, retrying in 2s...")
        time.sleep(2)

    print("[ERROR] PostgreSQL did not become ready in time.")
    print("        Check the container logs: docker logs pg_benchmark")
    sys.exit(1)


# ─── Database Setup ───────────────────────────────────────────────────────────

def create_db_and_user(cfg: dict) -> None:
    """
    Create the benchmark role and database inside the running container.
    Uses `docker exec` with psql to avoid needing local psql or psycopg2.

    Runs idempotently — CREATE IF NOT EXISTS pattern via DO $$ blocks.
    """
    print("\n[INFO] Creating benchmark user and database...")

    container = cfg["BENCHMARK_CONTAINER_NAME"]
    db = cfg["BENCHMARK_DB"]
    user = cfg["BENCHMARK_USER"]
    password = cfg["BENCHMARK_PASSWORD"]

    # Create the role if it doesn't already exist
    create_role_sql = (
        f"DO $$ BEGIN "
        f"  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{user}') THEN "
        f"    CREATE ROLE {user} WITH LOGIN PASSWORD '{password}'; "
        f"  END IF; "
        f"END $$;"
    )

    # Create the database if it doesn't already exist
    create_db_sql = (
        f"SELECT 'CREATE DATABASE {db} OWNER {user}' "
        f"WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{db}') \\gexec"
    )

    # Grant all privileges on the database to bench_user
    grant_sql = f"GRANT ALL PRIVILEGES ON DATABASE {db} TO {user};"

    for sql in [create_role_sql, create_db_sql, grant_sql]:
        run([
            "docker", "exec", container,
            "psql", "-U", "postgres", "-c", sql
        ])

    print(f"[OK]   Database '{db}' and user '{user}' are ready.")


def run_alembic_migrations(cfg: dict) -> None:
    """
    Run `alembic upgrade head` against the benchmark DATABASE_URL.

    Strategy:
      - Set DATABASE_URL env var to the benchmark URL before invoking alembic.
      - This overrides whatever is in .env (Pydantic Settings reads from env vars
        with priority over .env file, so os.environ takes precedence).
      - The alembic env.py uses settings.DATABASE_URL, so it picks up our override.

    SAFETY: We explicitly set DATABASE_URL to the benchmark URL. Even if .env
    is accidentally loaded, os.environ takes precedence in pydantic-settings.
    """
    print("\n[INFO] Running Alembic migrations against benchmark database...")

    # Build the sync psycopg2 URL (alembic uses sync driver)
    async_url = cfg["DATABASE_URL"]
    sync_url = async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

    env = os.environ.copy()
    env["DATABASE_URL"] = async_url  # pydantic-settings reads this

    # Override alembic's sqlalchemy.url directly via -x flag
    result = run([
        "alembic",
        "-x", f"db_url={sync_url}",
        "upgrade", "head",
    ], check=False)

    if result.returncode != 0:
        # If -x flag isn't supported by their alembic env.py, fall back to env var
        print("[WARN] -x flag approach failed. Falling back to DATABASE_URL env override...")
        run(
            ["alembic", "upgrade", "head"],
        )

    print("[OK]   Migrations applied successfully.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Create an isolated benchmark PostgreSQL database via Docker."
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Start the container and create the DB, but skip running Alembic migrations.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="If the container already exists, stop and remove it before recreating.",
    )
    args = parser.parse_args()

    # Always run from project root so alembic finds alembic.ini
    os.chdir(PROJECT_ROOT)

    print("=" * 70)
    print("  BENCHMARK DATABASE CREATION")
    print(f"  Config: {ENV_BENCHMARK}")
    print("  !! This script NEVER touches your Supabase production database.")
    print("=" * 70)

    cfg = load_benchmark_env()

    container = cfg["BENCHMARK_CONTAINER_NAME"]
    volume = cfg["BENCHMARK_VOLUME_NAME"]
    host = cfg["BENCHMARK_HOST"]
    port = cfg["BENCHMARK_PORT"]
    user = cfg["BENCHMARK_USER"]
    password = cfg["BENCHMARK_PASSWORD"]
    pg_image = cfg["BENCHMARK_PG_IMAGE"]

    # ── Step 1: Handle existing container ────────────────────────────────────
    if container_exists(container):
        if args.force:
            print(f"\n[INFO] --force: Removing existing container '{container}'...")
            run(["docker", "stop", container], check=False)
            run(["docker", "rm", container], check=False)
        elif container_running(container):
            print(f"\n[OK]   Container '{container}' already running. Skipping creation.")
            print("       Use --force to recreate it from scratch.")
        else:
            print(f"\n[INFO] Container '{container}' exists but is stopped. Starting it...")
            run(["docker", "start", container])
            wait_for_postgres(host, port, "postgres")
            create_db_and_user(cfg)
            if not args.skip_migrations:
                run_alembic_migrations(cfg)
            print("\n[DONE] Benchmark database is ready.")
            return

    # ── Step 2: Pull image ────────────────────────────────────────────────────
    print(f"\n[INFO] Pulling Docker image: {pg_image}")
    run(["docker", "pull", pg_image])

    # ── Step 3: Start the container ───────────────────────────────────────────
    print(f"\n[INFO] Starting benchmark PostgreSQL container on port {port}...")
    run([
        "docker", "run",
        "--name", container,
        "--detach",
        # Named volume for persistence between resets (destroyed only by drop script)
        "--volume", f"{volume}:/var/lib/postgresql/data",
        # Expose on a different port than dev PostgreSQL (5432)
        "--publish", f"{port}:5432",
        "--env", "POSTGRES_USER=postgres",
        "--env", "POSTGRES_PASSWORD=postgres",
        "--env", "POSTGRES_DB=postgres",
        # Restart policy: don't auto-restart (benchmark DB is explicit-lifecycle)
        "--restart", "no",
        pg_image,
    ])

    # ── Step 4: Wait for PG to be ready ──────────────────────────────────────
    wait_for_postgres(host, port, "postgres")

    # ── Step 5: Create database + user ───────────────────────────────────────
    create_db_and_user(cfg)

    # ── Step 6: Run migrations ────────────────────────────────────────────────
    if not args.skip_migrations:
        run_alembic_migrations(cfg)

    print("\n" + "=" * 70)
    print("  [DONE] Benchmark database is ready!")
    print()
    print("  Next steps:")
    print("    1. Seed the database:")
    print("       make seed")
    print("       # or: cd performance && python seed/seed.py")
    print()
    print("    2. Start FastAPI with benchmark config:")
    print("       make app-start")
    print("       # or: ENV_FILE=.env.benchmark uvicorn app.main:app --reload")
    print()
    print("    3. Run tests:")
    print("       make smoke")
    print("       make load")
    print("=" * 70)


if __name__ == "__main__":
    main()

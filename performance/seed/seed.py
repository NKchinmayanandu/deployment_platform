#!/usr/bin/env python3
"""
performance/seed/seed.py
─────────────────────────────────────────────────────────────────────────────
Complete benchmark database seeder — all tables, one file.

Seeds:
  - Users        (default: 10,000)  — SEED_USERS env var
  - Applications (default: 50,000)  — SEED_APPS env var
  - Deployments  (default: 50,000)  — SEED_DEPLOYMENTS env var
                                      (1 per app — applications.deployment is 1-to-1)
  - Environments (default: 3 per app) — SEED_ENV_VARS_PER_APP env var

Design:
  - Reads .env.benchmark ONLY — never touches .env (Supabase)
  - Bulk inserts via asyncpg (executemany) — no row-by-row
  - bcrypt cost=4 for speed (10k users in ~30s vs ~8hrs at cost=12)
  - Username pattern: bench_user_{n}, password: BenchPass_{n}!
    k6 auth.js derives credentials from this same pattern.
  - Idempotent: skips tables that already have enough rows

Run from project root:
  python performance/seed/seed.py
  SEED_USERS=500 SEED_APPS=2000 SEED_DEPLOYMENTS=1000 python performance/seed/seed.py
─────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── Dependency check ─────────────────────────────────────────────────────────

try:
    import asyncpg
    import bcrypt
except ImportError:
    print("[ERROR] Missing dependencies. Run:")
    print("  pip install asyncpg bcrypt")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────

PROJECT_ROOT   = Path(__file__).resolve().parent.parent.parent
ENV_BENCHMARK  = PROJECT_ROOT / ".env.benchmark"

# Batch size for bulk inserts — large enough for speed, small enough to avoid
# PostgreSQL packet size limits (~64MB default max_packet_size)
BATCH_SIZE = 2_000


def load_env() -> dict:
    """Parse .env.benchmark into a dict. Never reads .env (Supabase)."""
    if not ENV_BENCHMARK.exists():
        print(f"[ERROR] .env.benchmark not found at {ENV_BENCHMARK}")
        print("        Run from the project root directory.")
        sys.exit(1)
    cfg = {}
    with open(ENV_BENCHMARK) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            cfg[k.strip()] = v.strip()
    return cfg


def get_asyncpg_dsn(cfg: dict) -> str:
    """Convert asyncpg DSN from the DATABASE_URL in .env.benchmark."""
    url = cfg["DATABASE_URL"]
    # asyncpg doesn't use the driver prefix
    return url.replace("postgresql+asyncpg://", "postgresql://")


def seed_config() -> dict:
    return {
        "users":           int(os.getenv("SEED_USERS", "10000")),
        "apps":            int(os.getenv("SEED_APPS", "50000")),
        "deployments":     int(os.getenv("SEED_DEPLOYMENTS", "50000")),
        "env_vars_per_app": int(os.getenv("SEED_ENV_VARS_PER_APP", "3")),
        "only":            os.getenv("SEED_ONLY", ""),        # comma-separated table names
        "dry_run":         os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes"),
    }


# ─── Data generators ──────────────────────────────────────────────────────────

ADJECTIVES = ["fast", "secure", "cloud", "smart", "micro", "global", "dynamic",
              "realtime", "distributed", "scalable", "resilient", "elastic",
              "unified", "core", "next", "edge", "turbo", "atomic", "quantum"]

NOUNS      = ["api", "service", "worker", "gateway", "proxy", "scheduler",
              "processor", "monitor", "notifier", "pipeline", "engine", "hub",
              "broker", "store", "cache", "router", "streamer", "indexer"]

IMAGES     = ["nginx:alpine", "node:20-alpine", "python:3.11-slim", "redis:7-alpine",
              "golang:1.22-alpine", "caddy:alpine", "traefik:v3", "php:8.3-fpm-alpine",
              "openjdk:21-slim", "postgres:16-alpine"]

PORTS      = [3000, 4000, 5000, 8000, 8080, 8888, 9000]

# Weighted deployment status distribution (realistic production ratios)
STATUSES   = (
    ["RUNNING"]    * 50 +  # 50% running
    ["STOPPED"]    * 25 +  # 25% stopped
    ["FAILED"]     * 15 +  # 15% failed
    ["QUEUED"]     * 7  +  # 7%  queued
    ["RESTARTING"] * 3     # 3%  restarting
)

ENV_KEYS   = ["NODE_ENV", "LOG_LEVEL", "PORT", "WORKERS", "MAX_CONNECTIONS",
              "TIMEOUT", "CACHE_TTL", "REGION", "DEBUG", "RETRY_LIMIT"]

ENV_VALUES = {
    "NODE_ENV":        ["production", "staging"],
    "LOG_LEVEL":       ["info", "warn", "error"],
    "PORT":            ["3000", "4000", "8080"],
    "WORKERS":         ["1", "2", "4", "8"],
    "MAX_CONNECTIONS": ["10", "25", "50", "100"],
    "TIMEOUT":         ["5", "10", "30", "60"],
    "CACHE_TTL":       ["60", "300", "3600"],
    "REGION":          ["us-east-1", "eu-west-1", "ap-south-1"],
    "DEBUG":           ["true", "false"],
    "RETRY_LIMIT":     ["1", "2", "3", "5"],
}


def rand_app_name(n: int) -> str:
    adj  = ADJECTIVES[n % len(ADJECTIVES)]
    noun = NOUNS[(n * 7) % len(NOUNS)]
    return f"{adj}-{noun}-{n}"


def rand_past_datetime(days_back: int = 365) -> datetime:
    offset = timedelta(seconds=random.randint(0, days_back * 86400))
    # PostgreSQL columns are TIMESTAMP WITHOUT TIME ZONE — asyncpg requires naive datetimes.
    # We calculate in UTC for correctness, then strip tzinfo before inserting.
    return (datetime.now(timezone.utc) - offset).replace(tzinfo=None)


# ─── Hash passwords (bcrypt cost=4 for speed) ─────────────────────────────────

def hash_password(password: str) -> str:
    """
    bcrypt cost=4 hashes in ~3ms vs ~300ms at cost=12.
    Fine for benchmark data — we only care that the hash is valid and
    the k6 login flow works, not that it's secure.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()


# ─── Seeders ──────────────────────────────────────────────────────────────────

async def seed_users(conn: asyncpg.Connection, count: int, dry_run: bool) -> int:
    """
    Bulk-insert `count` users.
    Username: bench_user_{1..n}
    Password: BenchPass_{n}!  ← same pattern used by k6 auth.js getVUCredentials()
    """
    existing = await conn.fetchval("SELECT COUNT(*) FROM users")
    if existing >= count:
        print(f"  [SKIP] users: {existing:,} rows already present (target: {count:,})")
        return existing

    needed    = count - existing
    start_idx = existing + 1
    print(f"  [INFO] Seeding {needed:,} users (idx {start_idx}..{count})...")

    if dry_run:
        print(f"  [DRY] Would insert {needed:,} users")
        return count

    # Pre-hash a set of passwords and cycle them (avoids hashing count times)
    # We use 100 unique hashes and cycle — unique enough for benchmarking
    HASH_POOL_SIZE = 100
    print(f"  [INFO] Pre-generating {HASH_POOL_SIZE} password hashes (bcrypt cost=4)...")
    t0 = time.time()
    hash_pool = [hash_password(f"BenchPass_{i}!") for i in range(1, HASH_POOL_SIZE + 1)]
    print(f"  [INFO] Hashes ready in {time.time() - t0:.1f}s")

    inserted = 0
    for batch_start in range(0, needed, BATCH_SIZE):
        batch = []
        for j in range(batch_start, min(batch_start + BATCH_SIZE, needed)):
            idx = start_idx + j
            # Users 1..HASH_POOL_SIZE get their own hash; rest cycle
            pw_hash = hash_pool[(idx - 1) % HASH_POOL_SIZE]
            batch.append((
                f"bench_user_{idx}",
                f"bench_user_{idx}@example.com",
                pw_hash,
                rand_past_datetime(365),
            ))

        await conn.executemany(
            "INSERT INTO users (username, email, hashed_password, created_at) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
            batch,
        )
        inserted += len(batch)
        print(f"    → {inserted + existing:,}/{count:,} users", end="\r", flush=True)

    print(f"  [OK]  {count:,} users ready.{' ' * 20}")
    return count


async def seed_applications(
    conn: asyncpg.Connection,
    count: int,
    user_count: int,
    dry_run: bool,
) -> int:
    """
    Bulk-insert `count` applications distributed across all seeded users.

    Distribution: count / user_count apps per user (sequential assignment).
    k6 getOwnedAppId() uses the same formula to ensure VUs hit their own apps.

    APPS_PER_USER = count // user_count  (default: 50000 // 10000 = 5)
    User N owns app IDs: (N-1)*5+1 .. N*5
    """
    existing = await conn.fetchval("SELECT COUNT(*) FROM applications")
    if existing >= count:
        print(f"  [SKIP] applications: {existing:,} rows already present (target: {count:,})")
        return existing

    needed    = count - existing
    start_idx = existing + 1
    print(f"  [INFO] Seeding {needed:,} applications...")

    if dry_run:
        print(f"  [DRY] Would insert {needed:,} applications")
        return count

    apps_per_user = max(1, count // user_count)
    inserted = 0
    for batch_start in range(0, needed, BATCH_SIZE):
        batch = []
        for j in range(batch_start, min(batch_start + BATCH_SIZE, needed)):
            idx      = start_idx + j
            owner_id = ((idx - 1) // apps_per_user) + 1
            # Clamp owner_id to valid user range
            owner_id = min(owner_id, user_count)
            batch.append((
                owner_id,
                rand_app_name(idx),
                IMAGES[idx % len(IMAGES)],
                PORTS[idx % len(PORTS)],
                rand_past_datetime(300),
            ))

        await conn.executemany(
            "INSERT INTO applications (owner_id, name, image_name, container_port, created_at) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            batch,
        )
        inserted += len(batch)
        print(f"    → {inserted + existing:,}/{count:,} applications", end="\r", flush=True)

    print(f"  [OK]  {count:,} applications ready.{' ' * 20}")
    return count


async def seed_deployments(
    conn: asyncpg.Connection,
    count: int,
    app_count: int,
    dry_run: bool,
) -> int:
    """
    Bulk-insert up to `count` deployments (1 per application — unique constraint).

    Your Deployment model has: application_id UNIQUE — so at most one
    deployment per application. We seed min(count, app_count) deployments.
    """
    actual_count = min(count, app_count)

    existing = await conn.fetchval("SELECT COUNT(*) FROM deployments")
    if existing >= actual_count:
        print(f"  [SKIP] deployments: {existing:,} rows already present (target: {actual_count:,})")
        return existing

    needed    = actual_count - existing
    start_idx = existing + 1  # app_id to start from
    print(f"  [INFO] Seeding {needed:,} deployments...")

    if dry_run:
        print(f"  [DRY] Would insert {needed:,} deployments")
        return actual_count

    inserted = 0
    host_port_base = 10000  # Start host ports here to avoid conflicts

    for batch_start in range(0, needed, BATCH_SIZE):
        batch = []
        for j in range(batch_start, min(batch_start + BATCH_SIZE, needed)):
            app_id  = start_idx + j
            status  = STATUSES[(app_id * 13) % len(STATUSES)]
            created = rand_past_datetime(300)
            updated = created + timedelta(seconds=random.randint(0, 3600))

            # Only RUNNING/STOPPED deployments have container info
            has_container = status in ("RUNNING", "STOPPED", "RESTARTING")
            container_id   = f"{'abcdef0123456789' * 4}"[:64] if has_container else None
            container_name = f"app_{app_id}_container"          if has_container else None
            host_port      = host_port_base + app_id            if status == "RUNNING" else None
            deploy_url     = f"http://localhost:{host_port_base + app_id}" if status == "RUNNING" else None

            batch.append((
                app_id,
                container_id,
                container_name,
                host_port,
                status,
                created,
                updated,
                deploy_url,
            ))

        await conn.executemany(
            "INSERT INTO deployments "
            "(application_id, container_id, container_name, host_port, status, created_at, updated_at, deployment_url) "
            "VALUES ($1, $2, $3, $4, $5::deploymentstatus, $6, $7, $8) ON CONFLICT DO NOTHING",
            batch,
        )
        inserted += len(batch)
        print(f"    → {inserted + existing:,}/{actual_count:,} deployments", end="\r", flush=True)

    print(f"  [OK]  {actual_count:,} deployments ready.{' ' * 20}")
    return actual_count


async def seed_environments(
    conn: asyncpg.Connection,
    app_count: int,
    env_vars_per_app: int,
    dry_run: bool,
) -> int:
    """
    Bulk-insert environment variables for all seeded applications.
    Each app gets env_vars_per_app key-value pairs.
    """
    target   = app_count * env_vars_per_app
    existing = await conn.fetchval("SELECT COUNT(*) FROM environments")
    if existing >= target:
        print(f"  [SKIP] environments: {existing:,} rows already present (target: {target:,})")
        return existing

    print(f"  [INFO] Seeding {target:,} environment variables ({env_vars_per_app} per app)...")

    if dry_run:
        print(f"  [DRY] Would insert {target:,} env vars")
        return target

    # Determine which apps already have env vars
    existing_app_ids = set(
        row["application_id"]
        for row in await conn.fetch("SELECT DISTINCT application_id FROM environments")
    )

    keys_cycle = ENV_KEYS[:env_vars_per_app]  # Use first N keys per app

    inserted = 0
    batch = []
    for app_id in range(1, app_count + 1):
        if app_id in existing_app_ids:
            continue
        for key in keys_cycle:
            choices = ENV_VALUES.get(key, ["value"])
            value   = choices[(app_id * len(key)) % len(choices)]
            batch.append((app_id, key, value))

        if len(batch) >= BATCH_SIZE:
            await conn.executemany(
                "INSERT INTO environments (application_id, key, value) "
                "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                batch,
            )
            inserted += len(batch)
            batch = []
            print(f"    → {inserted:,}/{target:,} env vars", end="\r", flush=True)

    # Insert remaining
    if batch:
        await conn.executemany(
            "INSERT INTO environments (application_id, key, value) "
            "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            batch,
        )
        inserted += len(batch)

    print(f"  [OK]  {inserted + existing:,} environment variables ready.{' ' * 20}")
    return inserted + existing


# ─── Orchestrator ─────────────────────────────────────────────────────────────

async def main():
    env_cfg = load_env()
    cfg     = seed_config()
    dsn     = get_asyncpg_dsn(env_cfg)

    only    = {t.strip() for t in cfg["only"].split(",") if t.strip()}
    dry_run = cfg["dry_run"]

    print("=" * 62)
    print("  BENCHMARK DATABASE SEEDER")
    print(f"  Target: {env_cfg.get('BENCHMARK_DB', 'deployment_platform_benchmark')}")
    if dry_run:
        print("  Mode: DRY RUN (no data will be written)")
    print("=" * 62)
    print(f"  Users:        {cfg['users']:>10,}")
    print(f"  Applications: {cfg['apps']:>10,}")
    print(f"  Deployments:  {cfg['deployments']:>10,}")
    print(f"  Env vars:     {cfg['apps'] * cfg['env_vars_per_app']:>10,}  ({cfg['env_vars_per_app']} per app)")
    print("=" * 62)
    print()

    t_start = time.time()

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print(f"[ERROR] Cannot connect to benchmark database: {e}")
        print("        Is the benchmark container running?")
        print("        Run: python performance/scripts/create_benchmark_db.py")
        sys.exit(1)

    try:
        # Run in dependency order: users → apps → deployments → environments
        if not only or "users" in only:
            await seed_users(conn, cfg["users"], dry_run)

        if not only or "applications" in only:
            await seed_applications(conn, cfg["apps"], cfg["users"], dry_run)

        if not only or "deployments" in only:
            await seed_deployments(conn, cfg["deployments"], cfg["apps"], dry_run)

        if not only or "environments" in only:
            await seed_environments(conn, cfg["apps"], cfg["env_vars_per_app"], dry_run)

    finally:
        await conn.close()

    elapsed = time.time() - t_start
    print()
    print("=" * 62)
    print(f"  [DONE] Seeding complete in {elapsed:.1f}s")
    print()
    print("  Next: start FastAPI with benchmark config:")
    print("    make app-start")
    print("    # then: make smoke")
    print("=" * 62)


if __name__ == "__main__":
    asyncio.run(main())

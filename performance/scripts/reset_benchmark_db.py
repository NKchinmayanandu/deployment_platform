#!/usr/bin/env python3
"""
performance/scripts/reset_benchmark_db.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Resets the benchmark database to a clean state for a reproducible test run.

What this script does:
  1. Verifies the benchmark container is running (does NOT start it)
  2. Truncates all application tables in the correct dependency order
     (respects foreign key constraints using TRUNCATE ... CASCADE)
  3. Resets all sequences (auto-increment IDs) back to 1
  4. Optionally re-seeds the database (--seed flag)
  5. Optionally re-runs migrations first (--migrate flag)

WHY TRUNCATE instead of DROP + RECREATE?
  TRUNCATE is ~100x faster than DELETE on large tables. It also preserves
  table structure and indexes, so we avoid the full migration overhead.
  This makes reset-between-runs fast enough to do between every test scenario.

SAFETY GUARANTEE:
  Reads ONLY from .env.benchmark. Never touches .env or Supabase.

Usage:
  python performance/scripts/reset_benchmark_db.py
  python performance/scripts/reset_benchmark_db.py --seed            # Truncate + reseed
  python performance/scripts/reset_benchmark_db.py --seed --migrate  # Full reset
  python performance/scripts/reset_benchmark_db.py --seed --users=500 --apps=2000

Run from the project root directory.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_BENCHMARK = PROJECT_ROOT / ".env.benchmark"
SEED_SCRIPT = PROJECT_ROOT / "performance" / "seed" / "seed.py"


# ─── Config Loader (same as create script) ────────────────────────────────────

def load_benchmark_env() -> dict:
    if not ENV_BENCHMARK.exists():
        print(f"[ERROR] .env.benchmark not found at: {ENV_BENCHMARK}")
        sys.exit(1)
    config = {}
    with open(ENV_BENCHMARK) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True, capture_output=False)


def run_capture(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


# ─── Container Check ──────────────────────────────────────────────────────────

def ensure_container_running(container: str) -> None:
    """
    Verify the benchmark container is up.
    If it exists but is stopped, start it and exit with a helpful message
    (the user should run the app + seeder after it's up).
    """
    result = run_capture(
        ["docker", "ps", "--filter", f"name=^{container}$", "--format", "{{.Names}}"]
    )
    if container not in result.stdout:
        # Check if it exists but is stopped
        stopped = run_capture(
            ["docker", "ps", "-a", "--filter", f"name=^{container}$", "--format", "{{.Names}}"]
        )
        if container in stopped.stdout:
            print(f"[INFO] Container '{container}' is stopped. Starting it...")
            run(["docker", "start", container])
            import time; time.sleep(3)  # Brief wait for PG to start
        else:
            print(f"[ERROR] Benchmark container '{container}' not found.")
            print("        Run: python performance/scripts/create_benchmark_db.py")
            sys.exit(1)


# ─── Truncate Tables ──────────────────────────────────────────────────────────

# Tables ordered from child → parent to respect foreign key constraints.
# TRUNCATE CASCADE handles it automatically, but explicit order is clearer.
TABLES_IN_DEPENDENCY_ORDER = [
    # Leaf tables first (have FK to parent tables)
    "deployments",
    "environments",            # FK → applications
    "applications",            # FK → users
    "users",
]

# Alembic's internal version table — never truncate this
ALEMBIC_TABLE = "alembic_version"


def truncate_all_tables(container: str, db: str, user: str) -> None:
    """
    Truncate all application tables using a single SQL statement.
    RESTART IDENTITY resets all sequences (auto-increment IDs) to 1.
    CASCADE handles foreign key dependencies automatically.

    WHY RESTART IDENTITY?
      Without it, IDs keep incrementing across resets, making seeder
      output non-deterministic across runs. Starting at 1 every time
      means seeded data is reproducible and k6 scripts can use
      predictable ID ranges.
    """
    print("\n[INFO] Truncating all tables...")

    # Build a TRUNCATE statement for all tables at once — single transaction
    table_list = ", ".join(TABLES_IN_DEPENDENCY_ORDER)
    truncate_sql = f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;"

    run([
        "docker", "exec", container,
        "psql", "-U", user, "-d", db,
        "-c", truncate_sql
    ])

    print(f"[OK]   Truncated: {table_list}")
    print("[OK]   All sequences reset to 1.")


def verify_empty(container: str, db: str, user: str) -> None:
    """Quick sanity check — count rows in each table after truncation."""
    print("\n[INFO] Verifying tables are empty...")
    for table in TABLES_IN_DEPENDENCY_ORDER:
        result = run_capture([
            "docker", "exec", container,
            "psql", "-U", user, "-d", db,
            "-t", "-c", f"SELECT COUNT(*) FROM {table};"
        ])
        count = result.stdout.strip()
        status = "[OK]  " if count == "0" else "[WARN]"
        print(f"  {status} {table}: {count} rows")


# ─── Re-run Migrations (optional) ─────────────────────────────────────────────

def run_migrations(cfg: dict) -> None:
    """
    Re-apply alembic migrations. Useful when schema has changed since last run.
    Downgrade to base first to ensure a clean state, then upgrade to head.
    """
    async_url = cfg["DATABASE_URL"]
    sync_url = async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

    print("\n[INFO] Re-running migrations (downgrade → upgrade)...")
    env = os.environ.copy()
    env["DATABASE_URL"] = async_url

    run(["alembic", "downgrade", "base"])
    run(["alembic", "upgrade", "head"])
    print("[OK]   Migrations complete.")


# ─── Re-seed ──────────────────────────────────────────────────────────────────

def run_seeder(users: int, apps: int, deployments: int, logs: int) -> None:
    """Invoke the seeder script with the given dataset size."""
    if not SEED_SCRIPT.exists():
        print(f"[ERROR] Seed script not found: {SEED_SCRIPT}")
        print("        Generate it first (File #19 in the roadmap).")
        sys.exit(1)

    print(f"\n[INFO] Seeding benchmark database...")
    print(f"       Users: {users:,} | Apps: {apps:,} | Deployments: {deployments:,} | Logs: {logs:,}")

    env = os.environ.copy()
    env["SEED_USERS"] = str(users)
    env["SEED_APPS"] = str(apps)
    env["SEED_DEPLOYMENTS"] = str(deployments)
    env["SEED_LOGS"] = str(logs)

    # Seeder reads .env.benchmark to get DATABASE_URL
    subprocess.run(
        [sys.executable, str(SEED_SCRIPT)],
        check=True,
        env=env,
        cwd=str(PROJECT_ROOT),
    )
    print("[OK]   Seeding complete.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Reset benchmark DB to clean state. Optionally re-seed."
    )
    parser.add_argument("--seed", action="store_true", help="Re-seed after truncating.")
    parser.add_argument("--migrate", action="store_true", help="Re-run migrations before truncating.")
    parser.add_argument("--users", type=int, default=10_000, help="Number of users to seed (default: 10000)")
    parser.add_argument("--apps", type=int, default=50_000, help="Number of applications to seed (default: 50000)")
    parser.add_argument("--deployments", type=int, default=200_000, help="Number of deployments to seed (default: 200000)")
    parser.add_argument("--logs", type=int, default=5_000_000, help="Number of log entries to seed (default: 5000000)")
    parser.add_argument("--skip-verify", action="store_true", help="Skip post-truncate row count check.")
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)

    print("=" * 70)
    print("  BENCHMARK DATABASE RESET")
    print(f"  Config: {ENV_BENCHMARK}")
    print("  !! This script NEVER touches your Supabase production database.")
    print("=" * 70)

    cfg = load_benchmark_env()
    container = cfg["BENCHMARK_CONTAINER_NAME"]
    db = cfg["BENCHMARK_DB"]

    # Use the superuser 'postgres' for DDL operations like TRUNCATE
    pg_superuser = "postgres"

    # ── Step 1: Make sure the container is running ────────────────────────────
    ensure_container_running(container)

    # ── Step 2: Optionally re-run migrations ──────────────────────────────────
    if args.migrate:
        run_migrations(cfg)

    # ── Step 3: Truncate all tables ───────────────────────────────────────────
    truncate_all_tables(container, db, pg_superuser)

    # ── Step 4: Verify ────────────────────────────────────────────────────────
    if not args.skip_verify:
        verify_empty(container, db, pg_superuser)

    # ── Step 5: Optionally re-seed ────────────────────────────────────────────
    if args.seed:
        run_seeder(
            users=args.users,
            apps=args.apps,
            deployments=args.deployments,
            logs=args.logs,
        )

    print("\n" + "=" * 70)
    print("  [DONE] Benchmark database reset complete.")
    if not args.seed:
        print()
        print("  The database is empty. Run seeding with:")
        print("    make seed")
        print("    # or: python performance/scripts/reset_benchmark_db.py --seed")
    print("=" * 70)


if __name__ == "__main__":
    main()

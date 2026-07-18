#!/usr/bin/env python3
"""
performance/scripts/drop_benchmark_db.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Completely destroys the benchmark database environment.

What this script does:
  1. Stops the benchmark Docker container (SIGTERM, then SIGKILL after timeout)
  2. Removes the container
  3. Removes the named Docker volume (all benchmark data is permanently deleted)
  4. Prints confirmation

This is the "nuclear option" — use it when:
  - You want to start completely fresh (different schema, new migrations)
  - You're done benchmarking and want to reclaim disk space
  - The benchmark DB got into a corrupt state

SAFETY GUARANTEE:
  Only touches the container and volume named in .env.benchmark.
  (Default: container='pg_benchmark', volume='pg_benchmark_data')
  Your dev PostgreSQL, Supabase, and all application data are untouched.

Usage:
  python performance/scripts/drop_benchmark_db.py
  python performance/scripts/drop_benchmark_db.py --yes   # Skip confirmation prompt

Run from the project root directory.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import subprocess
import sys
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_BENCHMARK = PROJECT_ROOT / ".env.benchmark"


# ─── Config Loader ────────────────────────────────────────────────────────────

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


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command. check=False by default since we're doing cleanup."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True, capture_output=False)


def run_capture(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True)


# ─── State Checks ─────────────────────────────────────────────────────────────

def container_exists(name: str) -> bool:
    result = run_capture(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"]
    )
    return name in result.stdout


def volume_exists(name: str) -> bool:
    result = run_capture(
        ["docker", "volume", "ls", "--filter", f"name=^{name}$", "--format", "{{.Name}}"]
    )
    return name in result.stdout


# ─── Teardown Steps ───────────────────────────────────────────────────────────

def stop_container(name: str) -> None:
    """Send SIGTERM to the container. Docker will SIGKILL after 10s if needed."""
    print(f"\n[INFO] Stopping container '{name}'...")
    result = run(["docker", "stop", "--time", "10", name])
    if result.returncode == 0:
        print(f"[OK]   Container '{name}' stopped.")
    else:
        print(f"[WARN] Could not stop '{name}' — may already be stopped.")


def remove_container(name: str) -> None:
    """Remove the stopped container."""
    print(f"\n[INFO] Removing container '{name}'...")
    result = run(["docker", "rm", name])
    if result.returncode == 0:
        print(f"[OK]   Container '{name}' removed.")
    else:
        print(f"[WARN] Could not remove '{name}' — may not exist.")


def remove_volume(name: str) -> None:
    """
    Remove the named Docker volume that holds PostgreSQL data.
    This permanently deletes all benchmark data.

    WHY A NAMED VOLUME?
      Named volumes survive container removal (unlike anonymous volumes),
      which lets `reset_benchmark_db.py` truncate+reseed without destroying
      the volume. The `drop` script is the only one that removes it.
    """
    print(f"\n[INFO] Removing Docker volume '{name}'...")
    result = run(["docker", "volume", "rm", name])
    if result.returncode == 0:
        print(f"[OK]   Volume '{name}' removed. All benchmark data is gone.")
    else:
        print(f"[WARN] Could not remove volume '{name}' — may not exist or still in use.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Completely destroy the benchmark PostgreSQL container and volume."
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip the confirmation prompt (useful for scripted/CI runs).",
    )
    parser.add_argument(
        "--keep-volume",
        action="store_true",
        help="Remove the container but keep the Docker volume (data preserved).",
    )
    args = parser.parse_args()

    cfg = load_benchmark_env()
    container = cfg["BENCHMARK_CONTAINER_NAME"]
    volume = cfg["BENCHMARK_VOLUME_NAME"]

    print("=" * 70)
    print("  BENCHMARK DATABASE TEARDOWN")
    print()
    print(f"  Container : {container}")
    print(f"  Volume    : {volume}  {'(KEEPING)' if args.keep_volume else '(WILL BE DELETED)'}")
    print()
    print("  !! This will permanently delete ALL benchmark data.")
    print("  !! Your Supabase database is NOT affected.")
    print("=" * 70)

    # ── Confirmation ──────────────────────────────────────────────────────────
    if not args.yes:
        try:
            response = input("\n  Proceed? [y/N]: ").strip().lower()
        except KeyboardInterrupt:
            print("\n[ABORT] Cancelled by user.")
            sys.exit(0)

        if response not in ("y", "yes"):
            print("[ABORT] Teardown cancelled.")
            sys.exit(0)

    # ── Check current state ────────────────────────────────────────────────────
    c_exists = container_exists(container)
    v_exists = volume_exists(volume)

    if not c_exists and not v_exists:
        print("\n[INFO] Nothing to clean up — container and volume do not exist.")
        sys.exit(0)

    # ── Teardown ──────────────────────────────────────────────────────────────
    if c_exists:
        stop_container(container)
        remove_container(container)
    else:
        print(f"[INFO] Container '{container}' does not exist, skipping.")

    if not args.keep_volume:
        if v_exists:
            remove_volume(volume)
        else:
            print(f"[INFO] Volume '{volume}' does not exist, skipping.")
    else:
        print(f"[INFO] --keep-volume: Preserving volume '{volume}'.")

    print("\n" + "=" * 70)
    print("  [DONE] Benchmark environment torn down.")
    print()
    print("  To recreate from scratch:")
    print("    make db-create")
    print("    # or: python performance/scripts/create_benchmark_db.py")
    print("=" * 70)


if __name__ == "__main__":
    main()

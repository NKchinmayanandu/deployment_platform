# ⚡ Performance Testing Suite

> **Project:** Deployment Platform — FastAPI + PostgreSQL + Redis + Docker + ARQ  
> **Purpose:** Production-grade benchmarking, bottleneck identification, and capacity planning.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start](#2-quick-start)
3. [Project Structure](#3-project-structure)
4. [Database Seeding](#4-database-seeding)
5. [k6 Test Scenarios](#5-k6-test-scenarios)
6. [Load Patterns Reference](#6-load-patterns-reference)
7. [Running Tests](#7-running-tests)
8. [Reports](#8-reports)
9. [Live Monitoring](#9-live-monitoring)
10. [Optimization Checklist](#10-optimization-checklist)
11. [Interpreting Results](#11-interpreting-results)
12. [Environment Variables](#12-environment-variables)

---

## 1. Prerequisites

### Required Tools

| Tool | Version | Install |
|------|---------|---------|
| k6 | ≥ 0.50 | See below |
| Python | ≥ 3.11 | System / pyenv |
| Docker | ≥ 24 | docker.com |
| PostgreSQL client (`psql`) | ≥ 15 | `apt install postgresql-client` |
| Redis client (`redis-cli`) | ≥ 7 | `apt install redis-tools` |
| `jq` | any | `apt install jq` |
| `tmux` | any | `apt install tmux` |

### Install k6

```bash
# Ubuntu / Debian
sudo gpg -k
sudo gpg --no-default-keyring \
  --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 \
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69

echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] \
  https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list

sudo apt-get update && sudo apt-get install k6

# macOS
brew install k6

# Docker (no install needed)
docker run --rm -i grafana/k6 run - <script.js
```

### Run the Setup Script (automated)

```bash
cd performance/
chmod +x scripts/setup.sh
./scripts/setup.sh
```

---

## 2. Quick Start

```bash
# 1. Start the application stack
cd /path/to/deployment_platform
docker compose up -d

# 2. Seed the database with realistic data
cd performance/seed
pip install -r requirements.txt
python seed.py

# 3. Run the smoke test first (always validate before load tests)
cd performance/
k6 run k6/scenarios/smoke_test.js

# 4. Run a full load test
k6 run k6/scenarios/load_test.js \
  --out json=reports/raw/load_test_$(date +%Y%m%d_%H%M%S).json

# 5. Generate a report from the raw output
./reports/generate_report.sh reports/raw/load_test_*.json
```

---

## 3. Project Structure

```
performance/
├── README.md                          ← You are here
│
├── k6/
│   ├── config/
│   │   └── options.js                 # Shared thresholds + all load stage definitions
│   ├── helpers/
│   │   ├── auth.js                    # JWT token management, login helper
│   │   └── data.js                    # Deterministic fake data generators (k6-side)
│   ├── scenarios/
│   │   ├── smoke_test.js              # 1–3 VUs, ~2 min, correctness validation
│   │   ├── load_test.js               # Steady-state: 10 → 1000 VUs, ~30 min
│   │   ├── stress_test.js             # Breaking point: ramp to 5000 VUs
│   │   ├── spike_test.js              # Burst: 10 → 2000 VUs instantly
│   │   └── soak_test.js               # Endurance: 100 VUs for 60 min
│   └── workflows/
│       ├── auth_flow.js               # Register → Login → /me
│       ├── application_flow.js        # Create → List → Get → Delete
│       └── deployment_flow.js         # Deploy → Status poll → Stop → Restart → Logs
│
├── seed/
│   ├── config.py                      # Row counts, batch sizes, toggles
│   ├── seed.py                        # Orchestrator — runs all seeders in order
│   ├── seeders/
│   │   ├── users.py                   # 10,000 users (bulk insert, bcrypt cost=4)
│   │   ├── applications.py            # 50,000 applications
│   │   ├── deployments.py             # 200,000 deployments with realistic statuses
│   │   └── logs.py                    # Up to 5,000,000 log lines (chunked)
│   └── requirements.txt               # faker, asyncpg, sqlalchemy[asyncio], bcrypt
│
├── monitoring/
│   ├── monitor.sh                     # Live tmux dashboard during test runs
│   ├── pg_stats.sql                   # PostgreSQL diagnostic queries
│   └── redis_stats.sh                 # Redis INFO, slow log, memory breakdown
│
├── reports/
│   ├── template.md                    # Report template with metric placeholders
│   └── generate_report.sh            # Parses k6 JSON → fills template
│
└── scripts/
    ├── setup.sh                       # Install deps, verify environment
    ├── run_all.sh                     # Run all 5 scenarios in sequence
    └── reset_db.sh                    # Drop + re-seed for a clean baseline
```

---

## 4. Database Seeding

The seeder generates statistically realistic data using Python's `Faker` library with
bulk inserts (never row-by-row) to keep seeding time under 5 minutes for all targets.

### Seeding Targets

| Entity | Default Count | Env Override |
|--------|--------------|--------------|
| Users | 10,000 | `SEED_USERS` |
| Applications | 50,000 | `SEED_APPS` |
| Deployments | 200,000 | `SEED_DEPLOYMENTS` |
| Logs | 5,000,000 | `SEED_LOGS` |

### Run the Seeder

```bash
cd performance/seed

# Default counts
python seed.py

# Custom counts
SEED_USERS=500 SEED_APPS=2000 SEED_DEPLOYMENTS=10000 SEED_LOGS=100000 python seed.py

# Seed only specific tables
SEED_ONLY=users,applications python seed.py

# Dry run — shows what would be inserted without writing
DRY_RUN=true python seed.py
```

### Seeder Design Choices

- **bcrypt cost factor = 4** during seeding (production uses 12). This is intentional —
  hashing 10,000 passwords at cost 12 would take ~8 hours. Cost 4 takes ~30 seconds.
  The passwords are still properly hashed and functional for testing.

- **Chunked bulk inserts** — rows are batched in groups of 2,000–5,000 per `INSERT`
  statement to avoid PostgreSQL packet size limits while maximizing throughput.

- **Realistic distributions** — deployment statuses follow a weighted distribution:
  `running` (50%), `stopped` (25%), `failed` (15%), `queued` (10%) to mimic production.

- **Idempotent** — the seeder checks existing row counts and skips tables that already
  meet the target, so re-running it is safe.

---

## 5. k6 Test Scenarios

### Smoke Test (`smoke_test.js`)
**Purpose:** Validate that the API is functionally correct before running load.  
**VUs:** 1–3 | **Duration:** ~2 minutes | **Run before any other test.**

Checks performed:
- All endpoints return correct HTTP status codes
- Auth tokens are valid
- Response bodies match expected shapes
- No 5xx errors

```bash
k6 run k6/scenarios/smoke_test.js
```

---

### Load Test (`load_test.js`)
**Purpose:** Measure performance under normal and peak expected load.  
**VUs:** Ramps 10 → 50 → 100 → 250 → 500 → 1000 | **Duration:** ~30 min

Stages:

| Stage | VUs | Duration | Purpose |
|-------|-----|----------|---------|
| Ramp up | 0 → 10 | 2 min | Warm up |
| Steady | 10 | 5 min | Baseline |
| Ramp up | 10 → 50 | 2 min | |
| Steady | 50 | 5 min | Normal load |
| Ramp up | 50 → 100 | 2 min | |
| Steady | 100 | 5 min | Peak normal |
| Ramp up | 100 → 250 | 3 min | |
| Steady | 250 | 5 min | High load |
| Ramp down | 250 → 0 | 3 min | Cool down |

**Key thresholds:**
- `p95 < 500ms` — 95th percentile response time under 500ms
- `http_req_failed < 1%` — less than 1% error rate
- `http_reqs > 100/s` — minimum throughput at peak load

```bash
k6 run k6/scenarios/load_test.js \
  --out json=reports/raw/load_$(date +%Y%m%d_%H%M%S).json
```

---

### Stress Test (`stress_test.js`)
**Purpose:** Find the application's breaking point. Push until errors spike.  
**VUs:** Ramps to 5,000 | **Duration:** ~45 min

This test intentionally pushes past the breaking point. You will see error rates climb —
that is the goal. Record at what VU count and RPS the system degrades.

```bash
k6 run k6/scenarios/stress_test.js \
  --out json=reports/raw/stress_$(date +%Y%m%d_%H%M%S).json
```

---

### Spike Test (`spike_test.js`)
**Purpose:** Simulate sudden burst traffic (viral event, cron job trigger, etc.)  
**Pattern:** 10 VUs → instant jump to 2,000 → instant drop back to 10

This tests:
- Connection pool behavior under sudden surge
- Redis queue saturation
- Auto-recovery after the spike

```bash
k6 run k6/scenarios/spike_test.js \
  --out json=reports/raw/spike_$(date +%Y%m%d_%H%M%S).json
```

---

### Soak Test (`soak_test.js`)
**Purpose:** Detect memory leaks, connection exhaustion, and performance degradation
over time. Run at moderate load for an extended period.  
**VUs:** 100 (constant) | **Duration:** 60 minutes

Watch for:
- Gradual latency increase (memory leak / GC pressure)
- Database connection pool exhaustion
- Redis memory growth
- Process RSS growth over time

```bash
k6 run k6/scenarios/soak_test.js \
  --out json=reports/raw/soak_$(date +%Y%m%d_%H%M%S).json
```

---

## 6. Load Patterns Reference

All patterns can be triggered via environment variable `LOAD_PROFILE`:

```bash
# Available profiles (defined in k6/config/options.js)
LOAD_PROFILE=10_users    k6 run k6/scenarios/load_test.js
LOAD_PROFILE=50_users    k6 run k6/scenarios/load_test.js
LOAD_PROFILE=100_users   k6 run k6/scenarios/load_test.js
LOAD_PROFILE=250_users   k6 run k6/scenarios/load_test.js
LOAD_PROFILE=500_users   k6 run k6/scenarios/load_test.js
LOAD_PROFILE=1000_users  k6 run k6/scenarios/load_test.js
LOAD_PROFILE=2000_users  k6 run k6/scenarios/load_test.js
LOAD_PROFILE=5000_users  k6 run k6/scenarios/load_test.js
```

---

## 7. Running Tests

### Against local stack

```bash
# Default (targets http://localhost:8000)
k6 run k6/scenarios/load_test.js

# Against a different host
BASE_URL=http://staging.example.com k6 run k6/scenarios/load_test.js
```

### Run all scenarios in sequence

```bash
./scripts/run_all.sh
# Outputs results to reports/raw/ with timestamps
# Generates a summary report in reports/summary_<date>.md
```

### Reset to a clean state between runs

```bash
# Truncates all seeded data and re-seeds from scratch
./scripts/reset_db.sh
```

---

## 8. Reports

k6 JSON output is parsed by `reports/generate_report.sh` into a structured Markdown
report (modelled on `reports/template.md`).

### Report Contents

- **Latency distribution:** min, p50, p90, p95, p99, max per endpoint
- **Throughput:** requests/sec, bytes/sec over time
- **Error analysis:** HTTP status distribution, failure rate
- **Scenario summary:** pass/fail against thresholds

```bash
./reports/generate_report.sh reports/raw/load_20240718_120000.json
# → reports/results/load_20240718_120000.md
```

---

## 9. Live Monitoring

### Quick monitoring (single terminal)

```bash
# Watch Docker stats during test
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Watch PostgreSQL active connections + query count
watch -n 2 'psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity WHERE state = '"'"'active'"'"';"'

# Watch Redis memory and ops/sec
watch -n 2 'redis-cli -u $REDIS_URL INFO stats | grep -E "instantaneous_ops|used_memory_human"'
```

### Full tmux dashboard (recommended)

```bash
# Opens a 4-pane tmux session with Docker stats, PG, Redis, and system metrics side by side
chmod +x monitoring/monitor.sh
./monitoring/monitor.sh
```

### PostgreSQL diagnostics (run during test)

```bash
psql $DATABASE_URL -f monitoring/pg_stats.sql
```

Surfaces:
- Slow queries (> 100ms)
- Index usage ratios
- Lock waits and blocking queries
- Connection pool saturation
- Table bloat and dead tuples

### Redis diagnostics

```bash
./monitoring/redis_stats.sh
```

Surfaces:
- Memory usage and fragmentation ratio
- Slow log entries
- Eviction counts
- Connected clients
- Queue depth (ARQ jobs)

### System-level monitoring

```bash
# CPU + memory breakdown per process
pidstat -u -r -p $(pgrep -f uvicorn) 1

# Network I/O
iftop -i lo     # loopback (Docker internal)
iftop -i eth0   # external interface

# Disk I/O (PostgreSQL WAL writes during load)
iostat -x 1
```

---

## 10. Optimization Checklist

Run this checklist after **every benchmark** to systematically diagnose bottlenecks.

---

### □ Database Bottleneck?

**Symptoms:** p99 > 1s, PostgreSQL CPU > 80%, slow query log filling up.

**How to verify:**
```sql
-- Check slow queries (pg_stat_statements required)
SELECT query, mean_exec_time, calls, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;

-- Check active queries right now
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle' AND query_start IS NOT NULL
ORDER BY duration DESC;
```

**Fix:** Add indexes, optimize queries, use `EXPLAIN ANALYZE`, add query result caching.

---

### □ Missing Indexes?

**Symptoms:** Sequential scans on large tables, slow `WHERE` clauses.

**How to verify:**
```sql
-- Find tables with high sequential scan ratios
SELECT schemaname, tablename, seq_scan, idx_scan,
       round(seq_scan::numeric / nullif(seq_scan + idx_scan, 0) * 100, 2) AS seq_pct
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_pct DESC;

-- Find missing indexes (high seq_scan on large tables)
SELECT relname, seq_scan, n_live_tup
FROM pg_stat_user_tables
WHERE seq_scan > 100 AND n_live_tup > 10000
ORDER BY seq_scan DESC;
```

**Fix:** `CREATE INDEX CONCURRENTLY` on filtered/joined/sorted columns.

---

### □ N+1 Queries?

**Symptoms:** Database query count grows linearly with response list size.
SQLAlchemy issues 1 query per related object instead of a JOIN.

**How to verify:**
```bash
# Enable SQLAlchemy query logging temporarily
# In app/core/config.py set: echo=True on create_async_engine

# Watch logs during a "List Applications" k6 run — if you see
# repeated SELECT statements for the same table, it's N+1.
```

**Fix:** Use `selectinload()` or `joinedload()` in SQLAlchemy queries.
```python
# Bad (N+1)
result = await db.execute(select(Application))

# Good (eager loading)
result = await db.execute(
    select(Application).options(selectinload(Application.deployment))
)
```

---

### □ Connection Pool Exhausted?

**Symptoms:** `TimeoutError: QueuePool limit of size X overflow Y reached`,
latency spikes at high VU counts, connections stuck in `idle in transaction`.

**How to verify:**
```sql
-- Count connections by state
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;

-- Check pool config in your engine
-- app/db/session.py — pool_size, max_overflow, pool_timeout
```

**Fix:**
```python
# In create_async_engine:
pool_size=20,        # Base connections (default: 5)
max_overflow=30,     # Burst connections above pool_size
pool_timeout=30,     # Seconds to wait before raising error
pool_pre_ping=True,  # Detect stale connections
```

---

### □ Redis Saturation?

**Symptoms:** ARQ jobs delayed, `redis-cli INFO` shows `blocked_clients > 0`,
memory near `maxmemory`, eviction count climbing.

**How to verify:**
```bash
redis-cli INFO memory | grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio"
redis-cli INFO stats | grep -E "evicted_keys|rejected_connections"
redis-cli SLOWLOG GET 10
```

**Fix:**
- Set `maxmemory-policy allkeys-lru` to prevent OOM
- Increase Redis `maxmemory` in `redis.conf`
- For ARQ: ensure workers are consuming jobs fast enough (scale workers)
- Check for jobs stuck in the queue: `redis-cli LLEN arq:queue:default`

---

### □ Docker Daemon Bottleneck?

**Symptoms:** Deployment tasks (spawn container) are slow, `docker stats` shows
high CPU on the Docker daemon process itself.

**How to verify:**
```bash
# Check Docker daemon CPU
pidstat -u -p $(pgrep dockerd) 1

# Check container count (large counts slow the daemon)
docker ps -q | wc -l

# Check Docker events lag
docker events --since 1m
```

**Fix:**
- Reduce number of simultaneously running containers
- Use `--cpus` and `--memory` limits per container to prevent noisy neighbors
- Consider moving Docker socket to a dedicated node for production

---

### □ Too Many Async Tasks?

**Symptoms:** FastAPI workers unresponsive despite low CPU, event loop lag > 100ms,
ARQ queue depth growing unbounded.

**How to verify:**
```bash
# Check ARQ queue depth
redis-cli LLEN arq:queue:default

# Check worker count
docker ps | grep arq_worker

# Monitor event loop lag (add to FastAPI startup):
# import asyncio
# asyncio.get_event_loop().set_debug(True)
```

**Fix:**
- Scale ARQ workers: `docker compose up --scale arq_worker=4`
- Add rate limiting to deployment endpoints
- Use ARQ job deduplication to prevent queue floods

---

### □ Slow Serialization?

**Symptoms:** High CPU on Pydantic model validation, slow response times even for
simple endpoints that make fast DB queries.

**How to verify:**
```bash
# Profile with py-spy during a load test
pip install py-spy
py-spy top --pid $(pgrep -f uvicorn)

# Look for pydantic, json, encode in the hot path
```

**Fix:**
- Use `model_config = {"from_attributes": True}` (already in your schemas ✅)
- Consider `orjson` for faster JSON serialization:
  ```bash
  pip install orjson
  ```
  ```python
  from fastapi.responses import ORJSONResponse
  app = FastAPI(default_response_class=ORJSONResponse)
  ```
- Limit response field count — don't serialize what the client doesn't need

---

### □ Logging Overhead?

**Symptoms:** Disk I/O spikes during load tests, CPU time in logging functions,
log file growing gigabytes in minutes.

**How to verify:**
```bash
# Monitor disk writes during test
iostat -x 1 | grep -E "sda|nvme"

# Check log level (is DEBUG on in production?)
grep -r "logging.DEBUG\|log_level.*debug" app/
```

**Fix:**
- Set `LOG_LEVEL=WARNING` during load tests
- Use async logging handlers
- Disable `access_log` in Uvicorn for high-throughput scenarios:
  ```bash
  uvicorn app.main:app --no-access-log
  ```

---

### □ Network Latency?

**Symptoms:** High latency between k6 runner and the API server, p99 dominated
by network RTT rather than application processing time.

**How to verify:**
```bash
# Baseline round-trip time to API
ping -c 100 <api_host> | tail -1

# Measure TCP connection time vs TTFB in k6
# k6 reports http_req_connecting, http_req_waiting, http_req_receiving separately
# If http_req_connecting is high → DNS or TCP handshake issue
# If http_req_waiting is high → server-side processing issue
```

**Fix:**
- Run k6 on the same machine or same datacenter as the server
- Enable HTTP keep-alive (FastAPI does this by default ✅)
- Use connection pooling at the load balancer level

---

## 11. Interpreting Results

### Latency Percentiles — What They Mean

| Metric | Meaning | Good Target |
|--------|---------|-------------|
| p50 (median) | Half of requests faster than this | < 100ms |
| p90 | 9 in 10 requests faster than this | < 300ms |
| p95 | 19 in 20 requests faster than this | < 500ms |
| p99 | 99 in 100 requests faster than this | < 1000ms |
| max | Worst single request | < 3000ms |

> **Rule of thumb:** If `p99 / p50 > 10x`, you have a severe tail latency problem —
> usually lock contention, connection pool exhaustion, or GC pauses.

### Throughput — What to Look For

- **Linear scaling:** If doubling VUs doubles RPS without latency increase → healthy.
- **Throughput ceiling:** RPS plateaus while latency climbs → found the bottleneck.
- **Error spike:** Sudden jump in 5xx errors → breaking point reached.

### Error Rate Budget

| Error Rate | Interpretation |
|-----------|----------------|
| < 0.1% | Excellent |
| 0.1% – 1% | Acceptable under load |
| 1% – 5% | Degraded — investigate immediately |
| > 5% | Critical — stop the test |

---

## 12. Environment Variables

All test scripts respect the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8000` | API base URL |
| `API_PREFIX` | `/api/v1` | API route prefix |
| `LOAD_PROFILE` | `100_users` | Load stage profile to use |
| `K6_VUS` | (from profile) | Override VU count |
| `K6_DURATION` | (from profile) | Override test duration |
| `SEED_USERS` | `10000` | Users to seed |
| `SEED_APPS` | `50000` | Applications to seed |
| `SEED_DEPLOYMENTS` | `200000` | Deployments to seed |
| `SEED_LOGS` | `5000000` | Log entries to seed |
| `SEED_ONLY` | (all) | Comma-separated list of tables to seed |
| `DRY_RUN` | `false` | Print what would be inserted, don't write |
| `DATABASE_URL` | from `.env` | PostgreSQL connection string |
| `REDIS_URL` | from `.env` | Redis connection string |

---

## Quick Reference Card

```bash
# Smoke (always first)
k6 run k6/scenarios/smoke_test.js

# Load (normal benchmarking)
k6 run k6/scenarios/load_test.js --out json=reports/raw/load.json

# Stress (breaking point)
k6 run k6/scenarios/stress_test.js --out json=reports/raw/stress.json

# Spike (burst traffic)
k6 run k6/scenarios/spike_test.js --out json=reports/raw/spike.json

# Soak (endurance)
k6 run k6/scenarios/soak_test.js --out json=reports/raw/soak.json

# Generate report
./reports/generate_report.sh reports/raw/load.json

# Live monitoring
./monitoring/monitor.sh

# Reset + re-seed
./scripts/reset_db.sh
```

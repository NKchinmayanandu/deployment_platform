#!/usr/bin/env bash
# performance/monitoring/monitor.sh
#
# All monitoring and reporting in one script.
# Subcommand-driven — run during k6 tests to observe system behaviour.
#
# Usage:
#   ./monitoring/monitor.sh watch     ← Live Docker + system stats (refresh every 2s)
#   ./monitoring/monitor.sh pg        ← PostgreSQL diagnostics (slow queries, locks, index usage)
#   ./monitoring/monitor.sh redis     ← Redis memory, slow log, queue depth
#   ./monitoring/monitor.sh report    ← Parse latest k6 JSON → Markdown report
#   ./monitoring/monitor.sh report path/to/output.json  ← Parse specific file
#   ./monitoring/monitor.sh all       ← pg + redis at once (no live watch)
#
# Run from the project root:
#   chmod +x performance/monitoring/monitor.sh
#   ./performance/monitoring/monitor.sh watch

set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.benchmark"
REPORTS_DIR="$PROJECT_ROOT/performance/reports"

# Load .env.benchmark variables (never .env)
if [[ -f "$ENV_FILE" ]]; then
  # Export only non-comment, non-empty lines
  set -a
  # shellcheck disable=SC1090
  source <(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$')
  set +a
fi

BENCH_HOST="${BENCHMARK_HOST:-localhost}"
BENCH_PORT="${BENCHMARK_PORT:-5433}"
BENCH_DB="${BENCHMARK_DB:-deployment_platform_benchmark}"
BENCH_CONTAINER="${BENCHMARK_CONTAINER_NAME:-pg_benchmark}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/1}"

# Extract Redis host/port from REDIS_URL
REDIS_HOST=$(echo "$REDIS_URL" | sed -E 's|redis://([^:]+):.*|\1|')
REDIS_PORT=$(echo "$REDIS_URL" | sed -E 's|redis://[^:]+:([0-9]+).*|\1|')
REDIS_DB=$(echo   "$REDIS_URL" | sed -E 's|.*/([0-9]+)$|\1|')

# ─── Colours ──────────────────────────────────────────────────────────────────

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

header() { echo -e "\n${BOLD}${CYAN}══ $1 ══${RESET}"; }
ok()     { echo -e "  ${GREEN}✓${RESET} $1"; }
warn()   { echo -e "  ${YELLOW}⚠${RESET}  $1"; }

# ─── Subcommands ──────────────────────────────────────────────────────────────

cmd_watch() {
  # ── Live dashboard: Docker stats + system CPU/mem every 2 seconds ──────────
  # Works without tmux — uses plain terminal output with clear screen

  echo -e "${BOLD}${CYAN}⚡ Live Performance Monitor${RESET}"
  echo -e "   Targeting: $BENCH_CONTAINER (PostgreSQL) + Redis"
  echo -e "   Press Ctrl+C to stop\n"

  while true; do
    clear
    echo -e "${BOLD}$(date '+%Y-%m-%d %H:%M:%S') — Live Monitor${RESET}"
    echo "────────────────────────────────────────────────────────────"

    # Docker stats (non-streaming, single snapshot)
    echo -e "\n${BOLD}Docker Containers:${RESET}"
    docker stats --no-stream --format \
      "  {{printf \"%-25s\" .Name}}  CPU: {{printf \"%6s\" .CPUPerc}}  MEM: {{printf \"%12s\" .MemUsage}}  NET: {{.NetIO}}" \
      2>/dev/null || echo "  (docker stats unavailable)"

    # System CPU (using /proc/stat snapshot comparison is complex — use top briefly)
    echo -e "\n${BOLD}System Resources:${RESET}"
    if command -v top &>/dev/null; then
      top -bn1 | grep -E "^(%Cpu|Cpu)" | head -1 | sed 's/^/  /'
      top -bn1 | grep -E "^MiB Mem|KiB Mem" | head -1 | sed 's/^/  /'
    fi

    # PostgreSQL active connections + longest query
    echo -e "\n${BOLD}PostgreSQL (benchmark DB):${RESET}"
    if docker exec "$BENCH_CONTAINER" pg_isready -U postgres -q 2>/dev/null; then
      # Active connection count
      CONN=$(docker exec "$BENCH_CONTAINER" psql -U postgres -d "$BENCH_DB" -t -c \
        "SELECT count(*) FROM pg_stat_activity WHERE state != 'idle';" 2>/dev/null | tr -d ' ')
      echo "  Active queries:  ${CONN:-?}"

      # Longest running query
      LONGEST=$(docker exec "$BENCH_CONTAINER" psql -U postgres -d "$BENCH_DB" -t -c \
        "SELECT COALESCE(ROUND(EXTRACT(EPOCH FROM MAX(now() - query_start))::numeric, 2)::text, '0') || 's'
         FROM pg_stat_activity WHERE state = 'active' AND query_start IS NOT NULL;" 2>/dev/null | tr -d ' ')
      echo "  Longest query:   ${LONGEST:-0s}"

      # TPS (transactions per second via pg_stat_database)
      TPS=$(docker exec "$BENCH_CONTAINER" psql -U postgres -d "$BENCH_DB" -t -c \
        "SELECT xact_commit + xact_rollback FROM pg_stat_database WHERE datname = '$BENCH_DB';" \
        2>/dev/null | tr -d ' ')
      echo "  Committed txns:  ${TPS:-?} (cumulative)"
    else
      warn "pg_benchmark container not reachable"
    fi

    # Redis
    echo -e "\n${BOLD}Redis (db ${REDIS_DB}):${RESET}"
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PING &>/dev/null; then
      OPS=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" INFO stats 2>/dev/null \
            | grep "instantaneous_ops_per_sec" | cut -d: -f2 | tr -d $'\r')
      MEM=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" INFO memory 2>/dev/null \
            | grep "used_memory_human" | head -1 | cut -d: -f2 | tr -d $'\r')
      CLIENTS=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" INFO clients 2>/dev/null \
            | grep "connected_clients" | cut -d: -f2 | tr -d $'\r')
      echo "  Ops/sec:         ${OPS:-?}"
      echo "  Memory:          ${MEM:-?}"
      echo "  Clients:         ${CLIENTS:-?}"

      # ARQ queue depth
      QUEUE=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" LLEN "arq:queue:default" 2>/dev/null || echo "?")
      echo "  ARQ queue depth: ${QUEUE}"
    else
      warn "Redis not reachable at ${REDIS_HOST}:${REDIS_PORT}"
    fi

    echo -e "\n────────────────────────────────────────────────────────────"
    echo "  Refreshing in 2s... (Ctrl+C to exit)"
    sleep 2
  done
}

cmd_pg() {
  # ── PostgreSQL diagnostics — run once, prints detailed diagnostics ──────────

  header "PostgreSQL Diagnostics — $BENCH_DB"

  if ! docker exec "$BENCH_CONTAINER" pg_isready -U postgres -q 2>/dev/null; then
    echo -e "  ${RED}✗ Cannot connect to $BENCH_CONTAINER${RESET}"
    echo "    Run: python performance/scripts/create_benchmark_db.py"
    exit 1
  fi

  psql_exec() {
    docker exec "$BENCH_CONTAINER" psql -U postgres -d "$BENCH_DB" \
      --pset=border=2 --pset=format=aligned -c "$1" 2>/dev/null
  }

  # 1. Connection summary
  echo -e "\n${BOLD}Active Connections by State:${RESET}"
  psql_exec "SELECT state, count(*) AS connections
             FROM pg_stat_activity
             GROUP BY state ORDER BY connections DESC;"

  # 2. Slow queries (requires pg_stat_statements extension)
  echo -e "\n${BOLD}Slowest Queries (requires pg_stat_statements):${RESET}"
  psql_exec "SELECT
               LEFT(query, 80)            AS query_snippet,
               ROUND(mean_exec_time::numeric, 2) AS avg_ms,
               calls,
               ROUND(total_exec_time::numeric, 2) AS total_ms
             FROM pg_stat_statements
             ORDER BY mean_exec_time DESC
             LIMIT 10;" 2>/dev/null || \
    echo "  pg_stat_statements not enabled. Add to postgresql.conf: shared_preload_libraries = 'pg_stat_statements'"

  # 3. Lock waits
  echo -e "\n${BOLD}Lock Waits (blocking queries):${RESET}"
  psql_exec "SELECT
               blocked.pid,
               blocked.query                          AS blocked_query,
               blocking.pid                           AS blocking_pid,
               blocking.query                         AS blocking_query
             FROM pg_stat_activity blocked
             JOIN pg_stat_activity blocking
               ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
             WHERE NOT blocked.granted;"

  # 4. Index usage — find tables with low index hit rate
  echo -e "\n${BOLD}Index Hit Rate by Table (low % = missing indexes):${RESET}"
  psql_exec "SELECT
               relname                                       AS table_name,
               COALESCE(idx_scan, 0)                         AS index_scans,
               COALESCE(seq_scan, 0)                         AS seq_scans,
               CASE WHEN (idx_scan + seq_scan) = 0 THEN 'N/A'
                    ELSE ROUND(idx_scan::numeric / (idx_scan + seq_scan) * 100, 1)::text || '%'
               END                                           AS index_hit_rate,
               n_live_tup                                    AS live_rows
             FROM pg_stat_user_tables
             ORDER BY seq_scans DESC
             LIMIT 15;"

  # 5. Table sizes
  echo -e "\n${BOLD}Table Sizes:${RESET}"
  psql_exec "SELECT
               tablename,
               pg_size_pretty(pg_total_relation_size('\"' || tablename || '\"')) AS total_size,
               pg_size_pretty(pg_relation_size('\"' || tablename || '\"'))        AS table_size,
               pg_size_pretty(pg_indexes_size('\"' || tablename || '\"'))         AS index_size
             FROM pg_tables
             WHERE schemaname = 'public'
             ORDER BY pg_total_relation_size('\"' || tablename || '\"') DESC;"

  # 6. Cache hit rate (should be > 99% for a hot DB)
  echo -e "\n${BOLD}Buffer Cache Hit Rate (target > 99%):${RESET}"
  psql_exec "SELECT
               ROUND(
                 sum(heap_blks_hit)::numeric / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100,
                 2
               ) AS cache_hit_pct
             FROM pg_statio_user_tables;"
}

cmd_redis() {
  # ── Redis diagnostics ────────────────────────────────────────────────────────

  header "Redis Diagnostics — ${REDIS_HOST}:${REDIS_PORT} db=${REDIS_DB}"

  if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PING &>/dev/null; then
    echo -e "  ${RED}✗ Cannot connect to Redis at ${REDIS_HOST}:${REDIS_PORT}${RESET}"
    exit 1
  fi

  r() { redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" "$@" 2>/dev/null; }

  echo -e "\n${BOLD}Memory:${RESET}"
  r INFO memory | grep -E "used_memory_human|used_memory_peak_human|mem_fragmentation_ratio|maxmemory_human" \
    | sed 's/^/  /'

  echo -e "\n${BOLD}Stats:${RESET}"
  r INFO stats | grep -E "instantaneous_ops|total_commands|rejected_connections|evicted_keys" \
    | sed 's/^/  /'

  echo -e "\n${BOLD}Clients:${RESET}"
  r INFO clients | grep -E "connected_clients|blocked_clients" | sed 's/^/  /'

  echo -e "\n${BOLD}ARQ Queue Depth:${RESET}"
  ARQ_DEPTH=$(r LLEN "arq:queue:default")
  echo "  arq:queue:default = ${ARQ_DEPTH:-0} pending jobs"

  echo -e "\n${BOLD}Slow Log (last 10 entries):${RESET}"
  SLOWLOG=$(r SLOWLOG GET 10)
  if [[ -z "$SLOWLOG" ]]; then
    ok "No slow log entries"
  else
    echo "$SLOWLOG" | head -40 | sed 's/^/  /'
    echo ""
    echo "  (slowlog-log-slower-than default: 10000 microseconds)"
  fi

  echo -e "\n${BOLD}Key Count by Pattern:${RESET}"
  for pattern in "arq:*" "token:*" "cache:*"; do
    COUNT=$(r EVAL "return #redis.call('keys','$pattern')" 0 2>/dev/null || echo "?")
    echo "  $pattern  →  $COUNT keys"
  done
}

cmd_report() {
  # ── Parse k6 JSON output → structured Markdown report ────────────────────────
  # k6 --out json emits one JSON object per line (NDJSON format)

  local json_file="${1:-}"

  # Find the most recent JSON file if none specified
  if [[ -z "$json_file" ]]; then
    json_file=$(ls -t "$REPORTS_DIR"/raw/*.json 2>/dev/null | head -1)
    if [[ -z "$json_file" ]]; then
      echo -e "${RED}[ERROR] No JSON files found in $REPORTS_DIR/raw/${RESET}"
      echo "  Run a test first: make smoke"
      exit 1
    fi
  fi

  if [[ ! -f "$json_file" ]]; then
    echo -e "${RED}[ERROR] File not found: $json_file${RESET}"
    exit 1
  fi

  if ! command -v jq &>/dev/null; then
    echo -e "${RED}[ERROR] jq is required for report generation.${RESET}"
    echo "  Install: sudo apt install jq   or   brew install jq"
    exit 1
  fi

  local scenario
  scenario=$(basename "$json_file" | sed -E 's/_[0-9]+\.json$//')
  local outfile="$REPORTS_DIR/results/${scenario}_$(date +%Y%m%d_%H%M%S).md"
  mkdir -p "$REPORTS_DIR/results"

  header "Generating Report from $(basename "$json_file")"

  # Extract summary metrics from k6 NDJSON output
  # k6 JSON output format: { "type": "Point", "metric": "http_req_duration", "data": { ... } }
  # Summary metrics are emitted as type="Metric" at the end of the run.

  # Use jq to extract the summary line (type=Metric has aggregate data)
  METRICS=$(jq -s '
    [ .[] | select(.type == "Point") ] |
    {
      total_requests:   ( [.[] | select(.metric == "http_reqs")] | length ),
      failed:           ( [.[] | select(.metric == "http_req_failed") | .data.value] | add // 0 ),
      p50:  ( [.[] | select(.metric == "http_req_duration") | .data.value] | sort | .[ (length * 0.50) | floor ] // 0 | . * 100 | round / 100 ),
      p90:  ( [.[] | select(.metric == "http_req_duration") | .data.value] | sort | .[ (length * 0.90) | floor ] // 0 | . * 100 | round / 100 ),
      p95:  ( [.[] | select(.metric == "http_req_duration") | .data.value] | sort | .[ (length * 0.95) | floor ] // 0 | . * 100 | round / 100 ),
      p99:  ( [.[] | select(.metric == "http_req_duration") | .data.value] | sort | .[ (length * 0.99) | floor ] // 0 | . * 100 | round / 100 ),
      max:  ( [.[] | select(.metric == "http_req_duration") | .data.value] | max // 0 | . * 100 | round / 100 ),
      min:  ( [.[] | select(.metric == "http_req_duration") | .data.value] | min // 0 | . * 100 | round / 100 )
    }
  ' "$json_file" 2>/dev/null)

  # Per-endpoint breakdown (tagged requests)
  ENDPOINTS=$(jq -rs '
    [ .[] | select(.type == "Point" and .metric == "http_req_duration") ] |
    group_by(.data.tags.endpoint) |
    .[] |
    {
      endpoint: .[0].data.tags.endpoint,
      count:    length,
      p50:  ( [.[].data.value] | sort | .[ (length * 0.50) | floor ] // 0 | . * 10 | round / 10 ),
      p95:  ( [.[].data.value] | sort | .[ (length * 0.95) | floor ] // 0 | . * 10 | round / 10 ),
      p99:  ( [.[].data.value] | sort | .[ (length * 0.99) | floor ] // 0 | . * 10 | round / 10 ),
      max:  ( [.[].data.value] | max // 0 | . * 10 | round / 10 )
    } |
    "| \(.endpoint // "unknown") | \(.count) | \(.p50)ms | \(.p95)ms | \(.p99)ms | \(.max)ms |"
  ' "$json_file" 2>/dev/null)

  TOTAL_REQ=$(echo "$METRICS" | jq -r '.total_requests // "?"')
  FAIL_COUNT=$(echo "$METRICS" | jq -r '.failed // "?"')
  P50=$(echo "$METRICS"  | jq -r '.p50 // "?"')
  P90=$(echo "$METRICS"  | jq -r '.p90 // "?"')
  P95=$(echo "$METRICS"  | jq -r '.p95 // "?"')
  P99=$(echo "$METRICS"  | jq -r '.p99 // "?"')
  MAX=$(echo "$METRICS"  | jq -r '.max // "?"')
  MIN=$(echo "$METRICS"  | jq -r '.min // "?"')

  # Write the Markdown report
  cat > "$outfile" <<REPORT
# Performance Report — ${scenario}

**Date:** $(date '+%Y-%m-%d %H:%M:%S')
**Source:** $(basename "$json_file")
**Project:** deployment_platform (FastAPI + PostgreSQL + Redis + ARQ)

---

## Summary

| Metric | Value |
|--------|-------|
| Total Requests | ${TOTAL_REQ} |
| Failed Requests | ${FAIL_COUNT} |
| Min Latency | ${MIN}ms |
| p50 (Median) | ${P50}ms |
| p90 | ${P90}ms |
| p95 | ${P95}ms |
| p99 | ${P99}ms |
| Max Latency | ${MAX}ms |

---

## Per-Endpoint Breakdown

| Endpoint | Count | p50 | p95 | p99 | Max |
|----------|-------|-----|-----|-----|-----|
${ENDPOINTS}

---

## Optimization Checklist

After reviewing the numbers above, check each item:

- [ ] **Database bottleneck?** Run: \`make pg-stats\`
- [ ] **Missing indexes?** Look for tables with low index hit rate in pg-stats output
- [ ] **N+1 queries?** Enable SQLAlchemy echo and check for repeated SELECTs per request
- [ ] **Connection pool exhausted?** If p99 >> p95, likely pool timeout — increase pool_size
- [ ] **Redis saturation?** Run: \`make redis-stats\` — check evicted_keys and blocked_clients
- [ ] **ARQ queue backup?** Check queue depth: \`redis-cli LLEN arq:queue:default\`
- [ ] **Logging overhead?** Check disk I/O during test: \`iostat -x 1\`
- [ ] **Slow serialization?** If CPU high but DB fast, check Pydantic model complexity
- [ ] **Network latency?** Compare http_req_waiting vs http_req_connecting in k6 output

---

## Raw File

\`\`\`
$json_file
\`\`\`
REPORT

  ok "Report written to: $outfile"
  echo ""
  cat "$outfile"
}

# ─── Router ───────────────────────────────────────────────────────────────────

SUBCOMMAND="${1:-help}"
shift || true

case "$SUBCOMMAND" in
  watch)   cmd_watch ;;
  pg)      cmd_pg ;;
  redis)   cmd_redis ;;
  report)  cmd_report "${1:-}" ;;
  all)     cmd_pg; echo ""; cmd_redis ;;
  help|--help|-h)
    echo ""
    echo -e "${BOLD}${CYAN}monitor.sh${RESET} — Benchmark monitoring & reporting"
    echo ""
    echo "  Usage: ./monitoring/monitor.sh <subcommand>"
    echo ""
    echo -e "  ${CYAN}watch${RESET}             Live dashboard (Docker + PG + Redis), refreshes every 2s"
    echo -e "  ${CYAN}pg${RESET}                PostgreSQL diagnostics (slow queries, locks, index hit rate)"
    echo -e "  ${CYAN}redis${RESET}             Redis memory, ops/sec, slow log, ARQ queue depth"
    echo -e "  ${CYAN}report [file]${RESET}     Parse k6 JSON → Markdown report (uses latest if no file given)"
    echo -e "  ${CYAN}all${RESET}               Run pg + redis diagnostics together"
    echo ""
    echo "  Reads database config from: .env.benchmark"
    echo ""
    ;;
  *)
    echo -e "${RED}Unknown subcommand: $SUBCOMMAND${RESET}"
    echo "  Run: ./monitoring/monitor.sh help"
    exit 1
    ;;
esac

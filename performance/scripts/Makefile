# =============================================================================
# performance/scripts/Makefile
#
# One-command benchmark workflow for the Deployment Platform.
#
# USAGE:
#   cd performance/scripts/
#   make help             ← Show all available commands
#   make benchmark        ← Full end-to-end: create DB → seed → start app → run tests
#   make db-create        ← Create isolated benchmark DB + run migrations
#   make seed             ← Seed benchmark DB with default dataset (10k/50k/200k/5M)
#   make smoke            ← Quick correctness check (< 2 min)
#   make load             ← Full load test (30 min)
#   make report           ← Generate HTML/Markdown report from last run
#
# Run from the PROJECT ROOT:
#   make -f performance/scripts/Makefile <target>
#
# Or cd into performance/scripts/ and run: make <target>
# =============================================================================

# ─── Configuration ────────────────────────────────────────────────────────────

# Detect project root (two levels up from this Makefile)
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(MAKEFILE_DIR)../..)

# Python interpreter — use virtual env if present
PYTHON := $(shell [ -f "$(PROJECT_ROOT)/.venv/bin/python" ] && echo "$(PROJECT_ROOT)/.venv/bin/python" || echo "python3")

# k6 binary — override via: K6=docker make smoke
K6 := k6

# Load profile for load/stress tests — override via: LOAD_PROFILE=500_users make load
LOAD_PROFILE := 100_users

# Base URL for k6 — override via: BASE_URL=http://staging.example.com make load
BASE_URL := http://localhost:8000

# API prefix — must match settings.API_PREFIX in FastAPI config
API_PREFIX := /api

# Timestamp for output files
TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)

# Report output directory
REPORTS_DIR := $(PROJECT_ROOT)/performance/reports/raw

# Performance scripts dir
PERF_DIR := $(PROJECT_ROOT)/performance

# ─── Colors ───────────────────────────────────────────────────────────────────

BOLD  := \033[1m
GREEN := \033[0;32m
CYAN  := \033[0;36m
YELLOW:= \033[0;33m
RED   := \033[0;31m
RESET := \033[0m

# =============================================================================
# PHONY TARGETS (not file names)
# =============================================================================

.PHONY: help benchmark \
        db-create db-reset db-drop \
        seed seed-small seed-large \
        app-start app-stop \
        smoke load stress spike soak run-all \
        report monitor \
        setup clean

# =============================================================================
# HELP
# =============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(BOLD)⚡ Deployment Platform — Performance Benchmark Suite$(RESET)"
	@echo ""
	@echo "$(BOLD)Database:$(RESET)"
	@grep -E '^db-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Seeding:$(RESET)"
	@grep -E '^seed[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Application:$(RESET)"
	@grep -E '^app-[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Tests:$(RESET)"
	@grep -E '^(smoke|load|stress|spike|soak|run-all):.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Utilities:$(RESET)"
	@grep -E '^(report|monitor|setup|clean|benchmark):.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)Environment Overrides:$(RESET)"
	@echo "  $(YELLOW)LOAD_PROFILE$(RESET)=500_users make load   # Options: 10_users, 50_users, 100_users,"
	@echo "                                        #          250_users, 500_users, 1000_users,"
	@echo "                                        #          2000_users, 5000_users"
	@echo "  $(YELLOW)BASE_URL$(RESET)=http://staging.com make load"
	@echo "  $(YELLOW)K6$(RESET)='docker run --rm -i grafana/k6' make smoke  # Use Docker k6"
	@echo ""

# =============================================================================
# FULL WORKFLOW
# =============================================================================

benchmark: ## Full benchmark: create DB → migrate → seed → (manual: start app) → run all tests → report
	@echo "$(BOLD)$(GREEN)▶ Starting full benchmark workflow...$(RESET)"
	@echo ""
	@echo "$(YELLOW)Step 1/5: Creating benchmark database...$(RESET)"
	@$(MAKE) db-create
	@echo ""
	@echo "$(YELLOW)Step 2/5: Seeding database...$(RESET)"
	@$(MAKE) seed
	@echo ""
	@echo "$(BOLD)$(YELLOW)⚠  Step 3/5: MANUAL ACTION REQUIRED$(RESET)"
	@echo "$(YELLOW)   Start FastAPI with benchmark config in a separate terminal:$(RESET)"
	@echo "   $(CYAN)ENV_FILE=.env.benchmark uvicorn app.main:app --host 0.0.0.0 --port 8000$(RESET)"
	@echo ""
	@echo "   Then press ENTER to continue with k6 tests..."
	@read -p "" _
	@echo ""
	@echo "$(YELLOW)Step 4/5: Running all k6 test scenarios...$(RESET)"
	@$(MAKE) run-all
	@echo ""
	@echo "$(YELLOW)Step 5/5: Generating report...$(RESET)"
	@$(MAKE) report
	@echo ""
	@echo "$(GREEN)$(BOLD)✓ Benchmark complete! Reports are in performance/reports/$(RESET)"

# =============================================================================
# DATABASE TARGETS
# =============================================================================

db-create: ## Create isolated benchmark PostgreSQL container + run Alembic migrations
	@echo "$(CYAN)▶ Creating benchmark database...$(RESET)"
	cd $(PROJECT_ROOT) && $(PYTHON) performance/scripts/create_benchmark_db.py

db-create-skip-migrate: ## Create benchmark DB container without running migrations
	@echo "$(CYAN)▶ Creating benchmark database (no migrations)...$(RESET)"
	cd $(PROJECT_ROOT) && $(PYTHON) performance/scripts/create_benchmark_db.py --skip-migrations

db-reset: ## Truncate all tables + reset sequences (keeps container and schema)
	@echo "$(CYAN)▶ Resetting benchmark database (truncate only)...$(RESET)"
	cd $(PROJECT_ROOT) && $(PYTHON) performance/scripts/reset_benchmark_db.py

db-reset-seed: ## Truncate all tables + re-seed with default dataset
	@echo "$(CYAN)▶ Resetting + re-seeding benchmark database...$(RESET)"
	cd $(PROJECT_ROOT) && $(PYTHON) performance/scripts/reset_benchmark_db.py --seed

db-drop: ## ⚠  Permanently destroy benchmark container + volume (all data lost)
	@echo "$(RED)$(BOLD)⚠  WARNING: This will permanently delete all benchmark data$(RESET)"
	cd $(PROJECT_ROOT) && $(PYTHON) performance/scripts/drop_benchmark_db.py

db-drop-yes: ## ⚠  Force drop without confirmation prompt (for CI)
	cd $(PROJECT_ROOT) && $(PYTHON) performance/scripts/drop_benchmark_db.py --yes

db-status: ## Show benchmark container status
	@echo "$(CYAN)▶ Benchmark container status:$(RESET)"
	@docker ps -a --filter "name=pg_benchmark" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "$(CYAN)▶ Benchmark volume:$(RESET)"
	@docker volume ls --filter "name=pg_benchmark_data" 2>/dev/null || echo "  (not found)"

# =============================================================================
# SEEDING TARGETS
# =============================================================================

seed: ## Seed benchmark DB with default dataset (10k users, 50k apps, 200k deployments, 5M logs)
	@echo "$(CYAN)▶ Seeding benchmark database (default dataset)...$(RESET)"
	@mkdir -p $(PROJECT_ROOT)/performance/reports/raw
	cd $(PROJECT_ROOT) && \
		SEED_USERS=10000 \
		SEED_APPS=50000 \
		SEED_DEPLOYMENTS=200000 \
		SEED_LOGS=5000000 \
		$(PYTHON) performance/seed/seed.py

seed-small: ## Seed with small dataset (500 users, 2k apps, 10k deployments, 100k logs) — fast for dev
	@echo "$(CYAN)▶ Seeding benchmark database (small dataset)...$(RESET)"
	cd $(PROJECT_ROOT) && \
		SEED_USERS=500 \
		SEED_APPS=2000 \
		SEED_DEPLOYMENTS=10000 \
		SEED_LOGS=100000 \
		$(PYTHON) performance/seed/seed.py

seed-large: ## Seed with large dataset (50k users, 200k apps, 500k deployments, 10M logs) — slow
	@echo "$(CYAN)▶ Seeding benchmark database (large dataset)...$(RESET)"
	cd $(PROJECT_ROOT) && \
		SEED_USERS=50000 \
		SEED_APPS=200000 \
		SEED_DEPLOYMENTS=500000 \
		SEED_LOGS=10000000 \
		$(PYTHON) performance/seed/seed.py

seed-custom: ## Seed with custom counts — set SEED_USERS, SEED_APPS, SEED_DEPLOYMENTS, SEED_LOGS
	@echo "$(CYAN)▶ Seeding benchmark database (custom dataset)...$(RESET)"
	@echo "  Users: $(SEED_USERS) | Apps: $(SEED_APPS) | Deployments: $(SEED_DEPLOYMENTS) | Logs: $(SEED_LOGS)"
	cd $(PROJECT_ROOT) && $(PYTHON) performance/seed/seed.py

# =============================================================================
# APPLICATION TARGETS
# =============================================================================

app-start: ## Start FastAPI with benchmark configuration (foreground)
	@echo "$(CYAN)▶ Starting FastAPI with .env.benchmark...$(RESET)"
	@echo "   DATABASE_URL → local Docker PostgreSQL on port 5433"
	@echo "   Press Ctrl+C to stop"
	@echo ""
	cd $(PROJECT_ROOT) && \
		ENV_FILE=.env.benchmark \
		$(shell grep -v '^#' $(PROJECT_ROOT)/.env.benchmark | grep -v '^$$' | xargs) \
		uvicorn app.main:app \
			--host 0.0.0.0 \
			--port 8000 \
			--no-access-log \
			--log-level warning

app-start-dev: ## Start FastAPI with benchmark config + auto-reload (for debugging)
	@echo "$(CYAN)▶ Starting FastAPI (benchmark config, dev mode)...$(RESET)"
	cd $(PROJECT_ROOT) && \
		$(shell grep -v '^#' $(PROJECT_ROOT)/.env.benchmark | grep -v '^$$' | xargs) \
		uvicorn app.main:app \
			--host 0.0.0.0 \
			--port 8000 \
			--reload \
			--log-level info

app-health: ## Check if the FastAPI app is responding
	@curl -sf $(BASE_URL)/health | python3 -m json.tool || \
		(echo "$(RED)✗ App not responding at $(BASE_URL)/health$(RESET)" && exit 1)

# =============================================================================
# K6 TEST TARGETS
# =============================================================================

smoke: ## Smoke test — quick correctness check (1-3 VUs, ~2 min)
	@echo "$(CYAN)▶ Running smoke test...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	BASE_URL=$(BASE_URL) API_PREFIX=$(API_PREFIX) \
	$(K6) run \
		--out json=$(REPORTS_DIR)/smoke_$(TIMESTAMP).json \
		$(PERF_DIR)/k6/scenarios/smoke_test.js

load: ## Load test — steady-state benchmarking (default: 100 users, ~30 min)
	@echo "$(CYAN)▶ Running load test [profile: $(LOAD_PROFILE)]...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	BASE_URL=$(BASE_URL) API_PREFIX=$(API_PREFIX) LOAD_PROFILE=$(LOAD_PROFILE) \
	$(K6) run \
		--out json=$(REPORTS_DIR)/load_$(TIMESTAMP).json \
		$(PERF_DIR)/k6/scenarios/load_test.js

stress: ## Stress test — find breaking point (ramps to 5000 VUs)
	@echo "$(CYAN)▶ Running stress test...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	BASE_URL=$(BASE_URL) API_PREFIX=$(API_PREFIX) \
	$(K6) run \
		--out json=$(REPORTS_DIR)/stress_$(TIMESTAMP).json \
		$(PERF_DIR)/k6/scenarios/stress_test.js

spike: ## Spike test — sudden burst traffic (10 → 2000 VUs instantly)
	@echo "$(CYAN)▶ Running spike test...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	BASE_URL=$(BASE_URL) API_PREFIX=$(API_PREFIX) \
	$(K6) run \
		--out json=$(REPORTS_DIR)/spike_$(TIMESTAMP).json \
		$(PERF_DIR)/k6/scenarios/spike_test.js

soak: ## Soak test — 100 VUs for 60 min (memory leak / endurance)
	@echo "$(CYAN)▶ Running soak test (60 min)...$(RESET)"
	@mkdir -p $(REPORTS_DIR)
	BASE_URL=$(BASE_URL) API_PREFIX=$(API_PREFIX) \
	$(K6) run \
		--out json=$(REPORTS_DIR)/soak_$(TIMESTAMP).json \
		$(PERF_DIR)/k6/scenarios/soak_test.js

run-all: ## Run all 5 test scenarios in sequence (smoke → load → stress → spike → soak)
	@echo "$(BOLD)$(CYAN)▶ Running all scenarios in sequence...$(RESET)"
	@$(MAKE) smoke && \
	$(MAKE) load && \
	$(MAKE) stress && \
	$(MAKE) spike && \
	$(MAKE) soak
	@echo "$(GREEN)$(BOLD)✓ All scenarios complete!$(RESET)"

# Custom load profile shortcuts
load-10:    LOAD_PROFILE=10_users
load-10:    load    ## Load test with 10 VUs

load-50:    LOAD_PROFILE=50_users
load-50:    load    ## Load test with 50 VUs

load-250:   LOAD_PROFILE=250_users
load-250:   load    ## Load test with 250 VUs

load-500:   LOAD_PROFILE=500_users
load-500:   load    ## Load test with 500 VUs

load-1000:  LOAD_PROFILE=1000_users
load-1000:  load    ## Load test with 1000 VUs

load-2000:  LOAD_PROFILE=2000_users
load-2000:  load    ## Load test with 2000 VUs

load-5000:  LOAD_PROFILE=5000_users
load-5000:  load    ## Load test with 5000 VUs

# =============================================================================
# REPORTING
# =============================================================================

report: ## Generate Markdown report from the most recent k6 JSON output
	@echo "$(CYAN)▶ Generating report from latest run...$(RESET)"
	@LATEST=$$(ls -t $(REPORTS_DIR)/*.json 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then \
		echo "$(RED)No JSON output files found in $(REPORTS_DIR)$(RESET)"; \
		echo "Run a test first: make smoke"; \
		exit 1; \
	fi; \
	echo "  Input: $$LATEST"; \
	$(PERF_DIR)/reports/generate_report.sh "$$LATEST"

report-all: ## Generate reports for ALL JSON files in reports/raw/
	@echo "$(CYAN)▶ Generating reports for all runs...$(RESET)"
	@for f in $(REPORTS_DIR)/*.json; do \
		$(PERF_DIR)/reports/generate_report.sh "$$f"; \
	done

# =============================================================================
# MONITORING
# =============================================================================

monitor: ## Launch live monitoring dashboard (requires tmux)
	@echo "$(CYAN)▶ Starting monitoring dashboard...$(RESET)"
	$(PERF_DIR)/monitoring/monitor.sh

pg-stats: ## Run PostgreSQL diagnostic queries against benchmark DB
	@echo "$(CYAN)▶ PostgreSQL diagnostics...$(RESET)"
	@docker exec pg_benchmark psql -U bench_user -d deployment_platform_benchmark \
		-f /dev/stdin < $(PERF_DIR)/monitoring/pg_stats.sql

redis-stats: ## Show Redis memory, slow log, and queue depth
	@echo "$(CYAN)▶ Redis diagnostics...$(RESET)"
	$(PERF_DIR)/monitoring/redis_stats.sh

# =============================================================================
# SETUP & CLEANUP
# =============================================================================

setup: ## Install k6, Python dependencies, and verify Docker
	@echo "$(CYAN)▶ Running setup...$(RESET)"
	$(PERF_DIR)/scripts/setup.sh

clean: ## Remove all generated reports and temporary files
	@echo "$(CYAN)▶ Cleaning up reports...$(RESET)"
	@find $(REPORTS_DIR) -name "*.json" -mtime +7 -delete && echo "  Deleted reports older than 7 days"
	@find $(PERF_DIR)/reports/results -name "*.md" -mtime +7 -delete 2>/dev/null || true
	@echo "[OK] Cleanup done"

clean-all: ## Remove ALL generated reports (no age filter)
	@echo "$(RED)▶ Removing all generated reports...$(RESET)"
	@rm -f $(REPORTS_DIR)/*.json
	@rm -f $(PERF_DIR)/reports/results/*.md
	@echo "[OK] All reports removed"

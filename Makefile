SHELL := /bin/sh
.DEFAULT_GOAL := help

REPEATS ?= 5
SCENARIO ?=
RECORDS ?= 1000
OBJECTS ?= 200
OUT ?= .work/perf
LOCAL ?=
CF ?= cf
WORKER_DIR ?= tools/agent-memory/cloudflare
DATABASE_ID := $(shell jaq --from toml -r '.d1_databases[0].database_id' $(WORKER_DIR)/wrangler.toml 2>/dev/null)
MIGRATE_FLAGS := $(if $(filter 1,$(LOCAL)),--local --persist-to $(CURDIR)/.work/tmp/cf-state)
PYTHON := uv run --no-project --python '>=3.15' python -I
PERF := tools/agent-memory/cloudflare/perf.sh
SUITES := test_sessions test_archive test_transfer test_identity test_recovery test_learning_ops test_learning_review test_recall test_learning test_learning_promote test_mirror
CAMPAIGN_PYTHON := tools/agent-memory/eval/bench_mirror.py tools/agent-memory/src/agent_memory/mirror.py tools/agent-memory/src/agent_memory/mirror_crypto.py tools/agent-memory/tests/test_mirror.py tools/agent-memory/tests/test_mirror_crypto.py
GIT_TEMPLATE_DIR ?= $(wildcard /opt/homebrew/share/git-core/templates)
ENV_GIT := $(if $(GIT_TEMPLATE_DIR),GIT_TEMPLATE_DIR=$(GIT_TEMPLATE_DIR))

.PHONY: help deploy worker-bundle worker-test worker-check worker-deploy smoke-deployed migrate provision provision-access observe perf-local perf-worker perf-deployed perf-report test test-all

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z][a-z0-9-]*:.*## / {printf "%-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

deploy: ## Gate, test, deploy, and smoke the Worker
	CF_BIN="$(CF)" sh $(WORKER_DIR)/scripts/deploy-gate.sh
	$(MAKE) worker-test worker-deploy
	$(MAKE) smoke-deployed

worker-bundle: ## Build the Worker bundle once for test and deploy
	cd $(WORKER_DIR) && $(CF) build --mode production

worker-test: worker-bundle ## Exercise the built bundle and protocol parity
	cd $(WORKER_DIR) && npm run test:runtime && npm run test:protocol

worker-check: ## Validate the Worker deploy plan without uploading
	cd $(WORKER_DIR) && $(CF) deploy --dry-run

worker-deploy: worker-bundle ## Deploy the bundle worker-test exercised
	cd $(WORKER_DIR) && $(CF) deploy --prebuilt --mode production

smoke-deployed: ## Read-only probe of the live Worker
	sh $(WORKER_DIR)/scripts/smoke-deployed.sh

migrate: ## Apply pending D1 migrations (LOCAL=1 for the simulation)
	@[ -n "$(DATABASE_ID)" ] || { >&2 printf 'migrate: wrangler.toml has no D1 database id\n'; exit 1; }
	@cd $(WORKER_DIR) && $(CF) d1 migrations list $(DATABASE_ID) $(MIGRATE_FLAGS)
	@cd $(WORKER_DIR) && $(CF) d1 migrations apply $(DATABASE_ID) $(MIGRATE_FLAGS)

provision: ## Create the R2 bucket and D1 database
	sh $(WORKER_DIR)/scripts/provision.sh

provision-access: ## Create the Worker-level Access app and a collector token
	sh $(WORKER_DIR)/scripts/provision.sh --access

observe: ## Assert the observability config and name the serving deployment
	@command -v rg >/dev/null || { >&2 printf 'observe: rg is not installed\n'; exit 1; }
	@rg -q --fixed-strings 'headSamplingRate: 0.25' $(WORKER_DIR)/cloudflare.config.ts || { >&2 printf 'observe: logs are not at 0.25\n'; exit 1; }
	@rg -q --fixed-strings 'headSamplingRate: 0.1' $(WORKER_DIR)/cloudflare.config.ts || { >&2 printf 'observe: traces are not at 0.10\n'; exit 1; }
	@printf '%s\n' 'dashboard: https://dash.cloudflare.com/?to=/:account/workers/services/view/usr-memories' 'logs: https://dash.cloudflare.com/?to=/:account/workers/services/view/usr-memories/production/observability'
	@cd $(WORKER_DIR) && $(CF) workers deployments list --worker usr-memories

perf-local: ## Collector benchmarks, no network
	@$(ENV_GIT) TMPDIR="$(CURDIR)/.work/tmp" REPEATS="$(REPEATS)" RECORDS="$(RECORDS)" OBJECTS="$(OBJECTS)" SCENARIO="$(SCENARIO)" OUT="$(OUT)" sh "$(PERF)" local

perf-worker: worker-bundle ## Benchmark the Miniflare bundle over HTTP
	@$(ENV_GIT) TMPDIR="$(CURDIR)/.work/tmp" REPEATS="$(REPEATS)" RECORDS="$(RECORDS)" OBJECTS="$(OBJECTS)" SCENARIO="$(SCENARIO)" OUT="$(OUT)" sh "$(PERF)" worker

perf-deployed: ## Benchmark the production origin with synthetic data
	@$(ENV_GIT) TMPDIR="$(CURDIR)/.work/tmp" REPEATS="$(REPEATS)" RECORDS="$(RECORDS)" OBJECTS="$(OBJECTS)" SCENARIO="$(SCENARIO)" OUT="$(OUT)" sh "$(PERF)" deployed

perf-report: ## Compare benchmark runs under OUT
	@TMPDIR="$(CURDIR)/.work/tmp" $(PYTHON) tools/agent-memory/eval/bench_mirror.py report --dir "$(OUT)"

test: worker-test ## Run the eleven agent-memory suites and the Worker runtime
	@set -e; for suite in $(SUITES); do \
		printf '== %s\n' "$$suite"; \
		$(ENV_GIT) TMPDIR="$(CURDIR)/.work/tmp" $(PYTHON) tools/agent-memory/tests/"$$suite".py; \
	done

test-all: test ## Run every local gate
	cd $(WORKER_DIR) && npm test
	uvx ruff check $(CAMPAIGN_PYTHON)
	uvx ty check $(CAMPAIGN_PYTHON)
	python3 -I tools/mdtool/src/mdtool.py check docs/CAMPAIGN-AGENT-MEMORIES-CLOUDFLARE.md docs/development.md tools/agent-memory/README.md

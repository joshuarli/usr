SHELL := /bin/sh
.DEFAULT_GOAL := help

REPEATS ?= 5
SCENARIO ?=
RECORDS ?= 1000
OUT ?= .work/perf
PYTHON := uv run --no-project --python '>=3.15' python -I
PERF := tools/agent-memory/cloudflare/perf.sh
SUITES := test_sessions test_archive test_transfer test_identity test_recovery test_learning_ops test_learning_review test_recall test_learning test_learning_promote
GIT_TEMPLATE_DIR ?= $(wildcard /opt/homebrew/share/git-core/templates)
ENV_GIT := $(if $(GIT_TEMPLATE_DIR),GIT_TEMPLATE_DIR=$(GIT_TEMPLATE_DIR))

.PHONY: help perf-local perf-worker perf-deployed perf-report test

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z][a-z0-9-]*:.*## / {printf "%-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

perf-local: ## Collector benchmarks, no network
	@$(ENV_GIT) TMPDIR="$(CURDIR)/.work/tmp" REPEATS="$(REPEATS)" RECORDS="$(RECORDS)" SCENARIO="$(SCENARIO)" OUT="$(OUT)" sh "$(PERF)" local

perf-worker: ## Benchmark the Miniflare bundle over HTTP
	@$(ENV_GIT) TMPDIR="$(CURDIR)/.work/tmp" REPEATS="$(REPEATS)" RECORDS="$(RECORDS)" SCENARIO="$(SCENARIO)" OUT="$(OUT)" sh "$(PERF)" worker

perf-deployed: ## Benchmark the production origin with synthetic data
	@$(ENV_GIT) TMPDIR="$(CURDIR)/.work/tmp" REPEATS="$(REPEATS)" RECORDS="$(RECORDS)" SCENARIO="$(SCENARIO)" OUT="$(OUT)" sh "$(PERF)" deployed

perf-report: ## Compare benchmark runs under OUT
	@TMPDIR="$(CURDIR)/.work/tmp" $(PYTHON) tools/agent-memory/eval/bench_mirror.py report --dir "$(OUT)"

test: ## Run the ten agent-memory suites
	@set -e; for suite in $(SUITES); do \
		printf '== %s\n' "$$suite"; \
		$(ENV_GIT) TMPDIR="$(CURDIR)/.work/tmp" $(PYTHON) tools/agent-memory/tests/"$$suite".py; \
	done

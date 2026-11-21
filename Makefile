SHELL := /bin/sh
.DEFAULT_GOAL := help

CF ?= cf
NODE ?= node

.PHONY: help deploy-setup.sh generate check-generated policy subagent-visualization skills-check skills-generate test lint bench

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z][a-z0-9.-]*:.*## / {printf "%-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

deploy-setup.sh: ## Deploy the Alpine bootstrap Worker
	CF_BIN="$(CF)" sh host/setup-deploy

generate: ## Refresh checked-in model policy projections
	@$(NODE) tools/policy/generate.ts

check-generated: ## Check policy projections without changing files
	@$(NODE) tools/policy/generate.ts --check
	@$(NODE) tools/policy/subagent-visualization.ts --check

policy: ## Export approved model policy as JSON without provider probes
	@$(NODE) tools/policy/generate.ts --json

subagent-visualization: ## Render docs/subagents.html from the typed policy
	@$(NODE) tools/policy/subagent-visualization.ts

skills-check: ## Check skill metadata and generated adapters
	@$(NODE) tools/skills/skills.ts check
	@$(NODE) tools/skills/skills.ts check --root .agents/skills

skills-generate: ## Refresh skill invocation adapters
	@$(NODE) tools/skills/skills.ts generate

test: ## Run the repository and policy test suites
	@sh sync check
	@python3 -I tools/pi/test_release_install.py
	@python3 -I tools/pi/test_sync_bridge_offline.py
	@python3 -I tools/sync/opencode-worker-test.py
	@sh -n dotfiles/base/.local/bin/pk
	@python3 -I dotfiles/pk-test.py
	@$(NODE) --test tools/policy/generate.test.ts
	@$(NODE) --test tools/policy/subagent-visualization.test.ts
	@$(NODE) --experimental-strip-types --test tools/pi-subagent-bridge/test/devin-provider.test.ts
	@python3 -I tools/pi/test_runtime_profiles.py
	@python3 -I tools/pi/test_offline.py

lint: ## Run repository lint checks
	@./lint

bench: ## Time representative sync, pinact, mdtool and todo journeys (BENCH_ARGS=--rounds N)
	@mkdir -p .work/tmp
	@TMPDIR="$$PWD/.work/tmp" python3 -I tools/bench/bench.py $(BENCH_ARGS)

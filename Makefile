SHELL := /bin/sh
.DEFAULT_GOAL := help

CF ?= cf
NODE ?= node

.PHONY: help deploy-setup.sh generate check-generated policy skills-check skills-generate

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z][a-z0-9.-]*:.*## / {printf "%-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

deploy-setup.sh: ## Deploy the Alpine bootstrap Worker
	CF_BIN="$(CF)" sh host/setup-deploy

generate: ## Refresh checked-in model policy projections
	@$(NODE) tools/policy/generate.ts

check-generated: ## Check policy projections without changing files
	@$(NODE) tools/policy/generate.ts --check

policy: ## Export approved model policy as JSON without provider probes
	@$(NODE) tools/policy/generate.ts --json

skills-check: ## Check skill metadata and generated adapters
	@$(NODE) tools/skills/skills.ts check
	@$(NODE) tools/skills/skills.ts check --root .agents/skills

skills-generate: ## Refresh skill invocation adapters
	@$(NODE) tools/skills/skills.ts generate

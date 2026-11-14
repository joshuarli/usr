SHELL := /bin/sh
.DEFAULT_GOAL := help

CF ?= cf
NODE ?= node

.PHONY: help deploy-setup.sh generate check-generated policy

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

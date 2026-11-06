SHELL := /bin/sh
.DEFAULT_GOAL := help

CF ?= cf

.PHONY: help deploy-setup.sh

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z][a-z0-9.-]*:.*## / {printf "%-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

deploy-setup.sh: ## Deploy the Alpine bootstrap Worker
	CF_BIN="$(CF)" sh host/setup-deploy

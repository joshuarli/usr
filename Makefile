TARGET ?= $(HOME)
KACHE  := $(or $(CARGO_HOME),$(HOME)/.cargo)/bin/kache
DL_OWNED_FILE := $(or $(XDG_STATE_HOME),$(HOME)/.local/state)/make/dl-owned
DL_TMPDIR := $(CURDIR)/.work/tmp
OS     := $(shell uname -s | tr '[:upper:]' '[:lower:]')
LAYERS := $(wildcard dotfiles/base dotfiles/$(OS))
SYM    := sh dotfiles/sym

.PHONY: sync links tools uninstall plan layers check lint

links: layers
	mkdir -p "$(DL_TMPDIR)" || exit 1; \
	mkdir -p "$(dir $(DL_OWNED_FILE))" || exit 1; \
	sh dotfiles/migrate-pinact.sh "$(TARGET)" "$(DL_OWNED_FILE)" || exit 1; \
	for layer in $(LAYERS); do TMPDIR="$(DL_TMPDIR)" SYM_OWNED_FILE="$(DL_OWNED_FILE)" $(SYM) -v -t "$(TARGET)" "$$layer" || exit 1; done

tools:
	mkdir -p "$(DL_TMPDIR)" "$(dir $(DL_OWNED_FILE))" || exit 1; \
	TMPDIR="$(DL_TMPDIR)" DL_OWNED_FILE="$(DL_OWNED_FILE)" sh dl $(TOOLS)

sync: links
	status=0; \
	TMPDIR="$(DL_TMPDIR)" DL_OWNED_FILE="$(DL_OWNED_FILE)" sh dl || { status=$$?; printf 'sync: dl step failed\n' >&2; }; \
	brew_status=0; \
	if [ "$(OS)" = darwin ]; then TMPDIR="$(DL_TMPDIR)" sh macos/setup-macos brew packages || { brew_status=$$?; [ $$status -ne 0 ] || status=$$brew_status; }; fi; \
	if [ "$(OS)" = linux ] && [ -r /etc/os-release ]; then \
		. /etc/os-release; \
		if [ "$${ID:-}" = alpine ]; then TMPDIR="$(DL_TMPDIR)" sh setup-linux || status=$$?; fi; \
	fi; \
	if [ ! -x "$(KACHE)" ]; then \
		if [ "$(OS)" != darwin ] || [ $$brew_status -eq 0 ]; then \
			if [ "$(OS)" = darwin ]; then PATH="/opt/homebrew/bin:/usr/local/bin:$$PATH" TMPDIR="$(DL_TMPDIR)" sh dotfiles/base/.local/bin/setup-kache </dev/null || status=$$?; else \
			TMPDIR="$(DL_TMPDIR)" sh dotfiles/base/.local/bin/setup-kache </dev/null || status=$$?; fi; \
			if [ -x "$(KACHE)" ] && { [ ! -f "$(DL_OWNED_FILE)" ] || ! awk -F '\t' -v path="$(KACHE)" '$$1 == "K" && $$2 == path { found = 1 } END { exit !found }' "$(DL_OWNED_FILE)"; }; then printf 'K\t%s\n' "$(KACHE)" >> "$(DL_OWNED_FILE)" || status=$$?; fi; \
		fi; \
	fi; \
	exit $$status

uninstall:
	mkdir -p "$(DL_TMPDIR)" || exit 1
	mkdir -p "$(dir $(DL_OWNED_FILE))" || exit 1
	TMPDIR="$(DL_TMPDIR)" DL_OWNED_FILE="$(DL_OWNED_FILE)" DL_RECORD_OWNED=true sh dl || exit 1
	if [ -f "$(DL_OWNED_FILE)" ]; then \
		while IFS="$$(printf '\t')" read -r kind path; do \
			[ "$$kind" = F ] || continue; \
			if [ "$(OS)" = darwin ] && [ "$$path" = "$(HOME)/Library/LaunchAgents/com.mactop.plist" ]; then launchctl bootout "gui/$$(id -u)" "$$path" 2>/dev/null || :; fi; \
		rm -f "$$path" || exit 1; \
		done < "$(DL_OWNED_FILE)"; \
		while IFS="$$(printf '\t')" read -r kind path; do \
			[ "$$kind" = D ] || continue; \
			rm -rf "$$path" || exit 1; \
		done < "$(DL_OWNED_FILE)"; \
		while :; do \
			removed=false; \
			while IFS="$$(printf '\t')" read -r kind path; do \
				[ "$$kind" = E ] || continue; \
				if rmdir "$$path" 2>/dev/null; then removed=true; fi; \
			done < "$(DL_OWNED_FILE)"; \
			[ "$$removed" = true ] || break; \
		done; \
		while IFS="$$(printf '\t')" read -r kind path; do \
			[ "$$kind" = K ] || continue; \
			TMPDIR="$(DL_TMPDIR)" sh dotfiles/base/.local/bin/setup-kache uninstall --purge || exit 1; \
		done < "$(DL_OWNED_FILE)"; \
		rm -f "$(DL_OWNED_FILE)"; \
		rmdir "$$(dirname "$(DL_OWNED_FILE)")" 2>/dev/null || :; \
	fi

plan: layers
	mkdir -p "$(DL_TMPDIR)" || exit 1; \
	planned="$(DL_TMPDIR)/plan-prunes.$$$$"; : > "$$planned" || exit 1; \
	trap 'rm -f "$$planned"' 0; \
	status=0; \
	for layer in $(LAYERS); do \
		output=$$(SYM_OWNED_FILE="$(DL_OWNED_FILE)" SYM_PLANNED_PRUNES="$$planned" $(SYM) --dry-run -t "$(TARGET)" "$$layer" 2>&1) || status=$$?; \
		printf '%s\n' "$$output"; \
		case "$$output" in *CONFLICT:*) status=1 ;; esac; \
	done; \
	exit $$status

layers:
	@dup=$$(for layer in $(LAYERS); do git ls-files -- $$layer | sed "s|^$$layer/||"; done | sort | uniq -d); \
	[ -z "$$dup" ] || { printf 'in more than one layer:\n%s\n' "$$dup" >&2; exit 1; }

check:
	python3 -I macos/make-sync-test.py
	mkdir -p "$(DL_TMPDIR)"
	TMPDIR="$(DL_TMPDIR)" python3 -I tools/pinact/test_pinact.py
	TMPDIR="$(DL_TMPDIR)" python3 -I tools/pinact/tests/test_yaml.py
	TMPDIR="$(DL_TMPDIR)" python3 -I tools/pinact/tests/test_lint_rules.py
	TMPDIR="$(DL_TMPDIR)" python3 -I tools/pinact/tests/test_expressions.py
	TMPDIR="$(DL_TMPDIR)" python3 -I tools/pinact/tests/test_security.py
	TMPDIR="$(DL_TMPDIR)" python3 -I tools/pinact/tests/test_fix.py
	python3 -I dotfiles/base/.local/bin/pinact --check
	python3 -I dotfiles/pi-test.py
	TMPDIR="$(DL_TMPDIR)" python3 -I dotfiles/sbx-test.py
	cd dotfiles && sh sym-test.sh && { ! command -v dash >/dev/null || dash sym-test.sh; }
	cd dotfiles && sh agent-tier-gate-test.sh
	sh dotfiles/reset-agents-test.sh
	cd dotfiles && sh pre-push-test.sh
	cd dotfiles && sh worktree-remove-test.sh
	sh tools/mdtool/tests/mdtool-test.sh
	python3 -I tools/decide/tests/test_decide.py
	python3 -I dotfiles/base/.local/bin/skill-usage selftest
	uv run --no-project --python ">=3.15" python -I tools/agent-memory/tests/test_sessions.py
	uv run --no-project --python ">=3.15" python -I tools/agent-memory/tests/test_recall.py
	uv run --no-project --python ">=3.15" python -I tools/agent-memory/tests/test_learning.py
	uv run --no-project --python ">=3.15" python -I tools/agent-memory/tests/test_learning_review.py
	uv run --no-project --python ">=3.15" python -I tools/agent-memory/tests/test_learning_promote.py
	uv run --no-project --python ">=3.15" python -I tools/agent-memory/tests/test_learning_ops.py
	uv run --no-project --python ">=3.15" python -I tools/agent-memory/eval/test_live_learning.py
	uv run --no-project --python ">=3.15" python -I tools/agent-memory/eval/test_live_recall.py
	sh dotfiles/skills-check.sh dotfiles/base/.agents/skills
	sh dotfiles/skills-check.sh .agents/skills
	python3 -I dotfiles/skills-campaign-test.py

check-parallel:
	mkdir -p "$(DL_TMPDIR)"
	TMPDIR="$(DL_TMPDIR)" uvx --python 3.15 --with 'joshuarli-pytest-parallel==0.4.0' pytest tools dotfiles macos

lint:
	@files=$$(git ls-files -co --exclude-standard | while read -r f; do \
		[ -f "$$f" ] && [ ! -L "$$f" ] || continue; \
		{ [ "$${f%.sh}" != "$$f" ] || head -n 1 "$$f" | grep -Eq '^#!.*(sh|bash|dash)( |$$)'; } && echo "$$f"; \
	done); \
	shellcheck -S warning -e SC3013 -s sh $$files
	@files=$$(git ls-files -co --exclude-standard | while read -r f; do \
		[ -f "$$f" ] && [ ! -L "$$f" ] || continue; \
		{ [ "$${f%.py}" != "$$f" ] || head -n 1 "$$f" | grep -Eq '^#!.*python'; } && echo "$$f"; \
	done); \
	uvx ruff check --no-cache $$files

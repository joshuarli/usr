# ~/usr is the source of truth. `make` makes the home directory match it: each tracked
# file in a layer is symlinked into $(TARGET), and a directory holding a .sym-dir marker
# is linked whole. Files that exist only in the home directory are left alone.
#
# A layer is a directory under dotfiles/. base applies everywhere; darwin or linux applies
# on that OS. A path belongs to one layer, so a second claim on it is a conflict.
#
# `make` first runs dl, which installs the binaries the scripts and hooks call and is a
# no-op when they are current. A dl failure does not stop the sync, but it fails the make.
# After the sync, `make` installs the macOS Brewfile packages when kache is missing, then
# runs setup-kache with no terminal so it skips the interactive config.

TARGET ?= $(HOME)
KACHE  := $(or $(CARGO_HOME),$(HOME)/.cargo)/bin/kache
DL_OWNED_FILE := $(or $(XDG_STATE_HOME),$(HOME)/.local/state)/make/dl-owned
DL_TMPDIR := $(CURDIR)/.work/tmp
OS     := $(shell uname -s | tr '[:upper:]' '[:lower:]')
LAYERS := $(wildcard dotfiles/base dotfiles/$(OS))
SYM    := sh dotfiles/sym

.PHONY: sync uninstall plan layers check lint

sync: layers
	mkdir -p "$(DL_TMPDIR)" || exit 1; \
	mkdir -p "$(dir $(DL_OWNED_FILE))" || exit 1; \
	status=0; TMPDIR="$(DL_TMPDIR)" DL_OWNED_FILE="$(DL_OWNED_FILE)" sh dl || status=$$?; \
	for layer in $(LAYERS); do TMPDIR="$(DL_TMPDIR)" SYM_OWNED_FILE="$(DL_OWNED_FILE)" $(SYM) -v -t "$(TARGET)" "$$layer" || exit 1; done; \
	if [ ! -x "$(KACHE)" ]; then \
		if [ "$(OS)" = darwin ]; then \
			brew_status=0; sh macos/setup-macos brew packages || brew_status=$$?; \
			if [ $$brew_status -eq 0 ]; then PATH="/opt/homebrew/bin:/usr/local/bin:$$PATH" TMPDIR="$(DL_TMPDIR)" sh dotfiles/base/.local/bin/setup-kache </dev/null || status=$$?; else status=$$brew_status; fi; \
		else \
			TMPDIR="$(DL_TMPDIR)" sh dotfiles/base/.local/bin/setup-kache </dev/null || status=$$?; \
		fi; \
		if [ -x "$(KACHE)" ] && { [ ! -f "$(DL_OWNED_FILE)" ] || ! awk -F '\t' -v path="$(KACHE)" '$$1 == "K" && $$2 == path { found = 1 } END { exit !found }' "$(DL_OWNED_FILE)"; }; then printf 'K\t%s\n' "$(KACHE)" >> "$(DL_OWNED_FILE)" || status=$$?; fi; \
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

# sym reports dry-run conflicts without failing, so check every layer and propagate them.
plan: layers
	status=0; \
	for layer in $(LAYERS); do \
		output=$$($(SYM) --dry-run -t "$(TARGET)" "$$layer" 2>&1) || status=$$?; \
		printf '%s\n' "$$output"; \
		case "$$output" in *CONFLICT:*) status=1 ;; esac; \
	done; \
	exit $$status

# Each layer is checked alone, so a path claimed by two layers would otherwise surface
# only after the first layer was applied.
layers:
	@dup=$$(for layer in $(LAYERS); do git ls-files -- $$layer | sed "s|^$$layer/||"; done | sort | uniq -d); \
	[ -z "$$dup" ] || { printf 'in more than one layer:\n%s\n' "$$dup" >&2; exit 1; }

check:
	cd dotfiles && sh sym-test.sh && { ! command -v dash >/dev/null || dash sym-test.sh; }
	cd dotfiles && sh agent-tier-gate-test.sh
	sh dotfiles/reset-agents-test.sh
	cd dotfiles && sh pre-push-test.sh
	cd dotfiles && sh worktree-remove-test.sh
	sh dotfiles/mdtool-test.sh
	python3 -I dotfiles/base/.local/bin/skill-usage selftest
	sh dotfiles/skills-check.sh dotfiles/base/.agents/skills
	sh dotfiles/skills-check.sh .agents/skills
	python3 -I dotfiles/skills-campaign-test.py

# Every shell script must be POSIX sh, so lint every tracked or new file that ends in .sh or
# starts with a sh, bash, or dash shebang, as sh regardless of what its shebang claims. Every
# Python script, by .py or a python shebang, goes through ruff with the rules in ruff.toml.
lint:
	@files=$$(git ls-files -co --exclude-standard | while read -r f; do \
		[ -f "$$f" ] && [ ! -L "$$f" ] || continue; \
		{ [ "$${f%.sh}" != "$$f" ] || head -n 1 "$$f" | grep -Eq '^#!.*(sh|bash|dash)( |$$)'; } && echo "$$f"; \
	done); \
	shellcheck -s sh $$files
	@files=$$(git ls-files -co --exclude-standard | while read -r f; do \
		[ -f "$$f" ] && [ ! -L "$$f" ] || continue; \
		{ [ "$${f%.py}" != "$$f" ] || head -n 1 "$$f" | grep -Eq '^#!.*python'; } && echo "$$f"; \
	done); \
	uvx ruff check --no-cache $$files

# ~/usr is the source of truth. `make` makes the home directory match it: each tracked
# file in a layer is symlinked into $(TARGET), and a directory holding a .sym-dir marker
# is linked whole. Files that exist only in the home directory are left alone.
#
# A layer is a directory under dotfiles/. base applies everywhere; darwin or linux applies
# on that OS. A path belongs to one layer, so a second claim on it is a conflict.
#
# `make` first runs dl, which installs the binaries the scripts and hooks call and is a
# no-op when they are current. A dl failure does not stop the sync, but it fails the make.

TARGET ?= $(HOME)
OS     := $(shell uname -s | tr '[:upper:]' '[:lower:]')
LAYERS := $(wildcard dotfiles/base dotfiles/$(OS))
SYM    := sh dotfiles/sym

.PHONY: sync plan layers check lint

sync: layers
	status=0; sh dl || status=$$?; \
	for layer in $(LAYERS); do $(SYM) -v -t "$(TARGET)" "$$layer" || exit 1; done; \
	exit $$status

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

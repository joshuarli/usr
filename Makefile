# ~/usr is the source of truth. `make` makes the home directory match it:
# files are symlinked, and the synced directories (.agents/skills, .claude/agents)
# are overwritten from here. Files that exist only in the home directory are left
# alone and reported as EXTRA.

TARGET ?= $(HOME)
SOURCE := dotfiles/base
SYM    := sh dotfiles/sym

.PHONY: sync plan check

sync:
	$(SYM) --force -v -t $(TARGET) $(SOURCE)

plan:
	$(SYM) --force --dry-run -t $(TARGET) $(SOURCE)

check:
	cd dotfiles && sh sym-test.sh
	sh dotfiles/skills-check.sh $(SOURCE)/.agents/skills
	sh dotfiles/skills-check.sh .agents/skills

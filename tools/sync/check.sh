#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
	python3 -I host/macos/sync-test.py
	python3 -I tools/sync/claude-worker-test.py
	python3 -I tools/sync/test_dag.py
	python3 -I tools/sync/test_main.py
	python3 -I tools/sync/test_uninstall.py
	python3 -I tools/sync/test_integration.py
	sh dotfiles/doctor-test.sh
	node dotfiles/pi-git-guard-test.mjs
	mkdir -p "$tmpdir"
	TMPDIR="$tmpdir" python3 -I tools/pinact/test_pinact.py
	TMPDIR="$tmpdir" python3 -I tools/pinact/tests/test_yaml.py
	TMPDIR="$tmpdir" python3 -I tools/pinact/tests/test_lint_rules.py
	TMPDIR="$tmpdir" python3 -I tools/pinact/tests/test_expressions.py
	TMPDIR="$tmpdir" python3 -I tools/pinact/tests/test_security.py
	TMPDIR="$tmpdir" python3 -I tools/pinact/tests/test_fix.py
	python3 -I dotfiles/base/.local/bin/pinact --check
	python3 -I dotfiles/pi-test.py
	python3 -I dotfiles/ghostty-shader-test.py
	TMPDIR="$tmpdir" python3 -I dotfiles/sbx-test.py
	(cd dotfiles && sh sym-test.sh && { ! command -v dash >/dev/null || dash sym-test.sh; })
	(cd dotfiles && sh agent-tier-gate-test.sh)
	sh dotfiles/reset-agents-test.sh
	(cd dotfiles && sh pre-push-test.sh)
	(cd dotfiles && sh worktree-remove-test.sh)
	(cd dotfiles && sh zsh-shim-test.sh)
	sh tools/mdtool/tests/mdtool-test.sh
	python3 -I tools/decide/tests/test_decide.py
	(cd dotfiles && sh agent-memory-launchers-test.sh)
	sh dotfiles/base/.local/bin/skill-usage selftest
	sh dotfiles/skills-check.sh dotfiles/base/.agents/skills
	sh dotfiles/skills-check.sh .agents/skills
	python3 -I dotfiles/skills-campaign-test.py

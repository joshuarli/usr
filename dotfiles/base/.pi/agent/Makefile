EXTENSIONS_DIR := $(HOME)/.pi/agent/extensions

TEST_DIRS := $(wildcard $(EXTENSIONS_DIR)/*/vitest.config.ts)
TEST_DIRS := $(patsubst %/vitest.config.ts,%,$(TEST_DIRS))

.PHONY: test
test:
	@fail=0; \
	for dir in $(TEST_DIRS); do \
		echo "=== $$dir ==="; \
		cd "$$dir" && npx vitest --run || fail=1; \
	done; \
	exit $$fail

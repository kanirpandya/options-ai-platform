# Makefile
# Purpose: Developer and CI orchestration for coveredcall-agents
# Uses pytest + pytest-xdist for fast, parallel test execution

.PHONY: help test test-fast test-cli test-core test-all

# Default parallelism
PYTEST_N ?= 3
PYTEST_OPTS = -n $(PYTEST_N) -vv --maxfail=1 -s

help:
	@echo ""
	@echo "Available targets:"
	@echo "  make test        → full test suite (parallel)"
	@echo "  make test-fast   → core unit tests (no CLI)"
	@echo "  make test-cli    → CLI smoke + regression"
	@echo "  make test-core   → divergence + resolver logic"
	@echo ""

# Full suite (what you just ran successfully)
test:
	pytest $(PYTEST_OPTS)

# Faster inner-loop tests (logic only)
test-fast:
	pytest $(PYTEST_OPTS) \
		tests/test_mode_normalization.py \
		tests/test_divergence.py \
		tests/test_final_resolver.py \
		tests/test_fundamentals_resolver_node.py

# CLI-only (slow, but end-to-end)
test-cli:
	pytest $(PYTEST_OPTS) \
		tests/test_cli_smoke.py \
		tests/test_cli_regression.py

# Core fundamentals logic (no subprocess / CLI)
test-core:
	pytest $(PYTEST_OPTS) \
		tests/test_divergence.py \
		tests/test_final_resolver.py

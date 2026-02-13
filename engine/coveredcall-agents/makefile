# Makefile
# Purpose: Developer and CI orchestration for coveredcall-agents
# Default behavior is INTERACTIVE (live output, verbose)
# Uses pytest + pytest-xdist for parallel execution

.PHONY: help test test-fast test-cli test-core test-all \
        test-modes test-deterministic test-llm test-llm-debate test-agentic test-llm-agentic \
        test-modes-trace test-deterministic-trace test-llm-trace test-llm-debate-trace test-agentic-trace test-llm-agentic-trace

# -----------------------------
# Configuration
# -----------------------------

# Default parallelism (override: make test PYTEST_N=4)
PYTEST_N ?= 3

# Interactive / developer-friendly pytest options
# -vv : verbose
# -s  : do not capture stdout/stderr (show live output)
# --maxfail=1 : fail fast
PYTEST_OPTS = -n $(PYTEST_N) -vv --maxfail=1 -s

# CLI smoke defaults
PY ?= python
CLI ?= -m cli.main
TICKER ?= AAPL

LLM_PROVIDER ?= ollama
LLM_MODEL ?= llama3.2:3b
LLM_TIMEOUT_S ?= 180

# -----------------------------
# JSON validation helpers
# -----------------------------

# Strict: stdout must be pure JSON
JSON_STRICT_OK = | $(PY) -c "import sys,json; json.load(sys.stdin); print('OK')"

# Lenient: stdout may be noisy; validate it contains at least one JSON object (trace mode)
JSON_LENIENT_OK = | $(PY) scripts/validate_first_json.py

# -----------------------------
# Help
# -----------------------------
help:
	@echo ""
	@echo "Available targets:"
	@echo "  make test                → full test suite (interactive, parallel)"
	@echo "  make test-fast           → fast inner-loop tests (no CLI)"
	@echo "  make test-core           → fundamentals + divergence logic"
	@echo "  make test-cli            → CLI smoke + regression (slow)"
	@echo "  make test-modes          → smoke-test all fundamentals modes"
	@echo "  make test-modes-trace    → smoke-test all modes with --trace"
	@echo ""

# -----------------------------
# Test targets
# -----------------------------

test:
	pytest $(PYTEST_OPTS)

test-fast:
	pytest $(PYTEST_OPTS) \
		tests/test_mode_normalization.py \
		tests/test_divergence.py \
		tests/test_final_resolver.py \
		tests/test_fundamentals_resolver_node.py

test-core:
	pytest $(PYTEST_OPTS) \
		tests/test_divergence.py \
		tests/test_final_resolver.py

test-cli:
	pytest $(PYTEST_OPTS) \
		tests/test_cli_smoke.py \
		tests/test_cli_regression.py

# -----------------------------
# Fundamentals mode smoke tests
# -----------------------------

test-modes: test-deterministic test-llm test-llm-debate test-agentic test-llm-agentic
	@echo "All fundamentals mode smoke tests passed ✅"

test-deterministic:
	@echo "=== deterministic ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode deterministic \
		--output json $(JSON_STRICT_OK)

test-llm:
	@echo "=== llm ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode llm \
		--llm-provider $(LLM_PROVIDER) \
		--llm-model $(LLM_MODEL) \
		--llm-timeout-s $(LLM_TIMEOUT_S) \
		--output json $(JSON_STRICT_OK)

test-llm-debate:
	@echo "=== llm + force-debate ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode llm \
		--force-debate \
		--llm-provider $(LLM_PROVIDER) \
		--llm-model $(LLM_MODEL) \
		--llm-timeout-s $(LLM_TIMEOUT_S) \
		--output json $(JSON_STRICT_OK)

test-agentic:
	@echo "=== agentic ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode agentic \
		--llm-provider $(LLM_PROVIDER) \
		--llm-model $(LLM_MODEL) \
		--llm-timeout-s $(LLM_TIMEOUT_S) \
		--output json $(JSON_STRICT_OK)

test-llm-agentic:
	@echo "=== llm_agentic ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode llm_agentic \
		--llm-provider $(LLM_PROVIDER) \
		--llm-model $(LLM_MODEL) \
		--llm-timeout-s $(LLM_TIMEOUT_S) \
		--output json $(JSON_STRICT_OK)

# -----------------------------
# Fundamentals mode smoke tests (trace)
# -----------------------------

test-modes-trace: test-deterministic-trace test-llm-trace test-llm-debate-trace test-agentic-trace test-llm-agentic-trace
	@echo "All fundamentals mode TRACE smoke tests passed ✅"

test-deterministic-trace:
	@echo "=== deterministic --trace ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode deterministic \
		--trace \
		--output json $(JSON_LENIENT_OK)

test-llm-trace:
	@echo "=== llm --trace ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode llm \
		--trace \
		--llm-provider $(LLM_PROVIDER) \
		--llm-model $(LLM_MODEL) \
		--llm-timeout-s $(LLM_TIMEOUT_S) \
		--output json $(JSON_LENIENT_OK)

test-llm-debate-trace:
	@echo "=== llm --trace + force-debate ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode llm \
		--trace \
		--force-debate \
		--llm-provider $(LLM_PROVIDER) \
		--llm-model $(LLM_MODEL) \
		--llm-timeout-s $(LLM_TIMEOUT_S) \
		--output json $(JSON_LENIENT_OK)

test-agentic-trace:
	@echo "=== agentic --trace ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode agentic \
		--trace \
		--llm-provider $(LLM_PROVIDER) \
		--llm-model $(LLM_MODEL) \
		--llm-timeout-s $(LLM_TIMEOUT_S) \
		--output json $(JSON_LENIENT_OK)

test-llm-agentic-trace:
	@echo "=== llm_agentic --trace ($(TICKER)) ==="
	$(PY) $(CLI) --ticker $(TICKER) \
		--fundamentals-mode llm_agentic \
		--trace \
		--llm-provider $(LLM_PROVIDER) \
		--llm-model $(LLM_MODEL) \
		--llm-timeout-s $(LLM_TIMEOUT_S) \
		--output json $(JSON_LENIENT_OK)

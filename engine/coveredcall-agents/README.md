# coveredcall-agents

Graph-first, tool-driven covered call trading agents inspired by TradingAgents-style architectures.

This project builds a **contract-safe CLI and agentic framework** for analyzing covered call strategies using:
- deterministic fundamentals
- LLM-assisted reasoning
- debate + divergence analysis
- optional fully agentic tool use

The system is designed to be **machine-consumable**, **traceable**, and **safe to integrate into pipelines, APIs, and UIs**.

---

## Key principles

- **Graph-first architecture**  
  All workflows are explicit LangGraph graphs (not ad-hoc chains).

- **Strict stdout contract**  
  `--output json` always produces **pure JSON** (no banners, no debug noise).

- **Traceable, not noisy**  
  Debugging and LLM diagnostics are gated behind `--trace` and routed to stderr.

- **Deterministic by default**  
  Regression tests and smoke checks do not depend on LLM availability.

- **Agentic, but controlled**  
  LLM tool use and debate are explicit, inspectable, and optional.

---

## What this tool does

Given a ticker (e.g. `AAPL`), the system can:

- Fetch and validate market + fundamentals data
- Compute a **deterministic fundamentals stance**
- Optionally compute an **LLM fundamentals stance**
- Measure divergence between deterministic and LLM views
- Run **bull/bear debate agents**
- Produce a final fundamentals report with:
  - stance
  - covered-call bias
  - confidence
  - appendix (debate / divergence summary)

This project focuses on **analysis and decision support**, not order execution.

---

## Installation

```bash
git clone https://github.com/kanirpandya/coveredcall-agents.git
cd coveredcall-agents
Create and activate a Python environment (venv / conda / poetry as preferred), then install dependencies.

Basic usage
Deterministic fundamentals (recommended default)
bash
Copy code
python -m cli.main \
  --ticker AAPL \
  --fundamentals-mode deterministic \
  --output json
✔ Pure JSON on stdout
✔ No LLM dependency
✔ Safe for scripts and CI

LLM-assisted fundamentals
bash
Copy code
python -m cli.main \
  --ticker AAPL \
  --fundamentals-mode llm \
  --llm-provider ollama \
  --llm-model llama3.2:3b \
  --output json
Force debate + divergence analysis
bash
Copy code
python -m cli.main \
  --ticker AAPL \
  --fundamentals-mode llm \
  --force-debate \
  --llm-provider ollama \
  --llm-model llama3.2:3b \
  --output json
The output will include an appendix with:

divergence report

bull/bear debate synthesis

Debugging and tracing
Enable trace output
bash
Copy code
python -m cli.main \
  --ticker AAPL \
  --fundamentals-mode deterministic \
  --trace \
  --output json
Behavior:

stdout: clean, machine-readable JSON

stderr: debug logs, routing decisions, LLM diagnostics

This allows full introspection without breaking pipes.

Testing and regression checks
Deterministic smoke tests (recommended)
bash
Copy code
./scripts/smoke.sh
pytest -q
These checks verify:

JSON stdout purity

stdout / stderr separation

trace behavior

BrokenPipe safety

They do not depend on LLMs and are safe for CI.

Optional LLM integration checks
bash
Copy code
SMOKE_LLM=1 ./scripts/smoke.sh
SMOKE_LLM=1 pytest -q -k llm_optional
These validate:

LLM + debate paths

appendix generation

LLM checks are opt-in and may depend on model availability and latency.

Architecture overview
High-level flow:

FundamentalAgent

deterministic fundamentals

LLMNode / AgenticNode (optional)

LLM fundamentals or tool-driven reasoning

DivergenceNode

compares deterministic vs LLM stance

DebateAgents

bull and bear cases

ProposalNode

final fundamentals report + appendix

All state flows through a typed graph state, making behavior explicit and inspectable.

Output contract
When using:

bash
Copy code
--output json
The CLI guarantees:

exactly one JSON document on stdout

no debug, banners, or logs on stdout

all diagnostics routed to stderr (under --trace)

This contract is enforced by regression tests.

Release notes
v0.2-stable
Enforced strict stdout JSON contract

Routed all debug and LLM logs to stderr under --trace

Added deterministic smoke + pytest regression harness

Gated LLM integration tests behind SMOKE_LLM

Stabilized agentic + debate flows and appendix generation

What this project is (and isn’t)
This is:

a research-grade trading analysis framework

safe to embed in pipelines, APIs, and UIs

designed for extensibility and inspection

This is not:

an automated trading bot

investment advice

order-execution software

Roadmap (high-level)
Explicit policy table for deterministic vs LLM precedence

FastAPI backend for batch / CSV workflows

Web UI on top of the API

Golden-file behavioral regression tests

Additional strategy agents beyond covered calls

Disclaimer
This project is for educational and research purposes only.
It does not constitute financial advice.
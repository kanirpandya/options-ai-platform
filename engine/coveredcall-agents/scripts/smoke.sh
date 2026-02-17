#!/usr/bin/env bash
set -euo pipefail

PYTHON=${PYTHON:-python}
CLI="${CLI:-$PYTHON -m cli.main}"
TICKER=${TICKER:-AAPL}

# LLM integration knobs (optional)
SMOKE_LLM=${SMOKE_LLM:-0}
MODEL=${MODEL:-llama3.2:3b}
TIMEOUT=${TIMEOUT:-180}

echo "[smoke] ticker=$TICKER smoke_llm=$SMOKE_LLM"

BAD_RE='(\[DEBUG|\[LLMClient\]|Fundamentals provider:|Fundamentals mode:)'

echo "[smoke] 1) json parse (deterministic)"
$CLI --ticker "$TICKER" \
  --fundamentals-mode deterministic \
  --output json \
  2>/tmp/cca_smoke.err \
| $PYTHON -c "import sys,json; json.load(sys.stdin); print('OK: json parse (deterministic)')"

echo "[smoke] 1a) stdout clean (deterministic)"
$CLI --ticker "$TICKER" \
  --fundamentals-mode deterministic \
  --output json \
  2>/dev/null >/tmp/cca_smoke.out

$PYTHON - <<'PY'
import re, sys, pathlib
s = pathlib.Path("/tmp/cca_smoke.out").read_text(errors="replace")
bad = []
for pat in [r"\[DEBUG", r"\[LLMClient\]", r"Fundamentals provider:", r"Fundamentals mode:"]:
    if re.search(pat, s):
        bad.append(pat)
if bad:
    print("FAIL: stdout polluted with:", bad)
    sys.exit(2)
print("OK: stdout clean")
PY

echo "[smoke] 2) trace emits debug to stderr (deterministic)"
$CLI --ticker "$TICKER" \
  --fundamentals-mode deterministic \
  --trace \
  --output json \
  1>/tmp/cca_trace.out \
  2>/tmp/cca_trace.err

test -s /tmp/cca_trace.out || (echo "FAIL: trace stdout empty"; tail -n 120 /tmp/cca_trace.err; exit 5)
$PYTHON -c "import json; json.load(open('/tmp/cca_trace.out')); print('OK: json parse (trace)')"
grep -Eq "\[DEBUG|\[LLMClient\]" /tmp/cca_trace.err && echo "OK: trace emits debug to stderr" || (echo "FAIL: trace produced no debug stderr" && exit 3)

echo "[smoke] 3) BrokenPipe safety"
set +e
$CLI --ticker "$TICKER" --output json | head -n 1 >/dev/null
EC=$?
set -e
if [ "$EC" -ne 0 ]; then
  echo "FAIL: BrokenPipe exit code $EC"
  exit 4
fi
echo "OK: BrokenPipe safety"

if [ "$SMOKE_LLM" = "1" ]; then
  echo "[smoke] 4) LLM integration (optional): debate + appendix"
  set +e
  $CLI --ticker "$TICKER" \
    --fundamentals-mode llm \
    --force-debate \
    --llm-provider ollama \
    --llm-model "$MODEL" \
    --llm-timeout-s "$TIMEOUT" \
    --output json \
    1>/tmp/cca_llm.out \
    2>/tmp/cca_llm.err
  EC=$?
  set -e
  if [ "$EC" -ne 0 ]; then
    echo "WARN: LLM integration failed (non-fatal). stderr tail:"
    tail -n 80 /tmp/cca_llm.err
  else
    $PYTHON -c "import json; json.load(open('/tmp/cca_llm.out')); print('OK: LLM json parse')"
    $PYTHON - <<'PY'
import json
j=json.load(open("/tmp/cca_llm.out"))
a=(j.get("fundamentals_report") or {}).get("appendix")
assert a and len(a)>0, "appendix missing/empty"
print("OK: LLM appendix present")
PY
  fi
fi

echo "[smoke] ALL OK"

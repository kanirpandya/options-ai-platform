# Purpose: Validate that stdin contains at least one complete JSON object (extract the first {...}).
import sys
import json

s = sys.stdin.read()
start = s.find("{")
if start == -1:
    raise SystemExit("no JSON object found on stdout")

depth = 0
for i, ch in enumerate(s[start:], start):
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            json.loads(s[start : i + 1])
            print("OK")
            raise SystemExit(0)

raise SystemExit("incomplete JSON object")

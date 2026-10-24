"""Stand-in for `claude -p` in tests. No tokens, no network.

Appends one JSON line per call to $FAKE_CLAUDE_LOG (argv, cwd, whether API key
variables reached it) and behaves according to $FAKE_CLAUDE_MODE:

    success     a result with a valid structured report (default)
    slow        like success, after FAKE_CLAUDE_SLEEP seconds
    limit       an error result, as when the plan's usage limit is hit
    garbage     non-JSON output and exit 1, as when a resume fails
    bad_report  success, but the report is missing fields
"""

import json
import os
import sys
import time

args = sys.argv[1:]
with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({
        "args": args,
        "cwd": os.getcwd(),
        "api_key_vars": [k for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") if k in os.environ],
        "stdin_is_empty": sys.stdin.read() == "",
    }) + "\n")

mode = os.environ.get("FAKE_CLAUDE_MODE", "success")
resumed = args[args.index("--resume") + 1] if "--resume" in args else None
session_id = resumed or "session-1"
usage = {"input_tokens": 10, "output_tokens": 500, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 50_000}

if mode == "garbage":
    print(f"No conversation found with session ID: {resumed}", file=sys.stderr)
    sys.exit(1)

if mode == "slow":
    time.sleep(float(os.environ.get("FAKE_CLAUDE_SLEEP", "2")))

result = {"type": "result", "subtype": "success", "is_error": False, "session_id": session_id,
          "result": "done", "usage": usage}
if mode == "limit":
    result.update(subtype="error_during_execution", is_error=True,
                  result="Claude usage limit reached. Your limit will reset at 5pm.")
elif mode == "bad_report":
    result["structured_output"] = {"summary": "half a report"}
else:
    result["structured_output"] = {
        "summary": "Reported the current state.",
        "branch": None,
        "changed": [],
        "tests": "not run",
        "blockers": [],
        "next_step": "Pick the next task.",
    }
print(json.dumps(result))

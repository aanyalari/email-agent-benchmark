# Email Response Benchmark

A local, stdlib-only benchmark skeleton for evaluating email agents on realistic inbound email tasks.

The benchmark is intended to measure the full workflow:

- read an email thread
- inspect CRM, calendar, and knowledge-base context through tools
- choose one primary action
- draft, send, forward, escalate, schedule, ask a follow-up, or ignore
- avoid factual, policy, calendar, and CRM mistakes

Phase 0 only creates the project structure and placeholders. Later phases will fill in the frozen email world, MCP tools, runner, grading, and reports.

## Layout

```text
tasks/tasks.json
  -> runner.py
  -> agent CLI
  -> server/email_mcp.py
  -> data/{inbox.json, crm.json, calendar.json, kb/*.md}
  -> runs/<agent>/<task>/{ledger.json, tool_calls.jsonl, trace.jsonl, result.json}
  -> grading/grader.py
  -> report.py
```

## Quick Check

```bash
find . -maxdepth 3 -type f | sort
python3 runner.py --help
python3 report.py --help
python3 grading/grader.py --help
```

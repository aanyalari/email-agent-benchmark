# Email Response Benchmark

A local, stdlib-only benchmark for evaluating email agents on realistic support,
sales, and scheduling workflows.

The benchmark asks an agent to handle an inbound email thread using a fake but
consistent company world: inbox threads, CRM records, calendar availability, and
knowledge-base policies. A run is graded from the actions the agent records in a
ledger plus the tool calls it made while gathering evidence.

## What It Measures

This benchmark is meant to test whether an agent can:

- read the right email thread
- retrieve supporting CRM, calendar, and policy context
- choose the correct primary workflow action
- create the right draft, forward, escalation, meeting, send, or ignore record
- include required facts from the fake world
- avoid unsafe or unsupported claims
- use the expected classes of tools instead of guessing

It is not just a text-generation benchmark. The grader looks at durable workflow
state in `ledger.json`, not only at a free-form answer.

## Why It Is Agentic

Each task requires a small workflow:

1. Inspect the inbound thread.
2. Use tools to gather missing context.
3. Decide what action is safe and policy-compliant.
4. Mutate the run ledger through an action tool or adapter.
5. Produce artifacts that can be inspected after the run.

For example, a good scheduling agent should read the request, identify the
account owner, check calendar availability, avoid busy slots, and either schedule
the meeting or draft alternatives.

## Fake Email World

The benchmark data lives under `data/`:

```text
data/inbox.json
  Inbound threads and message history.

data/crm.json
  Contacts, companies, customer tier, plans, renewal dates, and account owners.

data/calendar.json
  Availability windows and busy events for company users.

data/kb/*.md
  Policy documents for refunds, pricing, escalation, scheduling, and security.
```

Agents access this world through `server/email_mcp.py` or through the local
adapter arguments used by the starter agents.

The MCP server exposes read tools such as `get_email_thread`,
`search_previous_emails`, `lookup_customer`, `lookup_company`, `search_kb`, and
`get_calendar_availability`. It also exposes action tools such as
`create_draft`, `send_email`, `forward_email`, `schedule_meeting`,
`escalate_email`, and `mark_ignore`.

## Task Structure

Tasks live in `tasks/tasks.json`. Each task defines:

- `id`: stable task id, usually matching the target thread id
- `prompt`: instruction passed to the agent
- `thread_id`: email thread being handled
- `expected_action`: primary action the agent should take
- `required_facts`: facts that must appear in the relevant action text
- `forbidden_claims`: claims that must not appear
- `expected_tool_categories`: required evidence sources, such as `inbox`,
  `crm`, `calendar`, and `kb`
- `expected_ledger`: expected counts for ledger action buckets

Human-readable notes for the starter tasks live in `tasks/GROUND_TRUTH.md`.

## Agents

Agent adapters are configured in `agents.json`.

Current starter agents:

- `baseline_no_tools`: reads only inbox data and does not mutate the ledger. It
  is expected to fail most action-oriented tasks and is useful as a baseline.
- `scripted_tool_agent`: deterministic smoke-test adapter that performs the
  intended workflow for the six MVP tasks. It validates the runner, ledger,
  tool-call logging, and grader.

These adapters are intentionally simple. Future model-backed adapters can be
added to `agents.json` as long as their command writes the expected run
artifacts through the provided paths.

## Run The Benchmark

From the repo root:

```bash
python3 runner.py --agents baseline_no_tools,scripted_tool_agent
python3 report.py
```

Run a subset:

```bash
python3 runner.py --agents scripted_tool_agent --tasks support_001,sched_001
python3 report.py
```

Run repeated trials:

```bash
python3 runner.py --agents scripted_tool_agent --tasks support_001 --reps 3 --runs-dir runs
python3 report.py --runs-dir runs
```

Useful help commands:

```bash
python3 runner.py --help
python3 report.py --help
python3 grading/grader.py --help
```

## Produced Files

The runner writes one directory per agent and task:

```text
runs/<agent>/<task>/
  ledger.json
  tool_calls.jsonl
  trace.jsonl
  stderr.log
  result.json
```

For agents with `uses_mcp: true`, the run directory also includes
`mcp_config.json`.

Repeated runs add a suffix:

```text
runs/<agent>/<task>_r1/
runs/<agent>/<task>_r2/
```

The runner also writes:

```text
runs/summary.json
```

Artifact meanings:

- `ledger.json`: workflow state created by the agent, including drafts,
  sent emails, forwards, escalations, meetings, ignored threads, and CRM updates
- `tool_calls.jsonl`: JSONL log of tool name, category, arguments, success, and
  error text
- `mcp_config.json`: per-run MCP server configuration for agents that need it
- `trace.jsonl`: captured stdout from the agent command
- `stderr.log`: captured stderr, timeout, or launch errors
- `result.json`: deterministic grade for one run
- `summary.json`: list of run results from the latest runner invocation

## Metrics

`result.json` and `report.py` use these core fields:

- `passed`: true when there are no grading reasons
- `reasons`: human-readable failures, such as missing ledger actions, missing
  facts, forbidden claims, missing tool categories, or calendar conflicts
- `warnings`: non-fatal issues, including malformed tool logs or failed tool
  calls
- `action_accuracy`: whether the expected primary ledger action was recorded
- `required_facts_ok`: whether required facts appeared in the relevant action
  text
- `forbidden_claims_ok`: whether prohibited claims were avoided
- `calendar_ok`: whether scheduled meetings satisfy calendar constraints
- `crm_ok`: whether required CRM tool evidence was used
- `tool_categories_ok`: whether the expected source categories were used
- `n_tool_calls`: number of logged tool calls
- `n_failed_tool_calls`: number of logged failed tool calls
- `wall_s`: wall-clock runtime in seconds, added by `runner.py`

`report.py` aggregates all `runs/*/*/result.json` files into a task-by-agent
matrix, per-agent pass rates, average tool calls, failed tool call counts,
average wall time, and failure reasons.

## Current Limitations

- The task suite is currently the six-task MVP in `tasks/tasks.json`.
- The deterministic scripted agent is a wiring check, not a real model result.
- Grading is intentionally exact and local. Required facts and forbidden claims
  are checked with string matching over the relevant ledger text.
- The grader checks tool categories, not full reasoning quality.
- Tone, concision, and user experience quality are only indirectly evaluated.
- `runs/` is ignored by git, so benchmark outputs are local unless explicitly
  copied elsewhere.

## Extend The Benchmark

Use `QUERY_GUIDE.md` before adding or changing tasks. In short: create a
realistic thread, make the needed evidence available in CRM/calendar/KB data,
choose one expected primary action, and write grading fields that are specific
enough to be deterministic.

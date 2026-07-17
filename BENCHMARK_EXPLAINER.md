# Email Response Benchmark Pilot Explanation

This document explains the current local email-response benchmark: what it
measures, how tasks are constructed, how agents are run, what artifacts are
captured, and how to interpret the latest pilot results.

The project is a benchmark-building effort first. The numbers below are pilot
evidence that the benchmark can run real MCP-capable agents and expose objective
workflow mistakes. They should not yet be reported as final model rankings.

## Goal

Build a deterministic benchmark for comparing email agents on realistic inbound
support, sales, scheduling, security, and triage workflows.

The benchmark evaluates agentic email handling rather than free-form reply
quality alone. A good agent must inspect the right email thread, retrieve
customer and policy context, choose a safe workflow action, cite the evidence it
used, and write that action to durable benchmark state.

## What The Benchmark Measures

The benchmark evaluates observable workflow behavior:

- whether the agent reads the target email thread
- whether it gathers expected evidence from inbox, CRM, calendar, and KB tools
- whether it chooses the correct primary action
- whether it writes the correct durable ledger record
- whether it records the required structured fact IDs as action evidence
- whether it avoids forbidden or unsafe claims
- whether calendar actions respect availability and attendee requirements
- whether action tools fail or succeed
- how long the agent takes

This is stricter than judging final prose alone. The grader checks
`ledger.json` and `tool_calls.jsonl`, so an agent cannot pass by merely printing
a plausible answer.

## Methodology

Each run starts from a task definition in `tasks/tasks.json` or
`tasks/tasks_hard.json`. The runner creates a fresh per-task run directory,
initializes an empty workflow ledger, launches the selected agent command, and
captures stdout, stderr, MCP tool calls, and the final ledger.

Agents interact with a fake but internally consistent company world:

| Data source | Contents |
|---|---|
| `data/inbox.json` | inbound email threads and prior messages |
| `data/crm.json` | contacts, companies, tiers, plans, renewal dates, owners |
| `data/calendar.json` | owner availability windows and busy events |
| `data/kb/*.md` | refund, pricing, escalation, scheduling, and security policies |

The primary tool interface is `server/email_mcp.py`, a stdlib stdio MCP-style
JSON-RPC server. It exposes read tools such as `get_email_thread`,
`search_previous_emails`, `lookup_customer`, `lookup_company`, `search_crm`,
`search_kb`, and `get_calendar_availability`. It also exposes action tools such
as `create_draft`, `send_email`, `forward_email`, `schedule_meeting`,
`escalate_email`, and `mark_ignore`.

The benchmark uses deterministic grading. There is no LLM judge in the main
score.

## Structured Evidence

The benchmark originally checked required facts with exact string matching in
the final action text. That was too brittle for real agents: a model could write
a semantically correct reply but fail because it phrased a fact differently.

The current grader uses structured fact IDs instead.

Read tools return visible fact records such as:

```json
{
  "fact_id": "refund_policy.window_30_days",
  "source": "kb/refund_policy.md",
  "category": "kb",
  "text": "Customers may receive a full refund within 30 days of purchase."
}
```

When an agent creates a draft, forward, escalation, meeting, send, or ignore
record, it records the relevant fact IDs in the action tool's `evidence`
argument:

```json
{
  "thread_id": "support_001",
  "body": "...",
  "evidence": [
    "refund_policy.window_30_days",
    "support_001.purchase_date_2026_05_31",
    "support_001.request_date_2026_07_15",
    "maya.standard_tier"
  ]
}
```

The main pass/fail check uses these structured fact IDs. Legacy prose
`required_facts` are still kept as human-readable notes and non-blocking text
warnings.

## Task Set

The current benchmark has 16 machine-checkable tasks: 6 starter tasks and 10
hard tasks.

### Starter Tasks

| Task | Scenario | Expected action | Expected evidence |
|---|---|---|---|
| `support_001` | refund outside window | draft | inbox, CRM, KB |
| `support_002` | VIP outage escalation | escalate | inbox, CRM, KB |
| `sales_001` | new lead pricing | draft | inbox, CRM, KB |
| `sales_002` | existing customer renewal | forward | inbox, CRM, KB |
| `sched_001` | available demo slot | schedule meeting | inbox, CRM, calendar, KB |
| `sched_002` | busy slot alternatives | draft | inbox, CRM, calendar, KB |

### Hard Tasks

| Task | Scenario | Expected action | Expected evidence |
|---|---|---|---|
| `sales_hard_001` | prior-email pricing context | draft | inbox, CRM, KB |
| `support_hard_001` | ambiguous Evergreen identity | ask follow-up | inbox, CRM |
| `ignore_hard_001` | automated newsletter | ignore | inbox |
| `support_hard_002` | refund missing account data | ask follow-up | inbox, KB |
| `support_hard_003` | VIP credit exception | escalate | inbox, CRM, KB |
| `sched_hard_001` | Pacific-time scheduling conversion | schedule meeting | inbox, CRM, calendar, KB |
| `sched_hard_002` | busy slot alternatives | draft | inbox, CRM, calendar, KB |
| `sales_hard_002` | enterprise pricing for existing customer | forward | inbox, CRM, KB |
| `security_hard_001` | PHI in email | escalate | inbox, CRM, KB |
| `support_hard_004` | customer claim contradicts CRM | draft | inbox, CRM, KB |

## Agents

Agent adapters live in `agents.json`.

| Agent | Purpose | Evaluation mode |
|---|---|---|
| `baseline_no_tools` | no-tool baseline that reads only limited inbox context and does not mutate the ledger | local control |
| `scripted_tool_agent` | deterministic wiring check that should pass tasks | local control |
| `codex` | real Codex CLI adapter connected to the email MCP server | MCP agent |
| `claude-haiku` | real Claude Code adapter connected to the email MCP server | MCP agent |
| `claude-sonnet` | real Claude Code adapter connected to the email MCP server | MCP agent |

The scripted agent is not a model result. It exists to prove that the runner,
tools, ledger, call logging, and grader are wired correctly.

The intended model comparison is Claude vs Codex using the same tasks, same MCP
tools, same frozen data, same ledger schema, and same deterministic grader.

## Run Artifacts

Each run writes one directory:

```text
runs/<agent>/<task>/
  ledger.json
  tool_calls.jsonl
  trace.jsonl
  stderr.log
  result.json
  mcp_config.json      # only for MCP-capable agents
```

The runner also writes:

```text
runs/summary.json
```

These artifacts make failures inspectable. For example, a model can choose the
right action but fail because it omitted a required fact ID, skipped CRM
evidence, scheduled the wrong attendee, or promised something the policy forbids.

## Statistic Annotations

| Statistic | What it measures | How to interpret it |
|---|---|---|
| Pass rate | runs with no grading reasons | strict end-to-end task success |
| Evidence coverage | required structured evidence IDs recorded on the action | whether the agent proved the right facts |
| Action accuracy | correct primary ledger action | whether the workflow choice was right |
| Tool categories ok | expected evidence categories used | whether the agent gathered the required kinds of context |
| Forbidden claims ok | unsafe claims absent | whether the agent avoided prohibited promises |
| Calendar ok | meeting constraints satisfied | scheduling correctness |
| Tool calls | logged MCP or adapter tool calls | evidence-gathering activity, not quality by itself |
| Failed tool calls | logged tool errors | tool reliability or agent misuse signal |
| Wall seconds | run duration | runtime cost; higher time is not automatically better |

## Current Validation Snapshot

The current local validation confirms the benchmark harness works.

### Starter-Suite Wiring Check

Command:

```bash
python3 runner.py --agents baseline_no_tools,scripted_tool_agent --runs-dir /tmp/email-mvp-metrics-starter --timeout 60
python3 report.py --runs-dir /tmp/email-mvp-metrics-starter
```

Result:

| Agent | Passes | Action | Evidence | Tools | Safe | Calendar | Average calls | Failed calls | Average wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_no_tools` | 0/6 | 0/6 | 0/6 | 0/6 | 6/6 | 5/6 | 0.0 | 0 | 0.0s |
| `scripted_tool_agent` | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 4.8 | 0 | 0.1s |

This is the expected health signal. The baseline fails because it does not write
ledger actions or use evidence tools. The scripted agent passes because it is a
deterministic smoke-test adapter.

### Hard-Suite Wiring Check

Command:

```bash
python3 runner.py --agents scripted_tool_agent --tasks-file tasks/tasks_hard.json --runs-dir /tmp/email-mvp-metrics-hard --timeout 60
python3 report.py --runs-dir /tmp/email-mvp-metrics-hard --tasks-file tasks/tasks_hard.json
```

Result:

| Agent | Passes | Action | Evidence | Tools | Safe | Calendar | Average calls | Failed calls | Average wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `scripted_tool_agent` | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 4.2 | 0 | 0.1s |

This confirms the hard task suite, MCP server, ledger schema, and grader are
coherent end to end.

## Real-Agent Pilot Results

### Codex Starter Suite

Command:

```bash
python3 runner.py --agents codex --timeout 600 --runs-dir results/codex-starter-structured-v2
python3 report.py --runs-dir results/codex-starter-structured-v2
```

Result:

| Agent | Passes | Action | Evidence | Tools | Safe | Calendar | Average calls | Failed calls | Average wall time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `codex` | 3/6 | 6/6 | 4/6 | 6/6 | 6/6 | 5/6 | 7.5 | 0 | 135.5s |

Task-level result:

| Task | Result | Failure type |
|---|---|---|
| `support_001` | pass | none |
| `support_002` | pass | none |
| `sales_001` | fail | missing evidence ID `brightpath.company_name` |
| `sales_002` | fail | missing policy evidence ID `pricing.renewal_discount_forward_owner` |
| `sched_001` | fail | scheduled correct slot but omitted attendee `jordan@company.example` |
| `sched_002` | pass | none |

Interpretation: Codex can connect to the MCP tools, gather evidence, write
ledger actions, and pass several tasks. Its failures are now objective workflow
or evidence-grounding failures, not brittle exact-wording failures.

### Claude Adapter Smoke

Claude Code 2.1.212 is installed and the `claude-haiku` / `claude-sonnet`
adapters are configured in `agents.json`. A one-task smoke launched the Claude
CLI, but it did not complete a model run because local Claude authentication was
expired.

Command:

```bash
python3 runner.py --agents claude-haiku --tasks support_001 --timeout 600 --runs-dir results/claude-debug
```

Observed trace:

```text
Failed to authenticate: OAuth session expired and could not be refreshed
```

Interpretation: this is an environment/authentication blocker, not a benchmark
or MCP wiring result. Claude should be rerun after logging in through:

```bash
claude
```

## Interpretation

This benchmark is useful because it separates several questions that are often
blurred together:

- Can the agent connect to tools?
- Can it find the right thread?
- Can it retrieve the right context?
- Can it choose the right workflow action?
- Can it write the durable action record?
- Can it cite the exact structured facts used as evidence?
- Can it avoid unsafe promises?
- Can it handle calendar constraints correctly?

A high tool-call count is not automatically good. The relevant question is
whether the agent used the right evidence sources and converted that evidence
into the correct ledger action.

Similarly, a polished answer is not enough. If the ledger is empty, the wrong
action bucket is used, required fact IDs are missing, or required attendees are
omitted, the run fails.

## Caveats

The current numbers are validation snapshots and a small real-agent pilot. They
should not be reported as final model rankings.

Known caveats:

- The scripted agent is deterministic and should not be compared as a model.
- Real CLI-agent results depend on local auth, provider network access, CLI
  version, model setting, and approval/sandbox mode.
- Codex headless MCP mode currently uses a broader approval/sandbox bypass to
  avoid auto-cancelled MCP tool calls.
- Claude is installed and configured but still needs local authentication before
  a valid Claude-vs-Codex comparison can be run.
- Fact-ID grading is more objective than exact prose matching, but it still
  depends on agents correctly carrying evidence IDs from read tools into action
  tools.
- Tone, concision, and customer-experience quality are only indirectly
  evaluated.
- `runs/` is ignored by git, so local outputs must be preserved explicitly if
  they are used in a report.

## Recommended Next Steps

1. Log in to Claude Code locally and rerun the `claude-haiku` smoke test.
2. Run Claude and Codex on the same starter suite with the same timeout and MCP
   access.
3. Repeat each task multiple times to separate stable behavior from stochastic
   variation.
4. Run the hard suite only after starter-suite tool behavior is stable.
5. Preserve raw run directories for every reported result.
6. Report model identity, CLI version, timeout, approval mode, and whether MCP
   or uploaded-file mode was used.
7. Keep deterministic pass/fail as the main score; optionally add an LLM judge
   only as a secondary tone/helpfulness metric.

## Source Artifacts

Primary source files:

- `README.md`
- `PLAN.md`
- `QUERY_GUIDE.md`
- `agents.json`
- `runner.py`
- `server/email_mcp.py`
- `grading/grader.py`
- `report.py`
- `tasks/tasks.json`
- `tasks/tasks_hard.json`
- `tasks/GROUND_TRUTH.md`

Pilot result folders referenced:

- `results/codex-debug-structured`
- `results/codex-starter-structured-v2`
- `results/claude-debug`

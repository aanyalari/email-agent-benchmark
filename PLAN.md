# Email Reply Agent Benchmark Plan

This document is meant to be detailed enough that each phase can be done in a fresh chat.

If you open a new chat, paste the phase's "New Chat Prompt" and tell the agent to work in:

```text
/Users/aanyalari/benchmark/email-response-benchmark
```

## Project Goal

Build a free, local benchmark for evaluating email agents on realistic inbound email tasks.

The benchmark should answer:

> Which agent handles support, sales, and scheduling emails most correctly?

This is not only an email-writing benchmark. It evaluates the full workflow:

1. Read the email thread.
2. Decide the correct action.
3. Look up relevant context.
4. Draft, send, forward, schedule, escalate, ask a follow-up question, or ignore.
5. Avoid factual, policy, calendar, and CRM mistakes.

## Model Benchmark Shape

This project should copy the structure of `flight-benchmark`.

Flight benchmark:

```text
tasks/tasks.json
  -> runner.py
  -> agent CLI
  -> server/flight_mcp.py
  -> data/snapshot.json
  -> runs/<agent>/<task>/{ledger.json, tool_calls.jsonl, trace.jsonl, result.json}
  -> grading/grader.py
  -> report.py
```

Email benchmark:

```text
tasks/tasks.json
  -> runner.py
  -> email agent
  -> server/email_mcp.py
  -> data/{inbox.json, crm.json, calendar.json, kb/*.md}
  -> runs/<agent>/<task>/{ledger.json, tool_calls.jsonl, trace.jsonl, result.json}
  -> grading/grader.py
  -> report.py
```

The benchmark owns the environment. Agents must use benchmark tools instead of directly reading hidden answers.

## Final Repository Layout

Build toward this structure:

```text
email-response-benchmark/
  PLAN.md
  README.md
  QUERY_GUIDE.md
  agents.json
  runner.py
  report.py
  web/
    app.py
  data/
    inbox.json
    crm.json
    calendar.json
    kb/
      refund_policy.md
      pricing.md
      scheduling_rules.md
      escalation_policy.md
      security_policy.md
  tasks/
    tasks.json
    tasks_hard.json
    GROUND_TRUTH.md
  server/
    email_mcp.py
  grading/
    grader.py
  agents/
    baseline_no_tools.py
    scripted_tool_agent.py
  runs/
    <agent>/
      <task>/
        ledger.json
        tool_calls.jsonl
        trace.jsonl
        stderr.log
        result.json
```

## Action Labels

Every task should expect exactly one primary action:

```text
draft
send
ask_followup
forward
escalate
schedule_meeting
ignore
```

For the first version, prefer `draft` over `send` for safety. Include `send` later only if needed.

## What The Benchmark Captures

With the local MCP/tool design, we can capture:

- Which email thread was opened
- Which previous emails were searched
- Which CRM records were accessed
- Which companies were looked up
- Which calendar slots were checked
- Which knowledge-base files were searched
- Number of tool calls
- Failed tool calls
- Final action
- Draft body
- Sent email body, if enabled
- Calendar changes
- Escalations
- Forwards
- Ignored threads
- Runtime

If later we use API-based models, we may also capture:

- Input tokens
- Output tokens
- Estimated cost

Native ChatGPT/Claude web connectors usually cannot expose exact tool calls or token usage. They are useful for black-box evaluation, not full trajectory logging.

## Phase 0: Initialize The Project Skeleton

### Goal

Create the folders and placeholder files so future phases have a stable structure.

### Files To Create

```text
README.md
QUERY_GUIDE.md
agents.json
runner.py
report.py
data/inbox.json
data/crm.json
data/calendar.json
data/kb/refund_policy.md
data/kb/pricing.md
data/kb/scheduling_rules.md
data/kb/escalation_policy.md
data/kb/security_policy.md
tasks/tasks.json
tasks/GROUND_TRUTH.md
server/email_mcp.py
grading/grader.py
agents/baseline_no_tools.py
agents/scripted_tool_agent.py
```

### Implementation Notes

- Keep everything Python 3 standard library at first.
- Do not install dependencies for the MVP.
- Add `.gitignore` with:

```text
runs/
__pycache__/
*.pyc
.DS_Store
```

### Done When

This command shows the expected files:

```bash
find . -maxdepth 3 -type f | sort
```

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 0 from PLAN.md: create the project skeleton, placeholder files, and .gitignore. Keep it stdlib-only and do not implement full logic yet.
```

## Phase 1: Build The Frozen Email World

### Goal

Create a fake but fixed email environment that all agents use.

### Files To Edit

```text
data/inbox.json
data/crm.json
data/calendar.json
data/kb/*.md
```

### Required Data

Create 6 starter threads:

- `support_001`: refund outside window
- `support_002`: angry VIP customer requiring escalation
- `sales_001`: new lead asking for pricing
- `sales_002`: existing customer renewal question that should be forwarded
- `sched_001`: schedule demo at available time
- `sched_002`: requested meeting time unavailable, ask/propose alternatives

### `data/inbox.json` Schema

```json
{
  "threads": [
    {
      "thread_id": "support_001",
      "category": "support",
      "subject": "Refund request",
      "messages": [
        {
          "message_id": "support_001_m1",
          "from": "maya@acme.example",
          "to": "support@company.example",
          "timestamp": "2026-07-15T10:00:00-05:00",
          "body": "Hi, I bought the Pro plan 45 days ago and would like a refund."
        }
      ]
    }
  ]
}
```

### `data/crm.json` Schema

```json
{
  "contacts": [
    {
      "email": "maya@acme.example",
      "name": "Maya Chen",
      "company_id": "acme",
      "role": "Operations Manager",
      "tier": "standard",
      "account_owner": "jordan@company.example",
      "customer_since": "2026-05-31"
    }
  ],
  "companies": [
    {
      "company_id": "acme",
      "name": "Acme Health",
      "deal_stage": "customer",
      "renewal_date": "2026-08-30"
    }
  ]
}
```

### `data/calendar.json` Schema

```json
{
  "users": {
    "jordan@company.example": {
      "timezone": "America/Chicago",
      "availability": [
        {
          "start": "2026-07-18T14:00:00-05:00",
          "end": "2026-07-18T14:30:00-05:00"
        }
      ],
      "events": [
        {
          "title": "Existing demo",
          "start": "2026-07-18T13:00:00-05:00",
          "end": "2026-07-18T13:30:00-05:00",
          "attendees": ["lead@example.com"]
        }
      ]
    }
  }
}
```

### Knowledge Base Files

Keep policies short and explicit.

`refund_policy.md` should include:

```text
Customers may receive a full refund within 30 days of purchase.
After 30 days, standard customers are not eligible for refunds.
VIP customers may receive store credit only after manager approval.
Agents must not promise that a refund has been processed unless an approved refund action exists.
```

`scheduling_rules.md` should include:

```text
Do not schedule over busy calendar events.
If the requested time is unavailable, propose available alternatives.
Include requested attendees when they are present in CRM or the email thread.
```

### Done When

Run:

```bash
python3 -m json.tool data/inbox.json
python3 -m json.tool data/crm.json
python3 -m json.tool data/calendar.json
```

All commands should succeed.

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 1 from PLAN.md: create the 6-thread frozen fake email world in data/inbox.json, data/crm.json, data/calendar.json, and data/kb/*.md. Keep the data small, deterministic, and machine-checkable.
```

## Phase 2: Build Machine-Checkable Tasks

### Goal

Create task specs that combine a natural-language prompt with hidden grading rules.

### Files To Edit

```text
tasks/tasks.json
tasks/GROUND_TRUTH.md
```

### `tasks/tasks.json` Schema

Use this structure:

```json
{
  "tasks": [
    {
      "id": "support_001",
      "name": "refund-outside-window",
      "prompt": "Handle email thread support_001. Decide the correct action and create the appropriate draft or workflow action.",
      "thread_id": "support_001",
      "expected_action": "draft",
      "required_facts": [
        "refund window is 30 days",
        "customer purchased 45 days ago",
        "customer is standard tier"
      ],
      "forbidden_claims": [
        "refund has been processed",
        "eligible for a full refund",
        "VIP"
      ],
      "expected_tool_categories": ["inbox", "crm", "kb"],
      "expected_ledger": {
        "drafts": 1,
        "sent_emails": 0,
        "forwards": 0,
        "escalations": 0,
        "scheduled_meetings": 0,
        "ignored_threads": 0
      }
    }
  ]
}
```

### Starter Task Requirements

Create one task per Phase 1 thread:

- `support_001`: expected action `draft`
- `support_002`: expected action `escalate`
- `sales_001`: expected action `draft`
- `sales_002`: expected action `forward`
- `sched_001`: expected action `schedule_meeting`
- `sched_002`: expected action `ask_followup` or `draft`, depending on the email text

### Ground Truth File

`tasks/GROUND_TRUTH.md` should be human-readable:

```text
## support_001

Expected action: draft
Why: The customer is outside the 30-day refund window and is standard tier.
Must mention: 30-day refund window.
Must not mention: refund processed, full refund approved.
```

### Done When

Run:

```bash
python3 -m json.tool tasks/tasks.json
```

Then manually verify every task ID exists in `data/inbox.json`.

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 2 from PLAN.md: create machine-checkable tasks/tasks.json and human-readable tasks/GROUND_TRUTH.md for the 6 starter email threads. Do not include hidden answers inside data/inbox.json.
```

## Phase 3: Build The Email Ledger Format

### Goal

Define the per-run final state that the grader will check.

### Files To Edit

```text
server/email_mcp.py
grading/grader.py
```

At this phase, it is acceptable to create helper functions without implementing full MCP yet.

### Ledger Schema

Every run should start with:

```json
{
  "drafts": [],
  "sent_emails": [],
  "forwards": [],
  "escalations": [],
  "scheduled_meetings": [],
  "ignored_threads": [],
  "crm_updates": []
}
```

### Action Records

Draft:

```json
{
  "thread_id": "support_001",
  "body": "Hi Maya...",
  "created_by": "agent"
}
```

Escalation:

```json
{
  "thread_id": "support_002",
  "reason": "VIP refund exception requires manager approval",
  "created_by": "agent"
}
```

Meeting:

```json
{
  "thread_id": "sched_001",
  "title": "Demo with Acme Health",
  "start": "2026-07-18T14:00:00-05:00",
  "end": "2026-07-18T14:30:00-05:00",
  "attendees": ["maya@acme.example", "jordan@company.example"],
  "created_by": "agent"
}
```

### Done When

There is a function that can initialize a ledger file, load it, and save it without losing fields.

Suggested functions:

```python
empty_ledger()
load_ledger(path)
save_ledger(path, ledger)
```

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 3 from PLAN.md: implement the ledger schema helpers for drafts, sends, forwards, escalations, scheduled meetings, ignored threads, and CRM updates. Keep it stdlib-only.
```

## Phase 4: Build The MCP Tool Server

### Goal

Expose the fake email world through tools and log every tool call.

### Files To Edit

```text
server/email_mcp.py
```

### Tools To Implement

Read tools:

```text
get_email_thread(thread_id)
search_previous_emails(query)
lookup_customer(email)
lookup_company(company_id)
search_crm(query)
search_kb(query)
get_calendar_availability(user_id, date_range)
```

Write/action tools:

```text
create_draft(thread_id, body)
send_email(thread_id, body)
forward_email(thread_id, recipient, note)
schedule_meeting(thread_id, attendees, start, end, title)
escalate_email(thread_id, reason)
mark_ignore(thread_id, reason)
```

### Environment Variables

The server should read:

```text
EMAIL_BENCH_INBOX
EMAIL_BENCH_CRM
EMAIL_BENCH_CALENDAR
EMAIL_BENCH_KB_DIR
EMAIL_BENCH_LEDGER
EMAIL_BENCH_CALLS_LOG
```

### Tool Call Log Format

Append one JSON object per call to `tool_calls.jsonl`:

```json
{
  "ts": 1784142000.0,
  "tool": "lookup_customer",
  "category": "crm",
  "arguments": {
    "email": "maya@acme.example"
  },
  "ok": true,
  "error": ""
}
```

### Validation Rules

The MCP server should reject:

- Unknown thread IDs
- Unknown customer emails
- Scheduling over an existing event
- Scheduling outside available slots
- Empty draft bodies
- Empty escalation reasons
- Forwarding without recipient

### MCP Protocol

Copy the simple stdio JSON-RPC pattern from `flight-benchmark/server/flight_mcp.py`.

Minimum methods:

```text
initialize
ping
tools/list
tools/call
```

### Done When

You can manually call the server through an MCP-compatible agent later. For this phase, at minimum:

- `python3 -m py_compile server/email_mcp.py` succeeds.
- The file includes a `TOOLS` dictionary.
- Every tool logs calls server-side.

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 4 from PLAN.md: implement server/email_mcp.py as a stdlib stdio MCP-style JSON-RPC server with the email, CRM, calendar, KB, and action tools. Use the flight-benchmark MCP server as the pattern.
```

## Phase 5: Build Agent Adapters

### Goal

Define how each benchmark agent is launched.

### Files To Edit

```text
agents.json
agents/baseline_no_tools.py
agents/scripted_tool_agent.py
```

### Initial Agents

Agent 1: `baseline_no_tools`

- Reads the prompt and visible thread text only.
- Cannot use MCP tools.
- Produces a JSON result with action and draft.
- Used to show the weakness of no-tool email handling.

Agent 2: `scripted_tool_agent`

- Uses the fake tools or directly calls a local helper in a controlled way.
- Should pass all 6 starter tasks.
- Used to smoke-test the benchmark.

Later agents:

- `codex`
- `claude`
- `ollama_agent`
- `langgraph_agent`

### `agents.json` Shape

```json
{
  "_comment": "Agent adapters. Placeholders: {prompt}, {mcp_config}, {server}, {ledger}, {calls_log}, {inbox}, {crm}, {calendar}, {kb_dir}.",
  "baseline_no_tools": {
    "kind": "local",
    "uses_mcp": false,
    "cmd": ["python3", "agents/baseline_no_tools.py", "--prompt", "{prompt}", "--inbox", "{inbox}"]
  },
  "scripted_tool_agent": {
    "kind": "local",
    "uses_mcp": false,
    "cmd": ["python3", "agents/scripted_tool_agent.py", "--task-id", "{task_id}", "--ledger", "{ledger}", "--inbox", "{inbox}", "--crm", "{crm}", "--calendar", "{calendar}", "--kb-dir", "{kb_dir}", "--calls-log", "{calls_log}"]
  }
}
```

### Done When

Run:

```bash
python3 -m json.tool agents.json
python3 -m py_compile agents/baseline_no_tools.py
python3 -m py_compile agents/scripted_tool_agent.py
```

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 5 from PLAN.md: implement agents.json, a no-tool baseline agent, and a scripted tool agent that can smoke-test the 6 starter tasks. Keep command-line interfaces simple and stdlib-only.
```

## Phase 6: Build The Runner

### Goal

Run agents against tasks, create per-run artifacts, and call the grader.

### Files To Edit

```text
runner.py
```

### Runner Responsibilities

For each agent/task/repetition:

1. Load `agents.json`.
2. Load `tasks/tasks.json`.
3. Create `runs/<agent>/<task>/`.
4. Create fresh `ledger.json`.
5. Create per-run `mcp_config.json` if the agent uses MCP.
6. Create empty `tool_calls.jsonl`.
7. Build the prompt.
8. Launch the agent command with a timeout.
9. Save stdout to `trace.jsonl`.
10. Save stderr to `stderr.log`.
11. Run `grading.grader.grade`.
12. Save `result.json`.
13. Print one summary line per run.

### Prompt Template

Use a prompt similar to:

```text
You are an email reply agent.

All email, CRM, calendar, and policy data lives in the provided tools.
Do not invent facts.
Use the tools to inspect the thread and relevant context.
If the request cannot be completed safely, escalate or ask a follow-up question.
Do not send an email unless the task clearly requires sending.
Finish only after creating the correct draft/action in the system.

TASK: {task_prompt}
```

### CLI

Support:

```bash
python3 runner.py --agents baseline_no_tools,scripted_tool_agent
python3 runner.py --agents scripted_tool_agent --tasks support_001,sched_001
python3 runner.py --agents scripted_tool_agent --reps 3
```

### Done When

This command creates run folders:

```bash
python3 runner.py --agents baseline_no_tools,scripted_tool_agent
```

Expected artifacts:

```text
runs/<agent>/<task>/ledger.json
runs/<agent>/<task>/tool_calls.jsonl
runs/<agent>/<task>/trace.jsonl
runs/<agent>/<task>/stderr.log
runs/<agent>/<task>/result.json
```

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 6 from PLAN.md: implement runner.py to load agents/tasks, create per-run ledgers/logs, run each agent command, call the grader, and save result.json. Model it after flight-benchmark/runner.py.
```

## Phase 7: Build The Deterministic Grader

### Goal

Score each run using the task spec, ledger, and tool-call log.

### Files To Edit

```text
grading/grader.py
```

### Grader Inputs

```text
task spec
run_dir/ledger.json
run_dir/tool_calls.jsonl
optional data files
```

### Grader Output

`result.json` should include:

```json
{
  "task_id": "support_001",
  "passed": true,
  "reasons": [],
  "warnings": [],
  "action_accuracy": true,
  "required_facts_ok": true,
  "forbidden_claims_ok": true,
  "calendar_ok": true,
  "crm_ok": true,
  "n_tool_calls": 4,
  "n_failed_tool_calls": 0,
  "wall_s": 0.5
}
```

### Deterministic Checks

Implement these first:

- Expected action exists in the correct ledger field.
- Expected ledger counts match.
- No unexpected extra actions.
- Draft body contains required facts, using simple case-insensitive substring checks.
- Draft body does not contain forbidden claims.
- Escalation reason is non-empty when escalation is expected.
- Forward recipient exists when forward is expected.
- Scheduled meeting has expected attendees if specified.
- Scheduled meeting does not overlap busy events.
- Scheduled meeting occurs within availability.
- Tool-call count is recorded.
- Failed tool calls are counted.

### Keep Out Of MVP

Do not add LLM judging yet. Email tone can be evaluated later.

### Done When

Run:

```bash
python3 -m py_compile grading/grader.py
python3 runner.py --agents scripted_tool_agent
```

The scripted agent should pass all 6 starter tasks.

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 7 from PLAN.md: implement grading/grader.py with deterministic checks over ledger.json, tool_calls.jsonl, and tasks/tasks.json. Do not add LLM judging yet.
```

## Phase 8: Build The Report

### Goal

Aggregate run results into a readable benchmark report.

### Files To Edit

```text
report.py
```

### Report Should Print

- Task-by-agent pass/fail matrix
- Pass rate by agent
- Average tool calls
- Failed tool calls
- Average wall time
- Failure reasons

### CLI

```bash
python3 report.py
python3 report.py --runs-dir runs
```

### Example Output

```text
task x agent
task          baseline_no_tools  scripted_tool_agent
support_001  F                  P
support_002  F                  P

agent                  pass     avg calls   failed calls   avg wall
baseline_no_tools       2/6          0.0              0       0.2s
scripted_tool_agent     6/6          3.8              0       0.5s

failures:
  baseline_no_tools support_001: missing required fact refund window is 30 days
```

### Done When

After running:

```bash
python3 runner.py --agents baseline_no_tools,scripted_tool_agent
python3 report.py
```

The report should summarize all `runs/*/*/result.json` files.

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 8 from PLAN.md: implement report.py to aggregate result.json files into a task-by-agent matrix, per-agent summary, and failure list.
```

## Phase 9: Write README And Query Guide

### Goal

Make the benchmark understandable to someone else.

### Files To Edit

```text
README.md
QUERY_GUIDE.md
```

### README Should Explain

- What the benchmark measures
- Why it is agentic
- How the fake email world works
- How tasks are structured
- How to run the benchmark
- What files are produced
- What metrics mean
- Current limitations

### QUERY_GUIDE Should Explain

- How to write good email benchmark tasks
- How to create traps
- How to choose expected actions
- How to write required facts
- How to write forbidden claims
- How to avoid ambiguous grading

### Done When

A new person can run:

```bash
python3 runner.py --agents baseline_no_tools,scripted_tool_agent
python3 report.py
```

by following the README.

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 9 from PLAN.md: write README.md and QUERY_GUIDE.md so another person can understand, run, and extend the benchmark.
```

## Phase 10: Add Hard Tasks

### Goal

Add a harder suite after the 6-task MVP works.

### Files To Edit

```text
tasks/tasks_hard.json
tasks/GROUND_TRUTH.md
data/inbox.json
data/crm.json
data/calendar.json
data/kb/*.md
```

### Hard Task Mechanisms

Add tasks that test:

- Prior-email dependency
- Ambiguous customer identity
- Correct action is ignore
- Correct action is ask follow-up
- VIP exception requires escalation
- Calendar time-zone trap
- Requested time conflicts with busy slot
- Sales lead must be forwarded to account owner
- Security/privacy request must not be answered directly
- Contradiction between email claim and CRM record

### Done When

Runner supports:

```bash
python3 runner.py --agents scripted_tool_agent --tasks-file tasks/tasks_hard.json
```

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 10 from PLAN.md: add tasks/tasks_hard.json with harder email-agent tasks and update fake data as needed. Keep tasks deterministic and machine-checkable.
```

## Phase 11: Build Local Web Dashboard

### Goal

Add a local browser dashboard like `flight-benchmark/web/app.py` so the benchmark
has something visible to inspect.

### Files To Create Or Edit

```text
web/app.py
README.md
PLAN.md
```

### Dashboard Should Show

- Agent list
- Starter and hard task catalogs
- Latest run pass/fail table
- Per-run ledger, tool calls, result JSON, trace, and stderr
- A small run launcher for selected agents and tasks

### CLI

```bash
python3 web/app.py
```

Open:

```text
http://127.0.0.1:8798
```

### Done When

These work:

```bash
python3 -m py_compile web/app.py
python3 web/app.py
```

The browser page can load the latest `runs/summary.json`, inspect a run
directory, and launch at least one `scripted_tool_agent` task.

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 11 from PLAN.md: add a stdlib-only local web dashboard in web/app.py that shows tasks, agents, latest results, per-run artifacts, and can launch selected benchmark runs.
```

## Phase 12: Add Real MCP-Capable Agents

### Goal

Run real CLI agents against the benchmark tools.

### Files To Edit

```text
agents.json
runner.py
README.md
```

### Possible Agents

- Codex CLI with MCP
- Claude CLI with MCP
- Local Ollama wrapper
- LangGraph agent

### Important Rule

Compare agents under the same environment and tools.

Do not compare:

```text
one agent with MCP tools
another agent with uploaded files
```

unless the report clearly says they are different evaluation modes.

### Done When

At least one real MCP-capable agent can run through:

```bash
python3 runner.py --agents <agent_name> --tasks support_001
```

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 12 from PLAN.md: add one real MCP-capable agent adapter to agents.json and update runner.py/README.md only as needed. Preserve the same fake tools and grading.
```

## Phase 13: Optional Black-Box ChatGPT/Claude Upload Evaluation

### Goal

Support a separate black-box mode where ChatGPT or Claude receives uploaded files instead of MCP tools.

### Why This Is Separate

Uploaded-file evaluation can capture:

- Final action
- Draft quality
- Factual accuracy
- Claimed sources

It usually cannot capture:

- Exact tool calls
- Exact previous emails opened
- Token usage
- Failed internal searches

### Files To Create

```text
exports/upload_bundle/
  inbox_public.json
  crm_public.json
  calendar_public.json
  kb/
  prompts/
```

Do not include hidden answer keys in the upload bundle.

### Done When

There is a documented process for manually asking ChatGPT/Claude to handle one task and saving the output for scoring.

### New Chat Prompt

```text
We are building /Users/aanyalari/benchmark/email-response-benchmark. Please complete Phase 13 from PLAN.md: create a black-box upload evaluation bundle and instructions for manually testing ChatGPT/Claude without exposing hidden answer keys.
```

## MVP Completion Checklist

The MVP is complete when all of these work:

```bash
python3 -m json.tool data/inbox.json
python3 -m json.tool data/crm.json
python3 -m json.tool data/calendar.json
python3 -m json.tool tasks/tasks.json
python3 -m json.tool agents.json
python3 -m py_compile server/email_mcp.py
python3 -m py_compile grading/grader.py
python3 -m py_compile runner.py
python3 -m py_compile report.py
python3 -m py_compile web/app.py
python3 runner.py --agents baseline_no_tools,scripted_tool_agent
python3 report.py
```

Expected MVP result:

- `scripted_tool_agent` passes all 6 starter tasks.
- `baseline_no_tools` fails at least some tasks, showing why tools matter.
- Every run has `ledger.json`, `tool_calls.jsonl`, `trace.jsonl`, `stderr.log`, and `result.json`.

## Key Design Principles

- Keep the first version small.
- Make grading deterministic before adding LLM judges.
- Hide answer keys from agents.
- Log tool calls server-side.
- Score final state through `ledger.json`.
- Prefer exact, machine-checkable task rules.
- Add hard cases only after the easy suite works.
- Keep black-box web testing separate from full-trace MCP testing.

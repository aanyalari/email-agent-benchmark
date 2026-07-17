# Query Guide

This guide explains how to write email benchmark tasks that separate capable
workflow agents from agents that guess, overpromise, or skip evidence gathering.

Tasks live in `tasks/tasks.json`. Human review notes can go in
`tasks/GROUND_TRUTH.md`.

## Good Task Shape

A strong task has:

- one realistic inbound thread
- enough hidden context in CRM, calendar, or KB data to require tool use
- one correct primary action
- at least one plausible wrong action
- required facts that prove the agent found the right evidence
- forbidden claims that catch unsafe shortcuts
- deterministic grading expectations

Prefer tasks where the email alone is insufficient. If a person could answer
perfectly from the thread without checking any other source, the task will not
measure agentic behavior very well.

## Task Fields

Use this shape:

```json
{
  "id": "support_003",
  "name": "short-human-readable-name",
  "prompt": "Handle email thread support_003. Decide the correct action and create the appropriate draft or workflow action.",
  "thread_id": "support_003",
  "expected_action": "draft",
  "required_facts": [
    "customer is standard tier",
    "refund window is 30 days"
  ],
  "forbidden_claims": [
    "refund approved"
  ],
  "expected_tool_categories": [
    "inbox",
    "crm",
    "kb"
  ],
  "expected_ledger": {
    "drafts": 1,
    "sent_emails": 0,
    "forwards": 0,
    "escalations": 0,
    "scheduled_meetings": 0,
    "ignored_threads": 0
  }
}
```

Keep the `id`, `thread_id`, and inbox thread id aligned unless there is a clear
reason not to. That makes artifacts and failure messages easy to inspect.

## Choosing Expected Actions

Choose exactly one primary action per task.

Supported actions:

- `draft`: create a safe draft reply without sending
- `send`: send a reply when immediate sending is clearly expected
- `ask_followup`: create a draft asking for missing information
- `forward`: forward the thread to the responsible person
- `escalate`: create an escalation record with a factual reason
- `schedule_meeting`: schedule a meeting after checking availability
- `ignore`: mark the thread intentionally ignored with a reason

Map the action to `expected_ledger`:

```text
draft or ask_followup -> drafts
send -> sent_emails
forward -> forwards
escalate -> escalations
schedule_meeting -> scheduled_meetings
ignore -> ignored_threads
```

Set every normal action bucket in `expected_ledger`, including the buckets that
should remain zero. This catches agents that do the right action plus an unsafe
extra action.

## Creating Traps

Good traps are realistic mistakes a weak agent might make:

- A customer asks for a refund, but the purchase date is outside policy.
- A VIP complaint sounds like a refund request, but policy requires escalation.
- A lead asks about pricing, but renewal discounts are only handled by an
  account owner.
- A meeting time sounds available from the email, but the calendar has a busy
  event.
- The sender mentions one attendee, while CRM or the thread reveals another
  required attendee.
- A policy has exceptions that depend on customer tier, plan, or renewal status.

Put the evidence for the trap somewhere outside the user email:

- use `data/crm.json` for tier, plan, renewal date, account owner, company, and
  contact facts
- use `data/calendar.json` for available slots and conflicts
- use `data/kb/*.md` for policy rules
- use earlier messages in `data/inbox.json` for thread history

Avoid traps that rely on broad world knowledge, taste, or unstated assumptions.

## Required Facts

`required_facts` are checked against the relevant ledger text for text-based
actions. For drafts and sends, that means the message body. For forwards, it
means recipient and note. For escalations or ignores, it means the reason.

Write facts as explicit strings the correct action can reasonably include:

- good: `customer is VIP tier`
- good: `renewal date is 2026-08-30`
- good: `annual billing is available and includes two months free`
- weak: `customer is important`
- weak: `talk about renewal`

Use canonical dates, email addresses, prices, plan names, and policy phrases
from the data files. The current grader uses exact substring checks after
lowercasing, so do not rely on paraphrases unless the agent is scripted to emit
that exact wording.

For `schedule_meeting`, required facts are useful for human review, but the
current grader does not check those strings against a message body. It mainly
checks the scheduled meeting record: attendees, a parseable start/end time,
calendar user, availability, and busy-event overlap. Design the calendar data so
wrong times fail through conflicts or missing availability.

## Forbidden Claims

`forbidden_claims` catch unsafe or unsupported statements in the same relevant
ledger text.

Use them for claims that would make the workflow wrong even if the action type
looks plausible:

- `refund has been processed`
- `eligible for a full refund`
- `discount carries over`
- `1:00 PM Central is available`
- `no escalation needed`

Keep them short and concrete. Do not add vague style preferences as forbidden
claims.

## Expected Tool Categories

Use `expected_tool_categories` to require evidence gathering. Current categories
are:

- `inbox`: email thread or previous email lookup
- `crm`: customer, company, contact, plan, owner, tier, and renewal facts
- `calendar`: availability and busy-event facts
- `kb`: policy facts

Do not include `action` in `expected_tool_categories`; the grader uses ledger
state for action correctness. Include only the read-side evidence categories the
agent must consult to solve the task.

## Avoid Ambiguous Grading

Before adding a task, check these points:

- There is only one correct primary action.
- The expected ledger counts match that one action.
- Required facts can be copied or naturally stated from the available data.
- Forbidden claims are claims the correct response should definitely avoid.
- Calendar tasks include exact ISO timestamps and required attendees in the
  available data and human notes.
- The prompt points to the target thread id.
- Human notes in `tasks/GROUND_TRUTH.md` explain why the answer is correct.

Avoid tasks where two actions could both be reasonable, such as either drafting a
reply or escalating with no clear policy trigger. If the intended answer depends
on a priority rule, put that rule in the KB and include the `kb` category.

## Suggested Authoring Workflow

1. Add or update the email thread in `data/inbox.json`.
2. Add the needed CRM, calendar, or KB facts.
3. Add the machine-checkable task to `tasks/tasks.json`.
4. Add a short human explanation to `tasks/GROUND_TRUTH.md`.
5. Run a known agent or targeted adapter against the task.
6. Inspect `runs/<agent>/<task>/ledger.json`, `tool_calls.jsonl`, and
   `result.json`.
7. Run `python3 report.py` to confirm the task appears clearly in the matrix.

For quick JSON validation:

```bash
python3 -m json.tool tasks/tasks.json >/tmp/tasks.json
python3 -m json.tool data/inbox.json >/tmp/inbox.json
python3 -m json.tool data/crm.json >/tmp/crm.json
python3 -m json.tool data/calendar.json >/tmp/calendar.json
```

For the current MVP suite:

```bash
python3 runner.py --agents baseline_no_tools,scripted_tool_agent
python3 report.py
```

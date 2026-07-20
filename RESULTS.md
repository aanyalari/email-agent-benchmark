# Codex Results

This file summarizes Codex performance on the current starter suite using the
MVP metrics reported by `report.py`.

## Run Source

These numbers come from the saved Codex starter-suite run:

```bash
python3 runner.py --agents codex --timeout 600 --runs-dir results/codex-starter-structured-v2
python3 report.py --runs-dir results/codex-starter-structured-v2
```

Source artifact:

```text
results/codex-starter-structured-v2/summary.json
```

Suite:

```text
tasks/tasks.json
```

## Aggregate Performance

| Metric | Codex result | Plain meaning |
|---|---:|---|
| Pass rate | 3/6 | Codex fully satisfied the grader on half of the starter tasks. |
| Action accuracy | 6/6 | Codex chose the correct primary action for every task. |
| Evidence coverage | 4/6 | Codex recorded all required structured fact IDs on four tasks. |
| Tool category coverage | 6/6 | Codex used the expected kinds of tools, such as inbox, CRM, calendar, or KB. |
| Safety | 6/6 | Codex avoided all forbidden claims. |
| Calendar correctness | 5/6 | Codex satisfied calendar constraints on all but one scheduling task. |
| Average tool calls | 7.5 | Codex made about eight logged tool calls per task. |
| Failed tool calls | 0 | No tool calls failed in this run. |
| Average runtime | 135.5s | Runtime was skewed by one long scheduling run. |

## Task-Level Results

| Task | Result | Action | Evidence | Tools | Safe | Calendar | Tool calls | Runtime | Failure reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `support_001` | Pass | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 5 | 31.4s | none |
| `support_002` | Pass | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 8 | 30.0s | none |
| `sales_001` | Fail | 1/1 | 0/1 | 1/1 | 1/1 | 1/1 | 7 | 26.2s | missing required fact ID `brightpath.company_name` |
| `sales_002` | Fail | 1/1 | 0/1 | 1/1 | 1/1 | 1/1 | 9 | 36.9s | missing required fact ID `pricing.renewal_discount_forward_owner` |
| `sched_001` | Fail | 1/1 | 1/1 | 1/1 | 1/1 | 0/1 | 10 | 662.1s | scheduled meeting missing attendee `jordan@company.example` |
| `sched_002` | Pass | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 6 | 26.3s | none |

## Interpretation

Codex did well on workflow selection: it chose the correct action on every task
and used the expected tool categories every time. It also avoided forbidden
claims and had no failed tool calls.

The failures were more specific:

- two tasks failed because Codex did not attach one required structured evidence
  fact ID to the final action
- one scheduling task failed because the meeting record did not include the
  expected account-owner attendee

This suggests the current Codex failures are not broad reasoning failures. They
are mostly evidence-recording and action-detail failures under the deterministic
grader.

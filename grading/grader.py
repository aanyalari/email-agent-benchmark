#!/usr/bin/env python3
"""Deterministic grader for the email response benchmark."""
import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.email_mcp import LEDGER_FIELDS, load_ledger


PRIMARY_ACTION_TO_LEDGER_FIELD = {
    "draft": "drafts",
    "send": "sent_emails",
    "ask_followup": "drafts",
    "forward": "forwards",
    "escalate": "escalations",
    "schedule_meeting": "scheduled_meetings",
    "ignore": "ignored_threads",
}


def _load_tool_call_count(run_dir):
    tool_calls_path = Path(run_dir) / "tool_calls.jsonl"
    if not tool_calls_path.exists():
        return 0

    count = 0
    with tool_calls_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _ledger_counts(ledger):
    return {field: len(ledger.get(field, [])) for field in LEDGER_FIELDS}


def _check_expected_ledger(task, ledger):
    reasons = []
    actual_counts = _ledger_counts(ledger)
    expected_counts = task.get("expected_ledger", {})

    for field, expected_count in expected_counts.items():
        actual_count = actual_counts.get(field)
        if actual_count != expected_count:
            reasons.append(
                f"expected {field} count {expected_count}, got {actual_count}"
            )

    expected_action = task.get("expected_action")
    expected_field = PRIMARY_ACTION_TO_LEDGER_FIELD.get(expected_action)
    if expected_action and expected_field is None:
        reasons.append(f"unknown expected action {expected_action!r}")
    elif expected_field and actual_counts.get(expected_field, 0) < 1:
        reasons.append(
            f"expected primary action {expected_action!r} in ledger field {expected_field!r}"
        )

    return reasons


def grade(task, run_dir):
    """Grade one run by comparing ledger state to task expectations."""
    ledger_path = Path(run_dir) / "ledger.json"
    reasons = []

    if not ledger_path.exists():
        reasons.append("missing ledger.json")
        ledger = load_ledger(ledger_path)
    else:
        try:
            ledger = load_ledger(ledger_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            ledger = None
            reasons.append(f"invalid ledger.json: {exc}")

    ledger_counts = _ledger_counts(ledger) if ledger is not None else {}
    if ledger is not None:
        reasons.extend(_check_expected_ledger(task, ledger))

    return {
        "task_id": task.get("id"),
        "passed": not reasons,
        "reasons": reasons,
        "ledger_counts": ledger_counts,
        "n_tool_calls": _load_tool_call_count(run_dir),
        "run_dir": str(run_dir),
    }


def _load_task(tasks_file, task_id):
    with open(tasks_file, "r", encoding="utf-8") as handle:
        tasks = json.load(handle).get("tasks", [])

    if task_id is None:
        return {"id": None}

    for task in tasks:
        if task.get("id") == task_id:
            return task

    raise SystemExit(f"task id not found: {task_id}")


def main():
    parser = argparse.ArgumentParser(description="Grade a single email benchmark run.")
    parser.add_argument("--task-id", required=False, help="task id to grade")
    parser.add_argument("--run-dir", required=False, default="runs/example", help="run artifact directory")
    parser.add_argument("--tasks-file", default="tasks/tasks.json", help="task suite JSON path")
    args = parser.parse_args()

    task = _load_task(args.tasks_file, args.task_id)
    result = grade(task, args.run_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Deterministic grader for the email response benchmark."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.email_mcp import LEDGER_FIELDS, load_ledger


CALENDAR_PATH = PROJECT_ROOT / "data" / "calendar.json"

PRIMARY_ACTION_TO_LEDGER_FIELD = {
    "draft": "drafts",
    "send": "sent_emails",
    "ask_followup": "drafts",
    "forward": "forwards",
    "escalate": "escalations",
    "schedule_meeting": "scheduled_meetings",
    "ignore": "ignored_threads",
}


ACTION_LEDGER_FIELDS = tuple(LEDGER_FIELDS)


def _load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_dt(value, label):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc


def _overlaps(start, end, other_start, other_end):
    return start < other_end and other_start < end


def _contains(slot, start, end):
    slot_start = _parse_dt(slot.get("start"), "availability.start")
    slot_end = _parse_dt(slot.get("end"), "availability.end")
    return slot_start <= start and end <= slot_end


def _load_tool_calls(run_dir):
    tool_calls_path = Path(run_dir) / "tool_calls.jsonl"
    if not tool_calls_path.exists():
        return [], ["missing tool_calls.jsonl"]

    calls = []
    warnings = []
    with tool_calls_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                call = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.append(f"invalid tool_calls.jsonl line {line_no}: {exc}")
                continue
            if not isinstance(call, dict):
                warnings.append(
                    f"invalid tool_calls.jsonl line {line_no}: expected object"
                )
                continue
            calls.append(call)
    return calls, warnings


def _failed_tool_calls(tool_calls):
    return [
        call
        for call in tool_calls
        if call.get("ok") is False or bool(call.get("error"))
    ]


def _critical_failed_tool_calls(tool_calls):
    return [
        call
        for call in _failed_tool_calls(tool_calls)
        if call.get("category") == "action"
    ]


def _tool_categories(tool_calls):
    return sorted(
        {
            str(call.get("category"))
            for call in tool_calls
            if call.get("category") not in (None, "")
        }
    )


def _ledger_counts(ledger):
    return {field: len(ledger.get(field, [])) for field in LEDGER_FIELDS}


def _records_for_task(records, task):
    thread_id = task.get("thread_id")
    if not thread_id:
        return records
    return [record for record in records if record.get("thread_id") == thread_id]


def _expected_action_records(task, ledger):
    expected_action = task.get("expected_action")
    expected_field = PRIMARY_ACTION_TO_LEDGER_FIELD.get(expected_action)
    if not expected_field:
        return []
    return _records_for_task(ledger.get(expected_field, []), task)


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
    elif expected_field and not _expected_action_records(task, ledger):
        reasons.append(
            f"expected primary action {expected_action!r} "
            f"in ledger field {expected_field!r}"
        )

    if expected_counts:
        for field in ACTION_LEDGER_FIELDS:
            if field not in expected_counts and actual_counts.get(field, 0) > 0:
                reasons.append(
                    f"unexpected {field} count {actual_counts[field]} with no expected count"
                )
    elif expected_field:
        for field in ACTION_LEDGER_FIELDS:
            if field != expected_field and actual_counts.get(field, 0) > 0:
                reasons.append(f"unexpected extra action in ledger field {field!r}")

    return reasons


def _record_text(record, keys):
    parts = []
    for key in keys:
        value = record.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value is not None:
            parts.append(str(value))
    return "\n".join(parts)


def _expected_action_text(task, ledger):
    expected_action = task.get("expected_action")
    records = _expected_action_records(task, ledger)
    if expected_action in {"draft", "ask_followup"}:
        return "\n".join(_record_text(record, ("body",)) for record in records)
    if expected_action == "send":
        return "\n".join(_record_text(record, ("body",)) for record in records)
    if expected_action == "forward":
        return "\n".join(
            _record_text(record, ("recipient", "note")) for record in records
        )
    if expected_action == "escalate":
        return "\n".join(_record_text(record, ("reason",)) for record in records)
    if expected_action == "ignore":
        return "\n".join(_record_text(record, ("reason",)) for record in records)
    return ""


def _evidence_fact_ids(task, ledger):
    fact_ids = set()
    for record in _expected_action_records(task, ledger):
        evidence = record.get("evidence") or []
        if not isinstance(evidence, list):
            continue
        for item in evidence:
            if isinstance(item, str):
                fact_id = item.strip()
            elif isinstance(item, dict):
                fact_id = str(item.get("fact_id") or "").strip()
            else:
                continue
            if fact_id:
                fact_ids.add(fact_id)
    return sorted(fact_ids)


def _check_required_fact_ids(task, ledger):
    required_fact_ids = task.get("required_fact_ids", [])
    if not required_fact_ids:
        return True, []

    actual = set(_evidence_fact_ids(task, ledger))
    missing = [fact_id for fact_id in required_fact_ids if fact_id not in actual]
    reasons = [f"missing required fact id: {fact_id}" for fact_id in missing]
    return not reasons, reasons


def _check_required_facts(task, ledger):
    facts = task.get("required_facts", [])
    if not facts:
        return True, []

    expected_action = task.get("expected_action")
    text_actions = {"draft", "ask_followup", "send", "forward", "escalate", "ignore"}
    if expected_action not in text_actions:
        return True, []

    text = _expected_action_text(task, ledger).lower()
    missing = [fact for fact in facts if str(fact).lower() not in text]
    reasons = [f"missing required fact: {fact}" for fact in missing]
    return not reasons, reasons


def _check_forbidden_claims(task, ledger):
    forbidden_claims = task.get("forbidden_claims", [])
    if not forbidden_claims:
        return True, []

    expected_action = task.get("expected_action")
    text_actions = {"draft", "ask_followup", "send", "forward", "escalate", "ignore"}
    if expected_action not in text_actions:
        return True, []

    text = _expected_action_text(task, ledger).lower()
    found = [claim for claim in forbidden_claims if str(claim).lower() in text]
    reasons = [f"forbidden claim present: {claim}" for claim in found]
    return not reasons, reasons


def _check_action_details(task, ledger):
    expected_action = task.get("expected_action")
    records = _expected_action_records(task, ledger)
    reasons = []

    if expected_action == "escalate":
        if not any((record.get("reason") or "").strip() for record in records):
            reasons.append("expected escalation reason to be non-empty")
    elif expected_action == "forward":
        if not any((record.get("recipient") or "").strip() for record in records):
            reasons.append("expected forward recipient to be non-empty")

    return reasons


def _expected_attendees(task):
    explicit = task.get("expected_attendees")
    if explicit:
        return [str(attendee).strip().lower() for attendee in explicit]

    expected_meeting = task.get("expected_meeting") or {}
    explicit = expected_meeting.get("attendees")
    if explicit:
        return [str(attendee).strip().lower() for attendee in explicit]

    attendees = []
    for fact in task.get("required_facts", []):
        words = str(fact).replace(",", " ").split()
        for word in words:
            cleaned = word.strip(" .;:()[]<>").lower()
            if "@" in cleaned and cleaned not in attendees:
                attendees.append(cleaned)
    return attendees


def _check_calendar(task, ledger, calendar_path):
    if task.get("expected_action") != "schedule_meeting":
        return True, []

    meetings = _expected_action_records(task, ledger)
    if not meetings:
        return False, ["expected scheduled meeting record for task"]

    meeting = meetings[0]
    reasons = []
    attendees = {
        str(attendee).strip().lower() for attendee in meeting.get("attendees", [])
    }
    for attendee in _expected_attendees(task):
        if attendee not in attendees:
            reasons.append(f"scheduled meeting missing attendee {attendee}")

    try:
        start = _parse_dt(meeting.get("start"), "meeting.start")
        end = _parse_dt(meeting.get("end"), "meeting.end")
    except ValueError as exc:
        return False, [str(exc)]

    if end <= start:
        reasons.append("scheduled meeting end must be after start")

    try:
        calendar = _load_json(calendar_path)
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"could not load calendar data: {exc}"]

    users = calendar.get("users", {})
    calendar_user = meeting.get("calendar_user")
    user_calendar = users.get(calendar_user)
    if not user_calendar:
        reasons.append(f"unknown scheduled meeting calendar_user {calendar_user!r}")
        return False, reasons

    if not any(_contains(slot, start, end) for slot in user_calendar.get("availability", [])):
        reasons.append("scheduled meeting is outside available calendar slots")

    for event in user_calendar.get("events", []):
        event_start = _parse_dt(event.get("start"), "event.start")
        event_end = _parse_dt(event.get("end"), "event.end")
        if _overlaps(start, end, event_start, event_end):
            reasons.append(
                f"scheduled meeting overlaps busy event {event.get('title', 'untitled')!r}"
            )

    return not reasons, reasons


def _check_expected_tool_categories(task, tool_calls):
    expected = task.get("expected_tool_categories", [])
    categories = set(_tool_categories(tool_calls))
    reasons = [
        f"expected tool category {category!r} was not used"
        for category in expected
        if category not in categories
    ]
    return not reasons, reasons


def grade(task, run_dir, calendar_path=CALENDAR_PATH):
    """Grade one run by comparing ledger state to task expectations."""
    ledger_path = Path(run_dir) / "ledger.json"
    reasons = []
    warnings = []
    action_accuracy = False
    required_fact_ids_ok = True
    forbidden_claims_ok = True
    calendar_ok = True
    tool_categories_ok = True

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
    evidence_fact_ids = []
    if ledger is not None:
        ledger_reasons = _check_expected_ledger(task, ledger)
        detail_reasons = _check_action_details(task, ledger)
        required_fact_ids_ok, fact_id_reasons = _check_required_fact_ids(task, ledger)
        fact_reasons = []
        if not task.get("required_fact_ids"):
            _, fact_reasons = _check_required_facts(task, ledger)
        forbidden_claims_ok, forbidden_reasons = _check_forbidden_claims(task, ledger)
        calendar_ok, calendar_reasons = _check_calendar(task, ledger, calendar_path)
        evidence_fact_ids = _evidence_fact_ids(task, ledger)

        action_accuracy = not ledger_reasons and not detail_reasons
        reasons.extend(ledger_reasons)
        reasons.extend(detail_reasons)
        reasons.extend(fact_id_reasons)
        reasons.extend(fact_reasons)
        reasons.extend(forbidden_reasons)
        reasons.extend(calendar_reasons)

    tool_calls, tool_warnings = _load_tool_calls(run_dir)
    failed_tool_calls = _failed_tool_calls(tool_calls)
    critical_failed_tool_calls = _critical_failed_tool_calls(tool_calls)
    warnings.extend(tool_warnings)
    if failed_tool_calls:
        warnings.append(f"{len(failed_tool_calls)} failed tool call(s) recorded")
    if critical_failed_tool_calls:
        reasons.append(f"{len(critical_failed_tool_calls)} failed action tool call(s)")

    tool_categories_ok, category_reasons = _check_expected_tool_categories(task, tool_calls)
    reasons.extend(category_reasons)

    return {
        "task_id": task.get("id"),
        "passed": not reasons,
        "reasons": reasons,
        "warnings": warnings,
        "action_accuracy": action_accuracy,
        "required_fact_ids_ok": required_fact_ids_ok,
        "forbidden_claims_ok": forbidden_claims_ok,
        "calendar_ok": calendar_ok,
        "tool_categories_ok": tool_categories_ok,
        "ledger_counts": ledger_counts,
        "evidence_fact_ids": evidence_fact_ids,
        "missing_required_fact_ids": [
            fact_id
            for fact_id in task.get("required_fact_ids", [])
            if fact_id not in set(evidence_fact_ids)
        ],
        "n_tool_calls": len(tool_calls),
        "n_failed_tool_calls": len(failed_tool_calls),
        "tool_categories": _tool_categories(tool_calls),
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
    parser.add_argument(
        "--run-dir",
        required=False,
        default="runs/example",
        help="run artifact directory",
    )
    parser.add_argument(
        "--tasks-file", default="tasks/tasks.json", help="task suite JSON path"
    )
    parser.add_argument(
        "--calendar-file", default=str(CALENDAR_PATH), help="calendar data JSON path"
    )
    args = parser.parse_args()

    task = _load_task(args.tasks_file, args.task_id)
    result = grade(task, args.run_dir, args.calendar_file)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Email response benchmark MCP server.

This is a small stdlib-only, stdio JSON-RPC server modeled after the
flight-benchmark MCP server. It exposes the frozen email world through tools,
records benchmark actions in a per-run ledger, and appends every tool call to a
JSONL calls log when configured.
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INBOX_PATH = Path(os.environ.get("EMAIL_BENCH_INBOX", ROOT / "data" / "inbox.json"))
CRM_PATH = Path(os.environ.get("EMAIL_BENCH_CRM", ROOT / "data" / "crm.json"))
CALENDAR_PATH = Path(os.environ.get("EMAIL_BENCH_CALENDAR", ROOT / "data" / "calendar.json"))
KB_DIR = Path(os.environ.get("EMAIL_BENCH_KB_DIR", ROOT / "data" / "kb"))
LEDGER_PATH = Path(os.environ.get("EMAIL_BENCH_LEDGER", Path.cwd() / "ledger.json"))
CALLS_LOG = os.environ.get("EMAIL_BENCH_CALLS_LOG", "")

LEDGER_FIELDS = (
    "drafts",
    "sent_emails",
    "forwards",
    "escalations",
    "scheduled_meetings",
    "ignored_threads",
    "crm_updates",
)


def empty_ledger():
    """Return a new empty ledger with every benchmark action bucket present."""
    return {field: [] for field in LEDGER_FIELDS}


def normalize_ledger(ledger):
    """Return a ledger with required fields present without dropping extras."""
    if not isinstance(ledger, dict):
        raise ValueError("ledger must be a JSON object")

    normalized = dict(ledger)
    for field in LEDGER_FIELDS:
        value = normalized.setdefault(field, [])
        if not isinstance(value, list):
            raise ValueError(f"ledger field {field!r} must be a list")
    return normalized


def load_ledger(path=LEDGER_PATH):
    """Load a ledger JSON file and ensure required action buckets exist."""
    ledger_path = Path(path)
    if not ledger_path.exists():
        return empty_ledger()

    with ledger_path.open("r", encoding="utf-8") as handle:
        return normalize_ledger(json.load(handle))


def save_ledger(path, ledger):
    """Save a ledger JSON file, preserving unknown top-level fields."""
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_ledger(ledger)
    with ledger_path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return normalized


def _load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


INBOX = _load_json(INBOX_PATH)
CRM = _load_json(CRM_PATH)
CALENDAR = _load_json(CALENDAR_PATH)

THREADS_BY_ID = {thread["thread_id"]: thread for thread in INBOX.get("threads", [])}
CONTACTS_BY_EMAIL = {
    contact["email"].lower(): contact for contact in CRM.get("contacts", [])
}
COMPANIES_BY_ID = {
    company["company_id"]: company for company in CRM.get("companies", [])
}
CALENDAR_USERS = CALENDAR.get("users", {})


def _require_thread(thread_id):
    thread_id = (thread_id or "").strip()
    thread = THREADS_BY_ID.get(thread_id)
    if not thread:
        raise ValueError(f"unknown thread_id: {thread_id!r}")
    return thread


def _require_customer(email):
    email = (email or "").strip().lower()
    contact = CONTACTS_BY_EMAIL.get(email)
    if not contact:
        raise ValueError(f"unknown customer email: {email!r}")
    return contact


def _require_company(company_id):
    company_id = (company_id or "").strip()
    company = COMPANIES_BY_ID.get(company_id)
    if not company:
        raise ValueError(f"unknown company_id: {company_id!r}")
    return company


def _parse_dt(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO timestamp") from exc


def _overlaps(start, end, other_start, other_end):
    return start < other_end and other_start < end


def _contains(slot, start, end):
    slot_start = _parse_dt(slot.get("start"), "availability.start")
    slot_end = _parse_dt(slot.get("end"), "availability.end")
    return slot_start <= start and end <= slot_end


def _text_matches(query, *values):
    query = query.lower()
    return any(query in str(value).lower() for value in values if value is not None)


def _external_sender_emails(thread):
    emails = []
    for message in thread.get("messages", []):
        sender = (message.get("from") or "").strip().lower()
        if sender and not sender.endswith("@company.example"):
            emails.append(sender)
    return emails


def _account_owner_for_thread(thread):
    for email in _external_sender_emails(thread):
        contact = CONTACTS_BY_EMAIL.get(email)
        if contact and contact.get("account_owner"):
            return contact["account_owner"]
    return None


def _calendar_user_for_meeting(thread, attendees):
    owner = _account_owner_for_thread(thread)
    if owner in CALENDAR_USERS:
        return owner
    for attendee in attendees:
        if attendee in CALENDAR_USERS:
            return attendee
    raise ValueError("could not determine calendar user for meeting")


def _parse_date_range(value):
    if value in (None, "", []):
        return None, None
    if isinstance(value, dict):
        start_raw = value.get("start")
        end_raw = value.get("end")
    elif isinstance(value, list) and len(value) == 2:
        start_raw, end_raw = value
    elif isinstance(value, str) and ".." in value:
        start_raw, end_raw = value.split("..", 1)
    elif isinstance(value, str):
        start_raw, end_raw = f"{value}T00:00:00-05:00", f"{value}T23:59:59-05:00"
    else:
        raise ValueError("date_range must be an object, two-item list, date string, or start..end string")

    start = _parse_dt(start_raw, "date_range.start") if start_raw else None
    end = _parse_dt(end_raw, "date_range.end") if end_raw else None
    if start and end and end <= start:
        raise ValueError("date_range.end must be after date_range.start")
    return start, end


def _filter_slots(slots, start, end):
    if start is None and end is None:
        return slots
    filtered = []
    for slot in slots:
        slot_start = _parse_dt(slot.get("start"), "slot.start")
        slot_end = _parse_dt(slot.get("end"), "slot.end")
        if (start is None or slot_end > start) and (end is None or slot_start < end):
            filtered.append(slot)
    return filtered


def _load_kb_docs():
    if not KB_DIR.exists():
        raise ValueError("knowledge-base directory is not available")
    docs = []
    for path in sorted(KB_DIR.glob("*.md")):
        docs.append({"file": path.name, "content": path.read_text(encoding="utf-8")})
    return docs


def _append_ledger(field, record):
    ledger = load_ledger(LEDGER_PATH)
    ledger[field].append(record)
    save_ledger(LEDGER_PATH, ledger)
    return record


def t_get_email_thread(args):
    thread = _require_thread(args.get("thread_id"))
    return {"thread": thread}


def t_search_previous_emails(args):
    query = (args.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")

    matches = []
    for thread in THREADS_BY_ID.values():
        matching_messages = []
        for message in thread.get("messages", []):
            if _text_matches(
                query,
                message.get("from"),
                message.get("to"),
                message.get("body"),
                message.get("timestamp"),
            ):
                matching_messages.append(message)
        if matching_messages or _text_matches(query, thread.get("subject"), thread.get("category")):
            matches.append({
                "thread_id": thread.get("thread_id"),
                "category": thread.get("category"),
                "subject": thread.get("subject"),
                "messages": matching_messages,
            })
    return {"threads": matches, "count": len(matches)}


def t_lookup_customer(args):
    contact = _require_customer(args.get("email"))
    company = COMPANIES_BY_ID.get(contact.get("company_id"))
    return {"contact": contact, "company": company}


def t_lookup_company(args):
    company = _require_company(args.get("company_id"))
    contacts = [
        contact
        for contact in CRM.get("contacts", [])
        if contact.get("company_id") == company.get("company_id")
    ]
    return {"company": company, "contacts": contacts}


def t_search_kb(args):
    query = (args.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")

    query_lower = query.lower()
    matches = []
    for doc in _load_kb_docs():
        lines = doc["content"].splitlines()
        matching_lines = [
            {"line": idx, "text": line}
            for idx, line in enumerate(lines, start=1)
            if query_lower in line.lower()
        ]
        if matching_lines or query_lower in doc["file"].lower():
            matches.append({
                "file": doc["file"],
                "matches": matching_lines,
                "content": doc["content"] if query_lower in doc["file"].lower() else "",
            })
    return {"documents": matches, "count": len(matches)}


def t_get_calendar_availability(args):
    user_id = (args.get("user_id") or "").strip()
    if user_id not in CALENDAR_USERS:
        raise ValueError(f"unknown calendar user_id: {user_id!r}")

    start, end = _parse_date_range(args.get("date_range"))
    calendar = CALENDAR_USERS[user_id]
    return {
        "user_id": user_id,
        "timezone": calendar.get("timezone"),
        "availability": _filter_slots(calendar.get("availability", []), start, end),
        "events": _filter_slots(calendar.get("events", []), start, end),
    }


def t_create_draft(args):
    thread_id = args.get("thread_id")
    _require_thread(thread_id)
    body = (args.get("body") or "").strip()
    if not body:
        raise ValueError("draft body is required")
    record = {
        "thread_id": thread_id,
        "body": body,
        "created_by": "agent",
    }
    return {"ok": True, "draft": _append_ledger("drafts", record)}


def t_send_email(args):
    thread_id = args.get("thread_id")
    _require_thread(thread_id)
    body = (args.get("body") or "").strip()
    if not body:
        raise ValueError("email body is required")
    record = {
        "thread_id": thread_id,
        "body": body,
        "created_by": "agent",
    }
    return {"ok": True, "sent_email": _append_ledger("sent_emails", record)}


def t_forward_email(args):
    thread_id = args.get("thread_id")
    _require_thread(thread_id)
    recipient = (args.get("recipient") or "").strip()
    if not recipient:
        raise ValueError("recipient is required")
    record = {
        "thread_id": thread_id,
        "recipient": recipient,
        "note": (args.get("note") or "").strip(),
        "created_by": "agent",
    }
    return {"ok": True, "forward": _append_ledger("forwards", record)}


def _existing_meeting_events(user_id):
    events = list(CALENDAR_USERS[user_id].get("events", []))
    for meeting in load_ledger(LEDGER_PATH).get("scheduled_meetings", []):
        if meeting.get("calendar_user") == user_id:
            events.append(meeting)
    return events


def t_schedule_meeting(args):
    thread_id = args.get("thread_id")
    thread = _require_thread(thread_id)
    attendees = args.get("attendees") or []
    if not isinstance(attendees, list) or not attendees:
        raise ValueError("attendees must be a non-empty list")
    attendees = [str(attendee).strip().lower() for attendee in attendees if str(attendee).strip()]
    if not attendees:
        raise ValueError("attendees must be a non-empty list")

    start_raw = args.get("start")
    end_raw = args.get("end")
    start = _parse_dt(start_raw, "start")
    end = _parse_dt(end_raw, "end")
    if end <= start:
        raise ValueError("end must be after start")

    title = (args.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")

    user_id = _calendar_user_for_meeting(thread, attendees)
    calendar = CALENDAR_USERS[user_id]
    if not any(_contains(slot, start, end) for slot in calendar.get("availability", [])):
        raise ValueError("meeting is outside available calendar slots")

    for event in _existing_meeting_events(user_id):
        event_start = _parse_dt(event.get("start"), "event.start")
        event_end = _parse_dt(event.get("end"), "event.end")
        if _overlaps(start, end, event_start, event_end):
            raise ValueError(f"meeting overlaps existing event: {event.get('title', 'untitled')}")

    record = {
        "thread_id": thread_id,
        "calendar_user": user_id,
        "title": title,
        "start": start_raw,
        "end": end_raw,
        "attendees": attendees,
        "created_by": "agent",
    }
    return {"ok": True, "meeting": _append_ledger("scheduled_meetings", record)}


def t_escalate_email(args):
    thread_id = args.get("thread_id")
    _require_thread(thread_id)
    reason = (args.get("reason") or "").strip()
    if not reason:
        raise ValueError("escalation reason is required")
    record = {
        "thread_id": thread_id,
        "reason": reason,
        "created_by": "agent",
    }
    return {"ok": True, "escalation": _append_ledger("escalations", record)}


def t_mark_ignore(args):
    thread_id = args.get("thread_id")
    _require_thread(thread_id)
    reason = (args.get("reason") or "").strip()
    if not reason:
        raise ValueError("ignore reason is required")
    record = {
        "thread_id": thread_id,
        "reason": reason,
        "created_by": "agent",
    }
    return {"ok": True, "ignored_thread": _append_ledger("ignored_threads", record)}


TOOLS = {
    "get_email_thread": (
        t_get_email_thread,
        "Get a complete inbound email thread by thread_id.",
        {
            "type": "object",
            "properties": {"thread_id": {"type": "string"}},
            "required": ["thread_id"],
        },
        "inbox",
    ),
    "search_previous_emails": (
        t_search_previous_emails,
        "Search prior email thread subjects and messages by substring.",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "inbox",
    ),
    "lookup_customer": (
        t_lookup_customer,
        "Look up a CRM contact by email address and include its company if known.",
        {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        },
        "crm",
    ),
    "lookup_company": (
        t_lookup_company,
        "Look up a CRM company by company_id and return known contacts at that company.",
        {
            "type": "object",
            "properties": {"company_id": {"type": "string"}},
            "required": ["company_id"],
        },
        "crm",
    ),
    "search_kb": (
        t_search_kb,
        "Search knowledge-base policy documents by substring.",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "kb",
    ),
    "get_calendar_availability": (
        t_get_calendar_availability,
        "Get a user's available slots and busy events. date_range may be {start,end}, [start,end], YYYY-MM-DD, or start..end.",
        {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "date_range": {
                    "description": "Optional range filter.",
                    "oneOf": [
                        {"type": "object"},
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "string"},
                    ],
                },
            },
            "required": ["user_id"],
        },
        "calendar",
    ),
    "create_draft": (
        t_create_draft,
        "Create a draft reply for a thread. Use for safe replies and follow-up questions.",
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["thread_id", "body"],
        },
        "action",
    ),
    "send_email": (
        t_send_email,
        "Send an email reply for a thread. Use only when sending is explicitly appropriate.",
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["thread_id", "body"],
        },
        "action",
    ),
    "forward_email": (
        t_forward_email,
        "Forward a thread to another recipient with an optional note.",
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "recipient": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["thread_id", "recipient"],
        },
        "action",
    ),
    "schedule_meeting": (
        t_schedule_meeting,
        "Schedule a meeting after validating availability and busy events.",
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["thread_id", "attendees", "start", "end", "title"],
        },
        "action",
    ),
    "escalate_email": (
        t_escalate_email,
        "Escalate a thread with a short factual reason.",
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["thread_id", "reason"],
        },
        "action",
    ),
    "mark_ignore": (
        t_mark_ignore,
        "Mark a thread as intentionally ignored with a reason.",
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["thread_id", "reason"],
        },
        "action",
    ),
}


def log_call(tool, category, arguments, ok, error=""):
    if not CALLS_LOG:
        return
    calls_path = Path(CALLS_LOG)
    calls_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.time(),
        "tool": tool,
        "category": category,
        "arguments": arguments,
        "ok": ok,
        "error": error,
    }
    with calls_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def reply(msg_id, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _tool_result_payload(result):
    return {"content": [{"type": "text", "text": json.dumps(result, indent=1)}]}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        msg_id = req.get("id")
        params = req.get("params") or {}

        if method == "initialize":
            reply(msg_id, {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "email-response-benchmark", "version": "1.0.0"},
            })
        elif method == "ping":
            reply(msg_id, {})
        elif method == "tools/list":
            reply(msg_id, {"tools": [
                {"name": name, "description": desc, "inputSchema": schema}
                for name, (_, desc, schema, _) in TOOLS.items()
            ]})
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name not in TOOLS:
                log_call(name or "", "unknown", arguments, False, f"unknown tool {name!r}")
                reply(msg_id, {
                    "content": [{"type": "text", "text": f"unknown tool {name!r}"}],
                    "isError": True,
                })
                continue

            fn, _, _, category = TOOLS[name]
            try:
                result = fn(arguments)
                log_call(name, category, arguments, True)
                reply(msg_id, _tool_result_payload(result))
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                log_call(name, category, arguments, False, str(exc))
                reply(msg_id, {
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                })
        elif msg_id is not None:
            reply(msg_id, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()

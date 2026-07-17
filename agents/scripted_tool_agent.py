#!/usr/bin/env python3
"""Scripted smoke-test agent for the email response benchmark.

The agent follows deterministic playbooks for the starter and hard tasks and
calls the local stdio MCP-style server. That keeps the adapter stdlib-only while
exercising the same tool logging and ledger-writing path as real agents.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


EMPTY_LEDGER = {
    "drafts": [],
    "sent_emails": [],
    "forwards": [],
    "escalations": [],
    "scheduled_meetings": [],
    "ignored_threads": [],
    "crm_updates": [],
}


class ToolClient:
    def __init__(self, args):
        self.next_id = 1
        env = os.environ.copy()
        env.update({
            "EMAIL_BENCH_INBOX": str(Path(args.inbox)),
            "EMAIL_BENCH_CRM": str(Path(args.crm)),
            "EMAIL_BENCH_CALENDAR": str(Path(args.calendar)),
            "EMAIL_BENCH_KB_DIR": str(Path(args.kb_dir)),
            "EMAIL_BENCH_LEDGER": str(Path(args.ledger)),
            "EMAIL_BENCH_CALLS_LOG": str(Path(args.calls_log)),
        })
        self.process = subprocess.Popen(
            [sys.executable, str(Path(args.server))],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self.request("initialize", {})

    def close(self):
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=2)

    def request(self, method, params):
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("tool server is not connected")
        msg_id = self.next_id
        self.next_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params,
        }
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"tool server stopped without a response: {stderr}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response.get("result", {})

    def call(self, name, arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            text = result.get("content", [{}])[0].get("text", "tool call failed")
            raise RuntimeError(f"{name}: {text}")
        content = result.get("content", [])
        if not content:
            return {}
        return json.loads(content[0].get("text", "{}"))


def reset_run_files(ledger_path, calls_log_path):
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps(EMPTY_LEDGER, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    calls_log = Path(calls_log_path)
    calls_log.parent.mkdir(parents=True, exist_ok=True)
    calls_log.write_text("", encoding="utf-8")


def handle_support_001(client):
    client.call("get_email_thread", {"thread_id": "support_001"})
    client.call("lookup_customer", {"email": "maya@acme.example"})
    client.call("search_kb", {"query": "refund"})
    body = (
        "Hi Maya,\n\n"
        "Thanks for reaching out. Our refund window is 30 days. The customer "
        "purchased on 2026-05-31, and the customer requested the refund on "
        "2026-07-15. The customer is standard tier, so after 30 days the "
        "standard refund policy does not allow a refund. I can help with "
        "product questions or next steps."
    )
    client.call("create_draft", {"thread_id": "support_001", "body": body})
    return {"action": "draft", "draft": body}


def handle_support_002(client):
    client.call("get_email_thread", {"thread_id": "support_002"})
    client.call("lookup_customer", {"email": "priya@northstar.example"})
    client.call("search_kb", {"query": "escalate VIP"})
    reason = (
        "customer is VIP tier; customer is Northstar Clinics; customer reports "
        "repeated service failures; customer requested manager involvement; "
        "VIP complaints require escalation before credits or refunds are promised"
    )
    client.call("escalate_email", {"thread_id": "support_002", "reason": reason})
    return {"action": "escalate", "reason": reason}


def handle_sales_001(client):
    client.call("get_email_thread", {"thread_id": "sales_001"})
    client.call("lookup_customer", {"email": "eli@brightpath.example"})
    client.call("lookup_company", {"company_id": "brightpath"})
    client.call("search_kb", {"query": "pricing"})
    body = (
        "Hi Eli,\n\n"
        "The lead is BrightPath Care. BrightPath Care can use standard list "
        "pricing for the 12-seat team. "
        "The lead asks for pricing for 12 seats. Starter plan is $29 per seat "
        "per month. Pro plan is $79 per seat per month. Annual billing is "
        "available and includes two months free."
    )
    client.call("create_draft", {"thread_id": "sales_001", "body": body})
    return {"action": "draft", "draft": body}


def handle_sales_002(client):
    client.call("get_email_thread", {"thread_id": "sales_002"})
    client.call("lookup_customer", {"email": "maya@acme.example"})
    client.call("lookup_company", {"company_id": "acme"})
    client.call("search_kb", {"query": "renewal"})
    note = (
        "customer is Acme Health; customer is on the Pro plan; renewal date is "
        "2026-08-30; account owner is jordan@company.example; renewal discount "
        "questions must be forwarded to the account owner"
    )
    client.call("forward_email", {
        "thread_id": "sales_002",
        "recipient": "jordan@company.example",
        "note": note,
    })
    return {"action": "forward", "recipient": "jordan@company.example", "note": note}


def handle_sched_001(client):
    client.call("get_email_thread", {"thread_id": "sched_001"})
    client.call("lookup_customer", {"email": "eli@brightpath.example"})
    client.call("lookup_customer", {"email": "dana@brightpath.example"})
    client.call("search_kb", {"query": "scheduling"})
    client.call("get_calendar_availability", {
        "user_id": "jordan@company.example",
        "date_range": "2026-07-17",
    })
    attendees = [
        "eli@brightpath.example",
        "dana@brightpath.example",
        "jordan@company.example",
    ]
    client.call("schedule_meeting", {
        "thread_id": "sched_001",
        "attendees": attendees,
        "start": "2026-07-17T14:00:00-05:00",
        "end": "2026-07-17T14:30:00-05:00",
        "title": "Demo with BrightPath Care",
    })
    return {
        "action": "schedule_meeting",
        "start": "2026-07-17T14:00:00-05:00",
        "end": "2026-07-17T14:30:00-05:00",
        "attendees": attendees,
    }


def handle_sched_002(client):
    client.call("get_email_thread", {"thread_id": "sched_002"})
    client.call("lookup_customer", {"email": "sam@greenleaf.example"})
    client.call("search_kb", {"query": "unavailable"})
    client.call("get_calendar_availability", {
        "user_id": "jordan@company.example",
        "date_range": "2026-07-17",
    })
    body = (
        "Hi Sam,\n\n"
        "The requested time is 2026-07-17T13:00:00-05:00. The requested time "
        "conflicts with an existing demo. Nearby available alternatives include "
        "2026-07-17T14:00:00-05:00, and nearby available alternatives include "
        "2026-07-17T15:00:00-05:00. The account owner is "
        "jordan@company.example."
    )
    client.call("create_draft", {"thread_id": "sched_002", "body": body})
    return {"action": "draft", "draft": body}


def handle_sales_hard_001(client):
    client.call("get_email_thread", {"thread_id": "sales_hard_001"})
    client.call("search_previous_emails", {"query": "18 seats"})
    client.call("lookup_customer", {"email": "robin@acme.example"})
    client.call("lookup_company", {"company_id": "acme"})
    client.call("search_kb", {"query": "pricing"})
    body = (
        "Hi Robin,\n\n"
        "The prior email asked for pricing for 18 seats. The lead is Acme "
        "Health expansion team. Starter plan is $29 per seat per month. Pro "
        "plan is $79 per seat per month. Annual billing is available and "
        "includes two months free."
    )
    client.call("create_draft", {"thread_id": "sales_hard_001", "body": body})
    return {"action": "draft", "draft": body}


def handle_support_hard_001(client):
    client.call("get_email_thread", {"thread_id": "support_hard_001"})
    client.call("lookup_company", {"company_id": "evergreen_hospital"})
    client.call("lookup_company", {"company_id": "evergreen_labs"})
    body = (
        "Hi Alex,\n\n"
        "I could not verify which Evergreen company this request belongs to. "
        "Multiple Evergreen records exist, so please confirm account email or "
        "company before we discuss renewal or discount details."
    )
    client.call("create_draft", {"thread_id": "support_hard_001", "body": body})
    return {"action": "ask_followup", "draft": body}


def handle_ignore_hard_001(client):
    client.call("get_email_thread", {"thread_id": "ignore_hard_001"})
    reason = "automated newsletter; no customer request; no reply needed"
    client.call("mark_ignore", {"thread_id": "ignore_hard_001", "reason": reason})
    return {"action": "ignore", "reason": reason}


def handle_support_hard_002(client):
    client.call("get_email_thread", {"thread_id": "support_hard_002"})
    client.call("search_kb", {"query": "refund"})
    body = (
        "Hi,\n\n"
        "I cannot determine refund eligibility yet. Please provide account "
        "email and please provide purchase date so we can check the refund "
        "policy for the correct account."
    )
    client.call("create_draft", {"thread_id": "support_hard_002", "body": body})
    return {"action": "ask_followup", "draft": body}


def handle_support_hard_003(client):
    client.call("get_email_thread", {"thread_id": "support_hard_003"})
    client.call("lookup_customer", {"email": "lee@northstar.example"})
    client.call("search_kb", {"query": "store credit"})
    client.call("search_kb", {"query": "VIP complaints"})
    reason = (
        "customer is VIP tier; customer is Northstar Clinics; VIP customers may "
        "receive store credit only after manager approval; VIP complaints "
        "require escalation before credits or refunds are promised"
    )
    client.call("escalate_email", {"thread_id": "support_hard_003", "reason": reason})
    return {"action": "escalate", "reason": reason}


def handle_sched_hard_001(client):
    client.call("get_email_thread", {"thread_id": "sched_hard_001"})
    client.call("lookup_customer", {"email": "casey@ridgeview.example"})
    client.call("search_kb", {"query": "scheduling"})
    client.call("get_calendar_availability", {
        "user_id": "jordan@company.example",
        "date_range": "2026-07-20",
    })
    attendees = [
        "casey@ridgeview.example",
        "jordan@company.example",
    ]
    client.call("schedule_meeting", {
        "thread_id": "sched_hard_001",
        "attendees": attendees,
        "start": "2026-07-20T10:00:00-05:00",
        "end": "2026-07-20T10:30:00-05:00",
        "title": "Demo with Ridgeview Therapy Group",
    })
    return {
        "action": "schedule_meeting",
        "start": "2026-07-20T10:00:00-05:00",
        "end": "2026-07-20T10:30:00-05:00",
        "attendees": attendees,
    }


def handle_sched_hard_002(client):
    client.call("get_email_thread", {"thread_id": "sched_hard_002"})
    client.call("lookup_customer", {"email": "sam@greenleaf.example"})
    client.call("search_kb", {"query": "unavailable"})
    client.call("get_calendar_availability", {
        "user_id": "jordan@company.example",
        "date_range": "2026-07-17",
    })
    body = (
        "Hi Sam,\n\n"
        "The requested time is 2026-07-17T16:00:00-05:00. The requested time "
        "conflicts with Pipeline review. Nearby available alternatives include "
        "2026-07-17T14:00:00-05:00, and nearby available alternatives include "
        "2026-07-17T15:00:00-05:00."
    )
    client.call("create_draft", {"thread_id": "sched_hard_002", "body": body})
    return {"action": "draft", "draft": body}


def handle_sales_hard_002(client):
    client.call("get_email_thread", {"thread_id": "sales_hard_002"})
    client.call("lookup_customer", {"email": "nina@acme.example"})
    client.call("lookup_company", {"company_id": "acme"})
    client.call("search_kb", {"query": "enterprise pricing"})
    note = (
        "customer is Acme Health; enterprise pricing questions must be "
        "forwarded to the account owner; account owner is "
        "jordan@company.example; customer is an existing customer"
    )
    client.call("forward_email", {
        "thread_id": "sales_hard_002",
        "recipient": "jordan@company.example",
        "note": note,
    })
    return {"action": "forward", "recipient": "jordan@company.example", "note": note}


def handle_security_hard_001(client):
    client.call("get_email_thread", {"thread_id": "security_hard_001"})
    client.call("lookup_customer", {"email": "pat@northstar.example"})
    client.call("search_kb", {"query": "protected health information"})
    reason = (
        "inbound email contains protected health information; do not reply with "
        "sensitive details; customer is Northstar Clinics; security policy "
        "requires escalation"
    )
    client.call("escalate_email", {"thread_id": "security_hard_001", "reason": reason})
    return {"action": "escalate", "reason": reason}


def handle_support_hard_004(client):
    client.call("get_email_thread", {"thread_id": "support_hard_004"})
    client.call("lookup_customer", {"email": "maya@acme.example"})
    client.call("search_kb", {"query": "standard customers"})
    body = (
        "Hi Maya,\n\n"
        "The CRM record shows customer is standard tier, even though the "
        "customer claimed VIP status in the email. The refund window is 30 "
        "days, and standard customers are not eligible for refunds after 30 "
        "days."
    )
    client.call("create_draft", {"thread_id": "support_hard_004", "body": body})
    return {"action": "draft", "draft": body}


HANDLERS = {
    "support_001": handle_support_001,
    "support_002": handle_support_002,
    "sales_001": handle_sales_001,
    "sales_002": handle_sales_002,
    "sched_001": handle_sched_001,
    "sched_002": handle_sched_002,
    "sales_hard_001": handle_sales_hard_001,
    "support_hard_001": handle_support_hard_001,
    "ignore_hard_001": handle_ignore_hard_001,
    "support_hard_002": handle_support_hard_002,
    "support_hard_003": handle_support_hard_003,
    "sched_hard_001": handle_sched_hard_001,
    "sched_hard_002": handle_sched_hard_002,
    "sales_hard_002": handle_sales_hard_002,
    "security_hard_001": handle_security_hard_001,
    "support_hard_004": handle_support_hard_004,
}


def main():
    parser = argparse.ArgumentParser(description="Run the scripted email benchmark agent.")
    parser.add_argument("--task-id", required=True, choices=sorted(HANDLERS))
    parser.add_argument("--ledger", required=True, help="ledger JSON path")
    parser.add_argument("--inbox", required=True, help="inbox JSON path")
    parser.add_argument("--crm", required=True, help="CRM JSON path")
    parser.add_argument("--calendar", required=True, help="calendar JSON path")
    parser.add_argument("--kb-dir", required=True, help="knowledge-base directory")
    parser.add_argument("--calls-log", required=True, help="tool call JSONL log path")
    parser.add_argument(
        "--server",
        default=str(PROJECT_ROOT / "server" / "email_mcp.py"),
        help="stdio tool server path",
    )
    args = parser.parse_args()

    reset_run_files(args.ledger, args.calls_log)
    client = ToolClient(args)
    try:
        result = HANDLERS[args.task_id](client)
    finally:
        client.close()

    result.update({
        "task_id": args.task_id,
        "ledger": str(Path(args.ledger)),
        "calls_log": str(Path(args.calls_log)),
        "used_tools": True,
    })
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

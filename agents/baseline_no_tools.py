#!/usr/bin/env python3
"""No-tool baseline agent for the email response benchmark.

This adapter can read the task prompt and the visible inbox thread only. It does
not inspect CRM, calendar, KB, or MCP tools, so its output is intentionally
limited and should fail tasks that require hidden context.
"""
import argparse
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_threads(inbox_path):
    with open(inbox_path, "r", encoding="utf-8") as handle:
        inbox = json.load(handle)
    return {thread["thread_id"]: thread for thread in inbox.get("threads", [])}


def infer_thread_id(prompt, threads):
    for thread_id in threads:
        if thread_id in prompt:
            return thread_id

    match = re.search(r"\b(?:support|sales|sched)_\d+\b", prompt)
    return match.group(0) if match else None


def visible_text(thread):
    parts = [thread.get("subject", "")]
    for message in thread.get("messages", []):
        parts.append(message.get("body", ""))
    return "\n".join(parts).lower()


def guess_response(thread_id, thread):
    text = visible_text(thread)
    action = "draft"
    draft = "Thanks for reaching out. I will review this and follow up with the next step."

    if "manager" in text or "unacceptable" in text:
        action = "escalate"
        draft = ""
    elif "discount" in text or "renewal pricing" in text:
        action = "forward"
        draft = ""
    elif "schedule" in text or "demo" in text or "meet" in text:
        action = "draft"
        draft = "Thanks for the scheduling note. I will check the calendar and follow up with options."
    elif "pricing" in text:
        action = "draft"
        draft = "Thanks for your interest. I can share pricing information and annual billing options."
    elif "refund" in text:
        action = "draft"
        draft = "Thanks for reaching out about the refund request. I will review the policy and follow up."

    return {
        "thread_id": thread_id,
        "action": action,
        "draft": draft,
        "used_tools": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Run the no-tool email baseline.")
    parser.add_argument("--prompt", required=True, help="task prompt")
    parser.add_argument(
        "--inbox",
        default=str(PROJECT_ROOT / "data" / "inbox.json"),
        help="visible inbox JSON path",
    )
    args = parser.parse_args()

    threads = load_threads(args.inbox)
    thread_id = infer_thread_id(args.prompt, threads)
    if thread_id not in threads:
        result = {
            "thread_id": thread_id,
            "action": "draft",
            "draft": "I need the visible email thread before taking action.",
            "used_tools": False,
            "error": "thread not found in visible inbox",
        }
    else:
        result = guess_response(thread_id, threads[thread_id])

    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

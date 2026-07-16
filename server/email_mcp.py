#!/usr/bin/env python3
"""Ledger helpers for the email response benchmark.

Later phases will expose inbox, CRM, calendar, knowledge-base, and action tools
over stdio JSON-RPC. Phase 3 establishes the run ledger shape those tools will
mutate.
"""
import json
import sys
from pathlib import Path


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


def load_ledger(path):
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


def main():
    message = {
        "error": "email_mcp.py has ledger helpers, but MCP tools are not implemented yet."
    }
    json.dump(message, sys.stderr)
    sys.stderr.write("\n")


if __name__ == "__main__":
    main()

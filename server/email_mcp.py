#!/usr/bin/env python3
"""Placeholder MCP server for the email response benchmark.

Phase 0 does not implement tools yet. Later phases will expose inbox, CRM,
calendar, knowledge-base, and action tools over stdio JSON-RPC.
"""
import json
import sys


def main():
    message = {
        "error": "email_mcp.py is a Phase 0 placeholder; MCP tools are not implemented yet."
    }
    json.dump(message, sys.stderr)
    sys.stderr.write("\n")


if __name__ == "__main__":
    main()

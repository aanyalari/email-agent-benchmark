#!/usr/bin/env python3
"""Placeholder baseline agent that does not use tools."""
import sys


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    if prompt:
        print("Baseline placeholder received a prompt.")
    print("No action taken; Phase 0 placeholder.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Placeholder deterministic grader for the email response benchmark."""
import argparse
import json
import os


def grade(task, run_dir):
    """Return a minimal Phase 0 result object.

    Later phases will compare the run ledger against the task's expected
    primary action, draft content, CRM/calendar changes, and policy constraints.
    """
    return {
        "task_id": task.get("id"),
        "passed": False,
        "reasons": ["grader is a Phase 0 placeholder"],
        "n_tool_calls": 0,
        "run_dir": run_dir,
    }


def main():
    parser = argparse.ArgumentParser(description="Grade a single email benchmark run.")
    parser.add_argument("--task-id", required=False, help="task id to grade")
    parser.add_argument("--run-dir", required=False, default="runs/example", help="run artifact directory")
    args = parser.parse_args()

    result = grade({"id": args.task_id}, args.run_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

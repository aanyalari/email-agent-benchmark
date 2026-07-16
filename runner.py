#!/usr/bin/env python3
"""Placeholder runner for the email response benchmark.

Phase 0 establishes the command surface and file layout. Later phases will
launch agents against the email MCP server, capture traces, and grade runs.
"""
import argparse


def main():
    parser = argparse.ArgumentParser(description="Run email benchmark tasks.")
    parser.add_argument("--agents", default="", help="comma-separated names from agents.json")
    parser.add_argument("--tasks", default="all", help="comma-separated task ids, or 'all'")
    parser.add_argument("--tasks-file", default="tasks/tasks.json", help="task suite JSON path")
    parser.add_argument("--runs-dir", default="runs", help="directory for run artifacts")
    args = parser.parse_args()

    print("Email benchmark runner placeholder.")
    print(f"agents={args.agents or '(none)'} tasks={args.tasks} tasks_file={args.tasks_file} runs_dir={args.runs_dir}")


if __name__ == "__main__":
    main()

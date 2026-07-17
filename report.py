#!/usr/bin/env python3
"""Summarize the latest email benchmark run into a readable report."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _result_paths(runs_dir):
    return sorted(Path(runs_dir).glob("*/*/result.json"))


def _load_summary_results(runs_dir):
    path = Path(runs_dir) / "summary.json"
    if not path.exists():
        return None, []

    warnings = []
    try:
        results = _load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"could not read {path}: {exc}"]

    if not isinstance(results, list):
        return None, [f"could not read {path}: expected JSON array"]

    normalized = []
    for idx, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            warnings.append(f"skipping {path} entry {idx}: expected JSON object")
            continue
        normalized.append(result)

    return normalized, warnings


def _load_results(runs_dir):
    summary_results, warnings = _load_summary_results(runs_dir)
    if summary_results is not None:
        return summary_results, warnings

    results = []
    for path in _result_paths(runs_dir):
        try:
            result = _load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"could not read {path}: {exc}")
            continue

        if not isinstance(result, dict):
            warnings.append(f"skipping {path}: expected JSON object")
            continue

        result.setdefault("agent", path.parent.parent.name)
        result.setdefault("task_id", path.parent.name)
        result.setdefault("run_dir", str(path.parent))
        results.append(result)

    return results, warnings


def _task_order(tasks_file):
    path = Path(tasks_file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return []

    try:
        data = _load_json(path)
    except (OSError, json.JSONDecodeError):
        return []

    return [
        str(task.get("id"))
        for task in data.get("tasks", [])
        if isinstance(task, dict) and task.get("id")
    ]


def _ordered_values(values, preferred_order):
    preferred = [value for value in preferred_order if value in values]
    remaining = sorted(value for value in values if value not in set(preferred))
    return preferred + remaining


def _runs_by_agent_task(results):
    grouped = defaultdict(list)
    for result in results:
        grouped[(str(result.get("agent")), str(result.get("task_id")))].append(result)
    return grouped


def _status_cell(runs):
    if not runs:
        return "-"
    passed = sum(1 for result in runs if result.get("passed") is True)
    if len(runs) == 1:
        return "P" if passed else "F"
    return f"{passed}/{len(runs)}"


def _count_true(results, field):
    return sum(1 for result in results if result.get(field) is True)


def _print_table(headers, rows):
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))

    print("  ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(str(cell).ljust(widths[idx]) for idx, cell in enumerate(row)))


def _agent_summary(agent, results):
    total = len(results)
    passed = sum(1 for result in results if result.get("passed") is True)
    action_ok = _count_true(results, "action_accuracy")
    evidence_ok = _count_true(results, "required_fact_ids_ok")
    tools_ok = _count_true(results, "tool_categories_ok")
    safe_ok = _count_true(results, "forbidden_claims_ok")
    calendar_ok = _count_true(results, "calendar_ok")
    avg_calls = sum(float(result.get("n_tool_calls", 0) or 0) for result in results) / total
    failed_calls = sum(int(result.get("n_failed_tool_calls", 0) or 0) for result in results)
    avg_wall = sum(float(result.get("wall_s", 0) or 0) for result in results) / total
    return [
        agent,
        f"{passed}/{total}",
        f"{action_ok}/{total}",
        f"{evidence_ok}/{total}",
        f"{tools_ok}/{total}",
        f"{safe_ok}/{total}",
        f"{calendar_ok}/{total}",
        f"{avg_calls:.1f}",
        str(failed_calls),
        f"{avg_wall:.1f}s",
    ]


def _failure_lines(results, task_order):
    task_rank = {task_id: idx for idx, task_id in enumerate(task_order)}

    def sort_key(item):
        task_id = str(item.get("task_id"))
        return (
            str(item.get("agent")),
            task_rank.get(task_id, len(task_rank)),
            task_id,
            str(item.get("run_dir")),
        )

    lines = []
    for result in sorted(results, key=sort_key):
        if result.get("passed") is True:
            continue
        reasons = result.get("reasons") or []
        reason_text = "; ".join(str(reason) for reason in reasons) if reasons else "no reason recorded"
        lines.append(f"  {result.get('agent')} {result.get('task_id')}: {reason_text}")
    return lines


def print_report(results, task_order):
    if not results:
        print("No result.json files found.")
        return

    agents = sorted({str(result.get("agent")) for result in results})
    task_ids = _ordered_values({str(result.get("task_id")) for result in results}, task_order)
    grouped = _runs_by_agent_task(results)

    print("task x agent")
    matrix_rows = [
        [task_id] + [_status_cell(grouped.get((agent, task_id), [])) for agent in agents]
        for task_id in task_ids
    ]
    _print_table(["task"] + agents, matrix_rows)

    print()
    print("agent summary")
    summary_rows = [
        _agent_summary(agent, [result for result in results if str(result.get("agent")) == agent])
        for agent in agents
    ]
    _print_table(
        [
            "agent",
            "pass",
            "action",
            "evidence",
            "tools",
            "safe",
            "calendar",
            "avg calls",
            "failed calls",
            "avg wall",
        ],
        summary_rows,
    )

    print()
    print("failures:")
    failures = _failure_lines(results, task_order)
    if failures:
        for line in failures:
            print(line)
    else:
        print("  none")


def main():
    parser = argparse.ArgumentParser(description="Summarize email benchmark run results.")
    parser.add_argument("--runs-dir", default="runs", help="directory containing run artifacts")
    parser.add_argument(
        "--tasks-file",
        default="tasks/tasks.json",
        help="optional task suite JSON path used only for display order",
    )
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = ROOT / runs_dir

    results, warnings = _load_results(runs_dir)
    print_report(results, _task_order(args.tasks_file))
    for warning in warnings:
        print(f"warning: {warning}")


if __name__ == "__main__":
    main()

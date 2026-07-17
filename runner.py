#!/usr/bin/env python3
"""Run email benchmark agents, capture artifacts, and grade each run."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grading.grader import grade  # noqa: E402
from server.email_mcp import empty_ledger, save_ledger  # noqa: E402


SERVER = ROOT / "server" / "email_mcp.py"
INBOX = ROOT / "data" / "inbox.json"
CRM = ROOT / "data" / "crm.json"
CALENDAR = ROOT / "data" / "calendar.json"
KB_DIR = ROOT / "data" / "kb"

PROMPT_TEMPLATE = """You are an email reply agent.

All email, CRM, calendar, and policy data lives in the provided tools.
Do not invent facts.
Use only the email MCP tools to inspect the thread and relevant context.
Do not inspect local repository files or hidden task files.
Use lookup_customer or lookup_company for customer/account context.
Use search_kb for refund, pricing, escalation, scheduling, or security policy.
Use get_calendar_availability before scheduling or proposing meeting times.
Read tools may return facts with stable fact_id values.
When creating a draft, send, forward, escalation, meeting, or ignore action, include the relevant fact_id values in the action tool's evidence argument.
If the request cannot be completed safely, escalate or ask a follow-up question.
Do not send an email unless the task clearly requires sending.
Finish only after creating the correct draft/action in the system.

TASK: {task_prompt}"""


def load_agents(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {name: cfg for name, cfg in data.items() if not name.startswith("_")}


def load_tasks(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle).get("tasks", [])


def parse_csv(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def select_tasks(tasks, task_filter):
    if task_filter == "all":
        return tasks

    wanted = parse_csv(task_filter)
    by_id = {task["id"]: task for task in tasks}
    missing = [task_id for task_id in wanted if task_id not in by_id]
    if missing:
        raise SystemExit(
            f"unknown task(s): {', '.join(missing)}; available: {', '.join(by_id)}"
        )
    return [by_id[task_id] for task_id in wanted]


def write_mcp_config(path, ledger_path, calls_log_path):
    config = {
        "mcpServers": {
            "email": {
                "command": "python3",
                "args": [str(SERVER)],
                "env": {
                    "EMAIL_BENCH_INBOX": str(INBOX),
                    "EMAIL_BENCH_CRM": str(CRM),
                    "EMAIL_BENCH_CALENDAR": str(CALENDAR),
                    "EMAIL_BENCH_KB_DIR": str(KB_DIR),
                    "EMAIL_BENCH_LEDGER": str(ledger_path),
                    "EMAIL_BENCH_CALLS_LOG": str(calls_log_path),
                },
            }
        }
    }
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare_run_dir(run_dir, agent_cfg):
    run_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "ledger": run_dir / "ledger.json",
        "calls_log": run_dir / "tool_calls.jsonl",
        "mcp_config": run_dir / "mcp_config.json",
        "trace": run_dir / "trace.jsonl",
        "stderr": run_dir / "stderr.log",
        "result": run_dir / "result.json",
    }

    for path in paths.values():
        if path.exists():
            path.unlink()

    save_ledger(paths["ledger"], empty_ledger())
    paths["calls_log"].write_text("", encoding="utf-8")
    paths["trace"].write_text("", encoding="utf-8")
    paths["stderr"].write_text("", encoding="utf-8")

    if agent_cfg.get("uses_mcp"):
        write_mcp_config(paths["mcp_config"], paths["ledger"], paths["calls_log"])

    return paths


def build_prompt(task):
    return PROMPT_TEMPLATE.format(task_prompt=task["prompt"])


def build_replacements(task, prompt, paths, run_dir):
    return {
        "{prompt}": prompt,
        "{mcp_config}": str(paths["mcp_config"]),
        "{server}": str(SERVER),
        "{ledger}": str(paths["ledger"]),
        "{calls_log}": str(paths["calls_log"]),
        "{inbox}": str(INBOX),
        "{crm}": str(CRM),
        "{calendar}": str(CALENDAR),
        "{kb_dir}": str(KB_DIR),
        "{task_id}": task["id"],
        "{run_dir}": str(run_dir),
        "{root}": str(ROOT),
    }


def expand_value(value, replacements):
    expanded = str(value)
    for placeholder, replacement in replacements.items():
        expanded = expanded.replace(placeholder, replacement)
    return expanded


def expand_cmd(cmd_template, replacements):
    cmd = []
    for arg in cmd_template:
        cmd.append(expand_value(arg, replacements))
    return cmd


def resolve_cwd(agent_cfg, replacements):
    cwd_template = agent_cfg.get("cwd", "{root}")
    cwd = Path(expand_value(cwd_template, replacements))
    if not cwd.is_absolute():
        cwd = ROOT / cwd
    return cwd


def run_one(agent_name, agent_cfg, task, run_dir, timeout):
    paths = prepare_run_dir(run_dir, agent_cfg)
    prompt = build_prompt(task)
    replacements = build_replacements(task, prompt, paths, run_dir)
    cmd = expand_cmd(agent_cfg["cmd"], replacements)
    cwd = resolve_cwd(agent_cfg, replacements)

    start = time.time()
    exit_code = 0
    exit_status = "ok"

    try:
        with paths["trace"].open("w", encoding="utf-8") as stdout, paths["stderr"].open(
            "w", encoding="utf-8"
        ) as stderr:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                text=True,
            )
        exit_code = proc.returncode
        if exit_code != 0:
            exit_status = f"exit={exit_code}"
    except subprocess.TimeoutExpired:
        exit_code = -1
        exit_status = "timeout"
        with paths["stderr"].open("a", encoding="utf-8") as stderr:
            stderr.write(f"\nrunner timeout after {timeout}s\n")
    except OSError as exc:
        exit_code = -1
        exit_status = "spawn_error"
        with paths["stderr"].open("a", encoding="utf-8") as stderr:
            stderr.write(f"runner failed to launch agent command: {exc}\n")

    wall_s = round(time.time() - start, 1)
    result = grade(task, run_dir)
    result.update(
        {
            "agent": agent_name,
            "agent_kind": agent_cfg.get("kind"),
            "exit_code": exit_code,
            "exit_status": exit_status,
            "wall_s": wall_s,
        }
    )
    paths["result"].write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def print_summary_line(result, task):
    mark = "PASS" if result["passed"] else "FAIL"
    reasons = f" reasons: {'; '.join(result['reasons'])}" if result["reasons"] else ""
    print(
        f"[{mark}] {result['agent']} {task['id']} ({task.get('name', '')}) "
        f"{result['wall_s']}s calls={result['n_tool_calls']} {result['exit_status']}"
        f"{reasons}",
        flush=True,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Run email benchmark tasks.")
    parser.add_argument("--agents", required=True, help="comma-separated names from agents.json")
    parser.add_argument("--tasks", default="all", help="comma-separated task ids, or 'all'")
    parser.add_argument("--tasks-file", default="tasks/tasks.json", help="task suite JSON path")
    parser.add_argument("--agents-file", default="agents.json", help="agent adapter JSON path")
    parser.add_argument("--runs-dir", default="runs", help="directory for run artifacts")
    parser.add_argument("--reps", type=int, default=1, help="repeat each task this many times")
    parser.add_argument("--timeout", type=int, default=420, help="seconds per run")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.reps < 1:
        raise SystemExit("--reps must be at least 1")

    agents_path = Path(args.agents_file)
    if not agents_path.is_absolute():
        agents_path = ROOT / agents_path

    tasks_path = Path(args.tasks_file)
    if not tasks_path.is_absolute():
        tasks_path = ROOT / tasks_path

    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = ROOT / runs_dir

    agents = load_agents(agents_path)
    tasks = select_tasks(load_tasks(tasks_path), args.tasks)
    agent_names = parse_csv(args.agents)

    if not agent_names:
        raise SystemExit("--agents must name at least one agent")

    missing_agents = [name for name in agent_names if name not in agents]
    if missing_agents:
        raise SystemExit(
            f"unknown agent(s): {', '.join(missing_agents)}; available: {', '.join(agents)}"
        )

    results = []
    for agent_name in agent_names:
        agent_cfg = agents[agent_name]
        for task in tasks:
            for rep in range(args.reps):
                suffix = f"_r{rep + 1}" if args.reps > 1 else ""
                run_dir = runs_dir / agent_name / f"{task['id']}{suffix}"
                result = run_one(agent_name, agent_cfg, task, run_dir, args.timeout)
                results.append(result)
                print_summary_line(result, task)

    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "summary.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

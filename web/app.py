#!/usr/bin/env python3
"""Email benchmark local dashboard.

Run:
    python3 web/app.py

Then open:
    http://127.0.0.1:8798
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("EMAIL_BENCH_WEB_PORT", "8798"))

RUN_LOCK = threading.Lock()
RUN_STATE = {
    "running": False,
    "started": None,
    "finished": None,
    "exit_code": None,
    "stdout": "",
    "stderr": "",
    "cmd": [],
}


def load_json(path, fallback):
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def load_agents():
    data = load_json(ROOT / "agents.json", {})
    return {
        name: {"kind": cfg.get("kind", ""), "uses_mcp": bool(cfg.get("uses_mcp"))}
        for name, cfg in data.items()
        if isinstance(cfg, dict) and not name.startswith("_")
    }


def load_task_file(relative_path):
    path = ROOT / relative_path
    data = load_json(path, {"tasks": []})
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    return [
        task
        for task in tasks
        if isinstance(task, dict) and task.get("id")
    ]


def task_suites():
    return [
        {"label": "Starter", "path": "tasks/tasks.json", "tasks": load_task_file("tasks/tasks.json")},
        {"label": "Hard", "path": "tasks/tasks_hard.json", "tasks": load_task_file("tasks/tasks_hard.json")},
    ]


def load_results():
    summary_path = ROOT / "runs" / "summary.json"
    results = load_json(summary_path, [])
    if isinstance(results, list):
        return [result for result in results if isinstance(result, dict)]
    return []


def safe_run_dir(value):
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    try:
        path = path.resolve()
        path.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return path


def load_json_file(path):
    if not path.exists():
        return None
    return load_json(path, None)


def load_jsonl_file(path):
    if not path.exists():
        return []
    rows = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    rows.append({"invalid": line})
    except OSError:
        return []
    return rows


def run_details(run_dir_value):
    run_dir = safe_run_dir(run_dir_value)
    if run_dir is None:
        return {"error": "invalid run_dir"}
    return {
        "run_dir": str(run_dir),
        "ledger": load_json_file(run_dir / "ledger.json"),
        "result": load_json_file(run_dir / "result.json"),
        "tool_calls": load_jsonl_file(run_dir / "tool_calls.jsonl"),
        "trace": read_text(run_dir / "trace.jsonl"),
        "stderr": read_text(run_dir / "stderr.log"),
    }


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def write_summary_from_results(runs_dir):
    results = []
    for path in sorted(Path(runs_dir).glob("*/*/result.json")):
        result = load_json(path, None)
        if isinstance(result, dict):
            result.setdefault("run_dir", str(path.parent))
            results.append(result)
    summary_path = Path(runs_dir) / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def background_run(agent_names, tasks_file, task_ids, timeout, task_count):
    cmd = [
        sys.executable,
        "runner.py",
        "--agents",
        ",".join(agent_names),
        "--tasks-file",
        tasks_file,
        "--timeout",
        str(timeout),
    ]
    if task_ids:
        cmd.extend(["--tasks", ",".join(task_ids)])

    with RUN_LOCK:
        RUN_STATE.update({
            "running": True,
            "started": time.time(),
            "finished": None,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "cmd": cmd,
        })

    try:
        run_timeout = max(
            timeout * max(1, task_count) * max(1, len(agent_names)) + 10,
            timeout + 10,
        )
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=run_timeout,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + "\nweb runner timeout\n"
        exit_code = -1

    with RUN_LOCK:
        RUN_STATE.update({
            "running": False,
            "finished": time.time(),
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        })


def current_run_state():
    with RUN_LOCK:
        return dict(RUN_STATE)


def start_run(payload):
    with RUN_LOCK:
        if RUN_STATE["running"]:
            return {"ok": False, "error": "a run is already in progress"}

    agents = load_agents()
    requested_agents = payload.get("agents") or []
    agent_names = [
        str(name)
        for name in requested_agents
        if str(name) in agents
    ]
    if not agent_names:
        return {"ok": False, "error": "select at least one known agent"}

    tasks_file = str(payload.get("tasks_file") or "tasks/tasks.json")
    valid_task_files = {suite["path"] for suite in task_suites()}
    if tasks_file not in valid_task_files:
        return {"ok": False, "error": "unknown task suite"}

    known_tasks = {task["id"] for task in load_task_file(tasks_file)}
    requested_tasks = payload.get("tasks") or []
    task_ids = [
        str(task_id)
        for task_id in requested_tasks
        if str(task_id) in known_tasks
    ]
    task_count = len(task_ids) if task_ids else len(known_tasks)

    try:
        timeout = int(payload.get("timeout") or 60)
    except (TypeError, ValueError):
        timeout = 60
    timeout = max(5, min(timeout, 600))

    thread = threading.Thread(
        target=background_run,
        args=(agent_names, tasks_file, task_ids, timeout, task_count),
        daemon=True,
    )
    thread.start()
    return {"ok": True, "state": current_run_state()}


def latest_snapshot():
    suites = task_suites()
    task_lookup = {}
    for suite in suites:
        for task in suite["tasks"]:
            task_lookup[task["id"]] = {
                "id": task.get("id"),
                "name": task.get("name", ""),
                "suite": suite["label"],
                "thread_id": task.get("thread_id", ""),
                "expected_action": task.get("expected_action", ""),
                "expected_tool_categories": task.get("expected_tool_categories", []),
            }
    return {
        "agents": load_agents(),
        "suites": suites,
        "results": load_results(),
        "task_lookup": task_lookup,
        "run_state": current_run_state(),
    }


PAGE = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Email Response Benchmark</title>
<style>
:root {
  --bg: #f4f6f8;
  --panel: #ffffff;
  --ink: #1c2630;
  --muted: #647282;
  --line: #d6dde5;
  --line-strong: #aeb9c5;
  --good: #167247;
  --bad: #b42318;
  --warn: #a15c00;
  --action: #255e91;
  --accent: #36506c;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 13px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
header {
  border-bottom: 1px solid var(--line);
  background: #182331;
  color: #fff;
}
.topbar {
  max-width: 1360px;
  margin: 0 auto;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}
h1 {
  margin: 0;
  font-size: 19px;
  font-weight: 650;
  letter-spacing: 0;
}
.subhead {
  color: #b8c4d0;
  font-size: 12px;
  margin-top: 2px;
}
main {
  max-width: 1360px;
  margin: 0 auto;
  padding: 18px 20px 44px;
}
.toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) 120px auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 18px;
}
.field label {
  display: block;
  margin-bottom: 5px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 650;
  text-transform: uppercase;
}
select, input {
  width: 100%;
  height: 34px;
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  background: #fff;
  color: var(--ink);
  padding: 0 9px;
  font: inherit;
}
button {
  height: 34px;
  border: 1px solid #243a52;
  border-radius: 4px;
  background: #243a52;
  color: #fff;
  padding: 0 13px;
  font-weight: 650;
  cursor: pointer;
}
button.secondary {
  background: #fff;
  color: #243a52;
}
button:disabled {
  opacity: .55;
  cursor: wait;
}
.agent-checks, .task-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: #fff;
  padding: 5px 9px;
}
.check input { width: auto; height: auto; }
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(360px, .85fr);
  gap: 18px;
  align-items: start;
}
section {
  margin-bottom: 18px;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
}
.panel h2 {
  margin: 0;
  padding: 11px 13px;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
  text-transform: uppercase;
  color: var(--accent);
  background: #f9fafb;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 8px 9px;
  border-bottom: 1px solid #edf0f3;
  text-align: left;
  vertical-align: top;
}
th {
  color: var(--muted);
  font-size: 11px;
  font-weight: 650;
  text-transform: uppercase;
  background: #fbfcfd;
}
tr:last-child td { border-bottom: 0; }
tr.clickable { cursor: pointer; }
tr.clickable:hover td { background: #f6f8fa; }
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}
.pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid transparent;
}
.pass { color: var(--good); background: #eaf6ef; border-color: #b9dfc8; }
.fail { color: var(--bad); background: #fceeee; border-color: #efc5c0; }
.dash { color: var(--muted); background: #f1f3f5; border-color: #d8dee5; }
.action { color: var(--action); background: #edf5fc; border-color: #c8dced; }
.status {
  color: #dce7f2;
  font-size: 12px;
}
.run-output {
  white-space: pre-wrap;
  max-height: 220px;
  overflow: auto;
  background: #101820;
  color: #d9e4ee;
  padding: 12px;
  margin: 0;
  border-radius: 0 0 6px 6px;
}
.details-body {
  padding: 12px 13px;
}
.tabs {
  display: flex;
  gap: 6px;
  padding: 10px 13px 0;
  border-top: 1px solid var(--line);
}
.tab {
  height: 28px;
  background: #fff;
  color: var(--accent);
  border-color: var(--line-strong);
}
.tab.active {
  background: var(--accent);
  color: #fff;
}
pre {
  margin: 10px 13px 13px;
  max-height: 420px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: #f8fafc;
  padding: 10px;
  white-space: pre-wrap;
}
.empty {
  padding: 18px 13px;
  color: var(--muted);
}
.grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.metric {
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 9px;
}
.metric .label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
}
.metric .value {
  margin-top: 2px;
  font-size: 18px;
  font-weight: 700;
}
@media (max-width: 980px) {
  .toolbar, .layout { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<header>
  <div class="topbar">
    <div>
      <h1>Email Response Benchmark</h1>
      <div class="subhead">Local runner, grader, ledger, and tool-call viewer</div>
    </div>
    <div class="status" id="runStatus">Loading</div>
  </div>
</header>
<main>
  <section class="panel">
    <h2>Run Controls</h2>
    <div style="padding:13px;">
      <div class="toolbar">
        <div class="field">
          <label>Task Suite</label>
          <select id="suiteSelect"></select>
        </div>
        <div class="field">
          <label>Agents</label>
          <div class="agent-checks" id="agentChecks"></div>
        </div>
        <div class="field">
          <label>Timeout</label>
          <input id="timeoutInput" value="60" inputmode="numeric">
        </div>
        <div>
          <button id="runButton">Run Selected</button>
          <button class="secondary" id="refreshButton">Refresh</button>
        </div>
      </div>
      <div class="field">
        <label>Tasks</label>
        <div class="task-checks" id="taskChecks"></div>
      </div>
    </div>
    <pre class="run-output" id="runOutput"></pre>
  </section>

  <div class="layout">
    <div>
      <section class="panel">
        <h2>Latest Results</h2>
        <div id="resultsWrap"></div>
      </section>
      <section class="panel">
        <h2>Task Catalog</h2>
        <div id="tasksWrap"></div>
      </section>
    </div>
    <div>
      <section class="panel">
        <h2>Run Details</h2>
        <div id="detailsWrap" class="empty">Select a result row to inspect its ledger, tool calls, result, trace, and stderr.</div>
      </section>
    </div>
  </div>
</main>

<script>
let snapshot = null;
let selectedSuite = 'tasks/tasks.json';
let selectedDetail = null;
let detailData = null;
let activeTab = 'ledger';

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function statusPill(value) {
  if (value === true) return '<span class="pill pass">PASS</span>';
  if (value === false) return '<span class="pill fail">FAIL</span>';
  return '<span class="pill dash">-</span>';
}

function suiteTasks() {
  const suite = (snapshot?.suites || []).find(s => s.path === selectedSuite);
  return suite ? suite.tasks : [];
}

async function fetchJson(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function refresh() {
  snapshot = await fetchJson('/api/snapshot');
  renderAll();
}

function renderAll() {
  renderStatus();
  renderControls();
  renderResults();
  renderTasks();
  renderDetails();
}

function renderStatus() {
  const state = snapshot?.run_state || {};
  const parts = [];
  if (state.running) {
    parts.push('Run in progress');
  } else if (state.exit_code !== null && state.exit_code !== undefined) {
    parts.push(`Last run exit ${state.exit_code}`);
  } else {
    parts.push('Ready');
  }
  $('runStatus').textContent = parts.join(' · ');
  $('runButton').disabled = !!state.running;
  $('runOutput').textContent = [state.cmd?.join(' '), state.stdout, state.stderr].filter(Boolean).join('\n\n');
}

function renderControls() {
  const suiteOptions = (snapshot.suites || []).map(s =>
    `<option value="${esc(s.path)}"${s.path === selectedSuite ? ' selected' : ''}>${esc(s.label)} (${s.tasks.length})</option>`
  ).join('');
  $('suiteSelect').innerHTML = suiteOptions;

  const agents = snapshot.agents || {};
  $('agentChecks').innerHTML = Object.keys(agents).map(name => {
    const checked = name === 'scripted_tool_agent' ? ' checked' : '';
    return `<label class="check"><input type="checkbox" name="agent" value="${esc(name)}"${checked}> ${esc(name)}</label>`;
  }).join('');

  $('taskChecks').innerHTML = [
    `<label class="check"><input type="checkbox" id="allTasks" checked> all tasks</label>`,
    ...suiteTasks().map(task =>
      `<label class="check"><input type="checkbox" name="task" value="${esc(task.id)}"> <span class="mono">${esc(task.id)}</span></label>`
    )
  ].join('');

  $('allTasks')?.addEventListener('change', (event) => {
    if (event.target.checked) {
      document.querySelectorAll('input[name="task"]').forEach(input => { input.checked = false; });
    }
  });
  document.querySelectorAll('input[name="task"]').forEach(input => {
    input.addEventListener('change', () => {
      if (input.checked && $('allTasks')) $('allTasks').checked = false;
      const anyTaskChecked = [...document.querySelectorAll('input[name="task"]')].some(item => item.checked);
      if (!anyTaskChecked && $('allTasks')) $('allTasks').checked = true;
    });
  });
}

function renderResults() {
  const results = snapshot.results || [];
  if (!results.length) {
    $('resultsWrap').innerHTML = '<div class="empty">No run summary yet. Launch a run above or use runner.py.</div>';
    return;
  }

  const rows = results.map((r, idx) => {
    const task = snapshot.task_lookup?.[r.task_id] || {};
    return `<tr class="clickable" data-run="${esc(r.run_dir || '')}" data-idx="${idx}">
      <td>${statusPill(r.passed)}</td>
      <td class="mono">${esc(r.task_id)}</td>
      <td>${esc(task.name || '')}</td>
      <td class="mono">${esc(r.agent)}</td>
      <td>${esc(r.n_tool_calls ?? 0)}</td>
      <td>${esc(r.wall_s ?? '')}s</td>
      <td>${esc((r.reasons || [])[0] || '')}</td>
    </tr>`;
  }).join('');

  const passed = results.filter(r => r.passed === true).length;
  const agentNames = [...new Set(results.map(r => r.agent))].sort();
  const metrics = `<div class="details-body grid2">
    <div class="metric"><div class="label">Passes</div><div class="value">${passed}/${results.length}</div></div>
    <div class="metric"><div class="label">Agents</div><div class="value">${agentNames.length}</div></div>
  </div>`;

  $('resultsWrap').innerHTML = metrics + `<table><thead><tr>
    <th>Status</th><th>Task</th><th>Name</th><th>Agent</th><th>Calls</th><th>Wall</th><th>First failure</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
  document.querySelectorAll('#resultsWrap tr[data-run]').forEach(row => {
    row.addEventListener('click', () => loadDetails(row.dataset.run));
  });
}

function renderTasks() {
  const rows = suiteTasks().map(task => `<tr>
    <td class="mono">${esc(task.id)}</td>
    <td>${esc(task.name || '')}</td>
    <td><span class="pill action">${esc(task.expected_action || '')}</span></td>
    <td>${esc(task.thread_id || '')}</td>
    <td>${esc((task.expected_tool_categories || []).join(', '))}</td>
  </tr>`).join('');
  $('tasksWrap').innerHTML = `<table><thead><tr>
    <th>Task</th><th>Name</th><th>Action</th><th>Thread</th><th>Tools</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

function renderDetails() {
  if (!detailData) return;
  const tabs = ['ledger', 'tool_calls', 'result', 'trace', 'stderr'];
  const tabButtons = tabs.map(tab =>
    `<button class="tab${activeTab === tab ? ' active' : ''}" data-tab="${tab}">${esc(tab.replace('_', ' '))}</button>`
  ).join('');
  let payload = detailData[activeTab];
  if (activeTab === 'tool_calls') payload = detailData.tool_calls || [];
  if (typeof payload !== 'string') payload = JSON.stringify(payload, null, 2);
  $('detailsWrap').className = '';
  $('detailsWrap').innerHTML = `
    <div class="details-body">
      <div class="mono">${esc(detailData.run_dir || selectedDetail || '')}</div>
    </div>
    <div class="tabs">${tabButtons}</div>
    <pre>${esc(payload || '')}</pre>`;
  document.querySelectorAll('.tab').forEach(button => {
    button.addEventListener('click', () => {
      activeTab = button.dataset.tab;
      renderDetails();
    });
  });
}

async function loadDetails(runDir) {
  if (!runDir) return;
  selectedDetail = runDir;
  activeTab = 'ledger';
  detailData = await fetchJson('/api/run?run_dir=' + encodeURIComponent(runDir));
  renderDetails();
}

async function startRun() {
  const agents = [...document.querySelectorAll('input[name="agent"]:checked')].map(input => input.value);
  const allTasks = $('allTasks')?.checked;
  const tasks = allTasks ? [] : [...document.querySelectorAll('input[name="task"]:checked')].map(input => input.value);
  await fetchJson('/api/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      agents,
      tasks,
      tasks_file: selectedSuite,
      timeout: $('timeoutInput').value
    })
  });
  await refresh();
}

$('suiteSelect').addEventListener('change', (event) => {
  selectedSuite = event.target.value;
  renderControls();
  renderTasks();
});
$('runButton').addEventListener('click', startRun);
$('refreshButton').addEventListener('click', refresh);
setInterval(async () => {
  if (snapshot?.run_state?.running) await refresh();
}, 1200);
refresh().catch(err => {
  $('runStatus').textContent = 'Error';
  $('resultsWrap').innerHTML = `<div class="empty">${esc(err.message)}</div>`;
});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def send_json(self, payload, status=200):
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, content_type="text/html; charset=utf-8", status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self.send_text(PAGE)
        elif parsed.path == "/api/snapshot":
            self.send_json(latest_snapshot())
        elif parsed.path == "/api/run":
            params = urllib.parse.parse_qs(parsed.query)
            self.send_json(run_details((params.get("run_dir") or [""])[0]))
        else:
            self.send_json({"error": "not found"}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}

        if parsed.path == "/api/run":
            result = start_run(payload)
            self.send_json(result, status=200 if result.get("ok") else 400)
        else:
            self.send_json({"error": "not found"}, status=404)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Email benchmark dashboard -> http://127.0.0.1:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

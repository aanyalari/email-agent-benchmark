# Email Agent Benchmark

# 1. Goal and Objective

The goal of this project is to evaluate how well AI agents can handle realistic email-response workflows.

The benchmark tests more than whether an agent can write a polished email. It checks whether the agent can use tools, gather the right information, choose the correct action, and record evidence for its decision.

The main objective is to compare Codex and Claude Code agents on the same set of email tasks using objective, repeatable evaluation metrics.

Codex

Claude Code Haiku

Claude Code Sonnet

The benchmark asks which agent is better at completing email workflows correctly, safely, and with enough supporting evidence.

# 2. Benchmark Setup

The benchmark creates a fake company email environment. Each agent receives an email task, such as a refund request, sales question, or scheduling request. The agent must inspect the email and use tools to find extra information before taking action.

The fake company world includes an inbox, CRM records, calendar availability, and knowledge-base policy documents.

| Artifact | Purpose |
| --- | --- |
| ledger.json | Final workflow actions taken by the agent. |
| tool_calls.jsonl | Tools the agent used and whether each call succeeded. |
| trace.jsonl | Agent execution trace. |
| result.json | Deterministic grade for one task. |
| summary.json | Combined run results. |

The important idea is that the benchmark does not only judge the final email text. It checks whether the agent actually used the right tools and wrote the correct structured action.

# 3. What the MCP Server and Tools Are For

The MCP server is the fake email workplace that the agents interact with. MCP stands for Model Context Protocol. In this project, it lets Codex and Claude use the same benchmark tools in the same way.

Instead of giving the agent all answers directly, the agent has to use tools to read context and record actions.

| Tool | What It Does |
| --- | --- |
| get_email_thread | Reads the email thread. |
| lookup_customer | Looks up the sender in CRM. |
| lookup_company | Gets company/account information. |
| search_kb | Searches company policy documents. |
| get_calendar_availability | Checks calendar slots. |
| create_draft | Records a draft reply. |
| forward_email | Records a forwarded email. |
| escalate_email | Records an escalation. |
| schedule_meeting | Records a meeting. |
| mark_ignore | Records that a thread was ignored. |

The MCP server has two main purposes. First, it gives agents information, such as who the customer is, what the refund policy says, or whether a calendar slot is available. Second, it records the agent's final action, such as creating a draft, forwarding an email, escalating a case, or scheduling a meeting.

The MCP server is like a fake Gmail plus fake CRM plus fake calendar plus fake company policy database. The agent has to use it to solve the task, and the benchmark grades what the agent did inside that fake workplace.

When the benchmark says an email was forwarded, it does not mean a real email was sent through Gmail or Outlook. It means the agent used the benchmark's forward_email tool, and that tool recorded a forward action in ledger.json. This makes the benchmark safe and repeatable.

# 4. Method

The same six starter tasks were run against three agents.

| Agent | Description |
| --- | --- |
| Codex GPT 5.5 | Codex CLI connected to the benchmark email MCP tools. |
| Claude Code Haiku 4.5 | Claude Code Haiku connected to the same email MCP tools. |
| Claude Code Sonnet 5.0 | Claude Code Sonnet connected to the same email MCP tools. |

The agents were evaluated on the same tasks, with the same fake inbox, CRM, calendar, and knowledge-base data.

Run command: python3 runner.py --agents codex,claude-haiku,claude-sonnet --timeout 600 --runs-dir results/codex-vs-claude-fixed

Each task was graded by a deterministic grader. This means the grader checks exact structured conditions rather than asking another model to judge the answer.

# 5. Task Descriptions

| Task ID | Scenario | Expected Action |
| --- | --- | --- |
| support_001 | Customer asks for a refund outside the refund window. | Create a draft reply. |
| support_002 | VIP customer reports repeated outage/service failures. | Escalate. |
| sales_001 | New lead asks for standard pricing. | Create a draft reply. |
| sales_002 | Existing customer asks about renewal/discount handling. | Forward to account owner. |
| sched_001 | Customer requests a demo at an available time. | Schedule meeting. |
| sched_002 | Customer requests a meeting time that is unavailable. | Create a draft proposing alternatives. |

The suite includes 2 support tasks, 2 sales tasks, and 2 scheduling tasks.

# 6. Evaluation Metrics

| Metric | Meaning |
| --- | --- |
| Pass rate | How many tasks the agent fully completed correctly. |
| Action accuracy | Whether the agent chose the correct workflow action. |
| Evidence coverage | Whether the agent attached the required structured fact IDs for its actions. |
| Tool coverage | Whether the agent used the expected types of tools. |
| Safety | Whether the agent avoided forbidden or unsupported claims. |
| Calendar correctness | Whether scheduling constraints were satisfied. |
| Average tool calls | Average number of tools used per task. |
| Failed tool calls | Number of tool calls that failed. |
| Average runtime | Average time per task. |
| Token usage | Reported token telemetry from each agent's trace logs. |

| Token caveat: Codex and Claude Code report token fields differently, especially cached tokens. Token usage should be treated as diagnostic telemetry, not a perfect apples-to-apples cost comparison. |
| --- |

# 7. Overall Results

| Agent | Pass | Action | Evidence | Tools | Safety | Calendar | Avg Calls | Failed | Avg Runtime |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Codex | 4/6 | 5/6 | 4/6 | 6/6 | 6/6 | 5/6 | 8.5 | 3 | 37.1s |
| Claude Sonnet | 2/6 | 4/6 | 3/6 | 6/6 | 6/6 | 5/6 | 7.3 | 3 | 36.4s |
| Claude Haiku | 1/6 | 5/6 | 1/6 | 4/6 | 5/6 | 5/6 | 4.8 | 4 | 36.4s |

Codex had the highest pass rate, passing 4 out of 6 tasks. Claude Sonnet passed 2 out of 6 tasks. Claude Haiku passed 1 out of 6 tasks.

# 8. Token Usage Results

| Agent | Avg Input | Avg Cache Read | Avg Cache Write | Avg Output | Avg Reasoning | Avg Total Shown |
| --- | --- | --- | --- | --- | --- | --- |
| Codex | 112,930 | 90,027 | 0 | 1,182 | 490 | 114,112 |
| Claude Sonnet | 15 | 149,907 | 16,657 | 2,228 | N/A | 168,807 |
| Claude Haiku | 66 | 107,211 | 11,050 | 1,966 | N/A | 120,293 |

Claude Sonnet used the most reported total tokens on average. Codex used fewer total reported tokens than Claude Sonnet but more than Claude Haiku by this calculation. These numbers should be interpreted carefully because token accounting differs between Codex and Claude Code.

# 9. Task-Level Results

| Task | Codex | Claude Haiku | Claude Sonnet |
| --- | --- | --- | --- |
| support_001 | Pass | Pass | Pass |
| support_002 | Pass | Fail | Fail |
| sales_001 | Pass | Fail | Pass |
| sales_002 | Pass | Fail | Fail |
| sched_001 | Fail | Fail | Fail |
| sched_002 | Fail | Fail | Fail |

# 10. Explanation of Results

Codex performed best overall. It passed the two support tasks and the two sales tasks. Its main weakness was scheduling, where it failed both scheduling tasks.

Claude Sonnet performed second best. It passed support_001 and sales_001, but failed the other four tasks. Its failures included wrong action choices and missing required evidence IDs.

Claude Haiku performed weakest. It passed only support_001. It often used tools, but it missed important evidence IDs and sometimes skipped required tool categories. It also made one forbidden claim in the sales renewal task.

The most important pattern is that all agents failed both scheduling tasks. This suggests that scheduling workflows are harder than support and sales workflows in the current benchmark.

Another important pattern is that agents sometimes appeared to understand the task but still failed because they did not record the correct structured evidence.

# 11. Key Findings

Codex was the strongest agent in this pilot.

Codex passed 4 out of 6 tasks, compared with 2 out of 6 for Claude Sonnet and 1 out of 6 for Claude Haiku.

All agents struggled with scheduling.

Evidence recording was a common source of failure.

Tool usage alone did not guarantee success.

Safety performance was mostly strong.

The deterministic grader made failures easy to inspect.

# 12. Limitations

This was a small pilot with only six starter tasks.

Each agent was run once, so results may vary across repeated runs.

The benchmark currently emphasizes objective workflow correctness more than natural-language quality.

The deterministic grader can be strict when evidence IDs are missing.

Token usage is not perfectly comparable across agents because Codex and Claude Code expose different token accounting fields.

The benchmark simulates email actions instead of sending real emails.

Scheduling failures may reflect model weakness, task design, tool design, or grading strictness.

# 13. Future Directions

Expand the benchmark with more support, sales, scheduling, security, billing, and account-management tasks.

Run each agent multiple times per task to measure consistency.

Add a larger hard-task suite with ambiguity, conflicting evidence, longer threads, and multi-step decisions.

Add an LLM-as-judge component for email draft quality, including tone, empathy, clarity, completeness, professionalism, directness, and concision.

Use a hybrid evaluation: deterministic grading for objective facts/actions and LLM-as-judge grading for natural-language quality.

Improve scheduling tests and separate wrong-action failures from missing-evidence failures.

Add stronger simulated action checks, such as exact forward recipient validation, required forward notes, and a fake outbox service.

# 14. Conclusion

This pilot shows that Codex performed best on the current email-response benchmark.

| Agent | Pass Rate |
| --- | --- |
| Codex | 4/6 |
| Claude Sonnet | 2/6 |
| Claude Haiku | 1/6 |

Codex was strongest overall, especially on support and sales workflows. Claude Sonnet showed moderate performance, while Claude Haiku struggled with evidence coverage and one safety issue.

The largest common weakness across all agents was scheduling. This makes scheduling the most important area for future benchmark improvement and agent comparison.

The current benchmark is useful because it evaluates agents as workflow actors, not just email writers. It checks whether agents can gather evidence, make correct decisions, use tools, and produce durable action records.

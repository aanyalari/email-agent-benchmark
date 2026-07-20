#!/usr/bin/env python3
"""OpenAI agent adapter for the email-response benchmark.

Reads the MCP config written by runner.py, spawns the email MCP server as a
subprocess, exposes its tools to the OpenAI chat-completions API (tool calling),
and runs an agentic loop until the model stops calling tools or the turn limit
is reached.

Usage (via agents.json entry, invoked by runner.py):
    python3 agents/openai_mcp_agent.py \
        --mcp-config <path> \
        --model gpt-4o \
        --max-turns 50 \
        "<prompt>"

Prerequisites:
    pip install openai mcp
    OPENAI_API_KEY must be set in the environment.
"""
import argparse
import json
import subprocess
import sys
import threading
import time

try:
    import openai
except ImportError:
    sys.exit("openai package not installed: pip install openai")

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    sys.exit("mcp package not installed: pip install mcp")

import asyncio


def load_mcp_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_agent(prompt, model, mcp_config_path, max_turns):
    cfg = load_mcp_config(mcp_config_path)
    server_cfg = cfg["mcpServers"]["email"]
    server_params = StdioServerParameters(
        command=server_cfg["command"],
        args=server_cfg["args"],
        env=server_cfg.get("env"),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover available tools and convert to OpenAI tool format
            tools_result = await session.list_tools()
            openai_tools = []
            tool_map = {}
            for tool in tools_result.tools:
                schema = tool.inputSchema or {"type": "object", "properties": {}}
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": schema,
                    },
                })
                tool_map[tool.name] = tool

            client = openai.AsyncOpenAI()
            messages = [{"role": "user", "content": prompt}]

            for turn in range(max_turns):
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=openai_tools if openai_tools else None,
                    tool_choice="auto" if openai_tools else None,
                )
                choice = response.choices[0]
                msg = choice.message

                # Emit the assistant turn to stdout so runner.py can capture it
                print(json.dumps({
                    "turn": turn + 1,
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                        for tc in (msg.tool_calls or [])
                    ],
                }), flush=True)

                if not msg.tool_calls:
                    # Model is done
                    break

                # Append assistant message with tool_calls
                messages.append(msg.model_dump(exclude_unset=True))

                # Execute each tool call via MCP and append results
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}

                    try:
                        result = await session.call_tool(tc.function.name, args)
                        content_text = "\n".join(
                            block.text for block in result.content
                            if hasattr(block, "text")
                        )
                        if not content_text and result.content:
                            content_text = str(result.content[0])
                    except Exception as exc:
                        content_text = f"Tool call error: {exc}"

                    print(json.dumps({
                        "turn": turn + 1,
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": content_text,
                    }), flush=True)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": content_text,
                    })
            else:
                print(json.dumps({"warning": f"Reached max_turns={max_turns} without finishing"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description="OpenAI MCP agent adapter")
    parser.add_argument("prompt", help="Task prompt string")
    parser.add_argument("--mcp-config", required=True, help="Path to mcp_config.json written by runner.py")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model name")
    parser.add_argument("--max-turns", type=int, default=50, help="Max agentic loop iterations")
    args = parser.parse_args()

    asyncio.run(run_agent(args.prompt, args.model, args.mcp_config, args.max_turns))


if __name__ == "__main__":
    main()

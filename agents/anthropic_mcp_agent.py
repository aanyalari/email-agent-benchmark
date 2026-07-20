#!/usr/bin/env python3
"""Anthropic agent adapter for the email-response benchmark.

Uses the Anthropic Python SDK with tool calling and the MCP Python SDK to
connect directly to the email MCP server — no Claude Code CLI required.

Usage (via agents.json entry, invoked by runner.py):
    python3 agents/anthropic_mcp_agent.py \
        --mcp-config <path> \
        --model claude-sonnet-4-5 \
        --max-turns 50 \
        "<prompt>"

Prerequisites:
    pip install anthropic mcp
    ANTHROPIC_API_KEY must be set in the environment.
"""
import argparse
import asyncio
import json
import sys

try:
    import anthropic
except ImportError:
    sys.exit("anthropic package not installed: pip install anthropic")

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    sys.exit("mcp package not installed: pip install mcp")


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

            # Discover MCP tools and convert to Anthropic tool format
            tools_result = await session.list_tools()
            anthropic_tools = []
            for tool in tools_result.tools:
                schema = tool.inputSchema or {"type": "object", "properties": {}}
                anthropic_tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": schema,
                })

            client = anthropic.AsyncAnthropic()
            messages = [{"role": "user", "content": prompt}]

            for turn in range(max_turns):
                response = await client.messages.create(
                    model=model,
                    max_tokens=4096,
                    tools=anthropic_tools,
                    messages=messages,
                )

                # Emit assistant turn to stdout for runner.py trace
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                text_blocks = [b for b in response.content if b.type == "text"]
                print(json.dumps({
                    "turn": turn + 1,
                    "role": "assistant",
                    "content": " ".join(b.text for b in text_blocks),
                    "tool_uses": [{"id": b.id, "name": b.name, "input": b.input} for b in tool_uses],
                    "stop_reason": response.stop_reason,
                }), flush=True)

                # Append assistant response to message history
                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason == "end_turn" or not tool_uses:
                    break

                # Execute each tool call and collect results
                tool_results = []
                for block in tool_uses:
                    try:
                        result = await session.call_tool(block.name, block.input)
                        content_text = "\n".join(
                            b.text for b in result.content if hasattr(b, "text")
                        )
                        if not content_text and result.content:
                            content_text = str(result.content[0])
                        is_error = False
                    except Exception as exc:
                        content_text = f"Tool call error: {exc}"
                        is_error = True

                    print(json.dumps({
                        "turn": turn + 1,
                        "role": "tool_result",
                        "tool_use_id": block.id,
                        "name": block.name,
                        "content": content_text,
                        "is_error": is_error,
                    }), flush=True)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content_text,
                        "is_error": is_error,
                    })

                messages.append({"role": "user", "content": tool_results})
            else:
                print(json.dumps({"warning": f"Reached max_turns={max_turns} without finishing"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Anthropic API MCP agent adapter")
    parser.add_argument("prompt", help="Task prompt string")
    parser.add_argument("--mcp-config", required=True, help="Path to mcp_config.json written by runner.py")
    parser.add_argument("--model", default="claude-sonnet-4-5", help="Anthropic model ID")
    parser.add_argument("--max-turns", type=int, default=50, help="Max agentic loop iterations")
    args = parser.parse_args()

    asyncio.run(run_agent(args.prompt, args.model, args.mcp_config, args.max_turns))


if __name__ == "__main__":
    main()

# SPDX-License-Identifier: LGPL-3.0-only
"""kitchenforge.claude_agent — Claude drives KitchenForge via tool_use.

Bridges Anthropic's Messages API + tool_use protocol to KitchenForge's
typed tool catalog. The agent surface is intentionally Claude-shaped:
the JSON schemas at `/agent/v1/tools` plug straight into the `tools=`
parameter of Claude's API.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    export KF_BASE=https://southbrookcabinetry.space
    export KF_API_KEY=kfk-...            # X-Api-Key for the agent fs
    export KF_MODEL=claude-opus-4-7      # optional; default below

    python -m kitchenforge.claude_agent "Build a Full Kitchen quote for Jane Smith
    in a 4200x3000 mm L-shape kitchen with maple boxes and shaker doors,
    confirm the quote, release manufacturing orders."

The agent will:
1. Fetch the live tool catalog from `/agent/v1/tools`
2. Hand it to Claude
3. Loop: Claude proposes a tool_use → script calls KitchenForge → returns result
4. Claude continues until it issues `end_turn` or runs out of patience

The script prints every tool call + result so the conversation is auditable.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.request
import urllib.error
from typing import Any, Optional


SCHEMA_VERSION = "kitchenforge.claude_agent.v1"
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TURNS = 12


# ----------------------------------------------------------------------
# KitchenForge HTTP transport
# ----------------------------------------------------------------------
class KFClient:
    def __init__(self, base: str, api_key: str):
        self.base = base.rstrip("/")
        self.api_key = api_key

    def _do(self, method: str, path: str, body: Optional[dict] = None,
            extra_headers: Optional[dict] = None) -> dict:
        url = self.base + path
        headers = {"X-Api-Key": self.api_key,
                   "Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            return {"error": "http_error",
                    "status": e.code,
                    "body": (e.read() or b"").decode()[:1000]}
        except urllib.error.URLError as e:
            return {"error": "url_error", "message": str(e)}

    def health(self) -> dict:
        return self._do("GET", "/.well-known/ai-agent.json")

    def tools(self) -> dict:
        return self._do("GET", "/agent/v1/tools")

    def call_tool(self, tool_name: str, args: dict) -> dict:
        return self._do(
            "POST", f"/agent/v1/tools/{tool_name}",
            body=args,
            extra_headers={"Idempotency-Key": str(uuid.uuid4())})

    def fs_get(self, path: str) -> dict:
        return self._do("GET", f"/agent/v1/files/{path.lstrip('/')}")


# ----------------------------------------------------------------------
# Anthropic Messages API transport
# ----------------------------------------------------------------------
class ClaudeClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def messages(self, *, system: str, messages: list,
                 tools: list, max_tokens: int = 4096) -> dict:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "tools": tools,
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())


# ----------------------------------------------------------------------
# Agent loop
# ----------------------------------------------------------------------
SYSTEM_PROMPT = """You are the KitchenForge orchestration agent.

You drive a working kitchen-MRP platform via a typed tool catalog. The
human gives you natural-language requests like "build a quote for Jane in
a 4m kitchen with maple boxes" and you turn those into a sequence of tool
calls against the platform.

The tool catalog is provided. Each tool has a strict input schema. You
must use these tools — do not pretend to act. Each tool call returns a
structured result; chain calls as needed.

Style: concise. State what you're about to do in one sentence, make the
tool call, observe the result, continue. End your turn when the user's
request is satisfied (e.g. quote confirmed and MOs released)."""


def run_agent(prompt: str, *, kf: KFClient, claude: ClaudeClient,
              max_turns: int = DEFAULT_MAX_TURNS) -> None:
    print(f"=== fetching tool catalog from {kf.base}/agent/v1/tools ===")
    catalog = kf.tools()
    if catalog.get("error"):
        print(f"  ERROR fetching tools: {catalog}")
        sys.exit(1)
    tools = catalog.get("tools", [])
    print(f"  loaded {len(tools)} tools: {', '.join(t['name'] for t in tools)}")
    print()

    # Adapt KF's tool schema (name/description/input_schema) to Claude's
    # tools= shape — they're already nearly identical.
    claude_tools = [{
        "name": t["name"],
        "description": t["description"],
        "input_schema": t["input_schema"],
    } for t in tools]

    messages: list = [{"role": "user", "content": prompt}]

    for turn in range(1, max_turns + 1):
        print(f"--- turn {turn} ---")
        resp = claude.messages(
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=claude_tools,
            max_tokens=4096)

        stop_reason = resp.get("stop_reason")
        content = resp.get("content", [])
        assistant_blocks: list = []
        tool_calls: list = []

        for block in content:
            if block["type"] == "text":
                text = block["text"]
                if text.strip():
                    print(f"  Claude: {text.strip()}")
                assistant_blocks.append(block)
            elif block["type"] == "tool_use":
                tool_name = block["name"]
                args = block.get("input", {})
                print(f"  > tool_use: {tool_name}({json.dumps(args)[:120]})")
                assistant_blocks.append(block)
                tool_calls.append((block["id"], tool_name, args))

        messages.append({"role": "assistant", "content": assistant_blocks})

        if stop_reason == "end_turn" and not tool_calls:
            print(f"--- agent finished (stop_reason=end_turn, turn {turn}) ---")
            return

        if not tool_calls:
            print(f"--- no tool calls, stop_reason={stop_reason} ---")
            return

        # Execute each tool_use against KF and feed results back.
        results: list = []
        for tool_id, name, args in tool_calls:
            result = kf.call_tool(name, args)
            print(f"  < result for {name}: {json.dumps(result)[:200]}")
            results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result),
                "is_error": bool(result.get("error")),
            })

        messages.append({"role": "user", "content": results})

    print(f"--- max_turns ({max_turns}) reached ---")


def main() -> None:
    ak = os.environ.get("ANTHROPIC_API_KEY")
    kf_base = os.environ.get("KF_BASE", "https://southbrookcabinetry.space")
    kf_key = os.environ.get("KF_API_KEY")
    model = os.environ.get("KF_MODEL", DEFAULT_MODEL)

    if not ak:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(2)
    if not kf_key:
        print("ERROR: KF_API_KEY not set (issued at backend Settings ▸ API Keys)",
              file=sys.stderr)
        sys.exit(2)

    if len(sys.argv) < 2:
        print("Usage: python -m kitchenforge.claude_agent \"<prompt>\"",
              file=sys.stderr)
        sys.exit(2)
    prompt = " ".join(sys.argv[1:])

    kf = KFClient(kf_base, kf_key)
    claude = ClaudeClient(ak, model)

    # Pre-flight: is the agent surface live?
    health = kf.health()
    if health.get("error") or "schema_version" not in health:
        print(f"WARN: agent surface not ready: {json.dumps(health)[:200]}",
              file=sys.stderr)
        print("Deploy kitchenforge_core first (deploy/qnap_direct_deploy.sh)",
              file=sys.stderr)
        sys.exit(3)
    print(f"agent surface live: {health.get('name_for_human')}")
    print()

    run_agent(prompt, kf=kf, claude=claude)


if __name__ == "__main__":
    main()

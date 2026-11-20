"""Thin MCP stdio client used by the agent."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class MCPClient:
    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "src.mcp_server"],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._id = 0
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "helpdesk-agent", "version": "1.0.0"}})

    def _rpc(self, method: str, params: dict) -> dict:
        self._id += 1
        message = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed the stream")
            payload = json.loads(line)
            if payload.get("id") == self._id:
                if "error" in payload:
                    raise RuntimeError(payload["error"]["message"])
                return payload["result"]

    def call_tool(self, name: str, arguments: dict) -> dict:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        text = result["content"][0]["text"]
        return {"is_error": bool(result.get("isError")), "raw": text, "data": None if result.get("isError") else json.loads(text)}

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()

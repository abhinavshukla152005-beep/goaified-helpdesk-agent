"""Minimal MCP server (stdio, newline-delimited JSON-RPC 2.0).

Exposes employee data from PostgreSQL (or the SQLite demo file) to any MCP client.
Run:  python -m src.mcp_server           # serve on stdio
      python -m src.mcp_server --selftest # one-shot smoke test
"""
from __future__ import annotations

import json
import sys

from . import db

SERVER_INFO = {"name": "helpdesk-mcp", "version": "1.0.0"}
TOOLS = [
    {
        "name": "get_leave_balance",
        "description": "Return remaining annual, sick and casual leave for one employee.",
        "inputSchema": {
            "type": "object",
            "properties": {"employee_id": {"type": "string", "description": "e.g. E102"}},
            "required": ["employee_id"],
        },
    },
    {
        "name": "get_employee_profile",
        "description": "Return department, manager and joining date for one employee.",
        "inputSchema": {
            "type": "object",
            "properties": {"employee_id": {"type": "string", "description": "e.g. E102"}},
            "required": ["employee_id"],
        },
    },
]


def _call_tool(name: str, args: dict) -> dict:
    conn, engine = db.connect()
    try:
        employee_id = str(args.get("employee_id", "")).strip()
        if name == "get_leave_balance":
            row = db.leave_balance(conn, engine, employee_id)
        elif name == "get_employee_profile":
            row = db.employee_profile(conn, engine, employee_id)
        else:
            return {"isError": True, "text": f"unknown tool: {name}"}
        if row is None:
            return {"isError": True, "text": f"employee not found: {employee_id}"}
        return {"isError": False, "text": json.dumps(row)}
    finally:
        conn.close()


def handle(request: dict) -> dict | None:
    method = request.get("method")
    req_id = request.get("id")
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params") or {}
        out = _call_tool(params.get("name", ""), params.get("arguments") or {})
        result = {"content": [{"type": "text", "text": out["text"]}], "isError": out["isError"]}
    elif method in ("notifications/initialized", "notifications/cancelled"):
        return None
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def serve() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}), flush=True)
            continue
        response = handle(request)
        if response is not None:
            print(json.dumps(response), flush=True)


def selftest() -> None:
    for call in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "get_leave_balance", "arguments": {"employee_id": "E102"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "get_leave_balance", "arguments": {"employee_id": "E999"}}},
    ):
        print(json.dumps(handle(call)))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        print("helpdesk-mcp listening on stdio", file=sys.stderr, flush=True)
        serve()

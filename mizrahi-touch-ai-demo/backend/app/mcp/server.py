"""The Mortgage Case MCP server — Streamable HTTP, stateless, JSON responses, tools only.

The same tool registry as the in-app assistant, so JEEN Talk or a JEEN agent sees exactly
the case state the customer app shows. Each bearer key is bound to ONE case; a model
never names the case it reads. Browser Origins other than localhost are refused."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ..agent import tools
from ..config import settings
from ..store import repo

router = APIRouter(tags=["mcp"])
PROTOCOL_VERSIONS = ["2026-07-28", "2025-11-25", "2025-06-18", "2025-03-26"]
SERVER_INFO = {"name": "mizrahi-touch-mortgage-case", "version": "0.1.0"}
INSTRUCTIONS = ("Mortgage Case Service of the Mizrahi Tefahot Touch × JEEN concept demo (synthetic data). Read the case "
                "state, document reviews and open items of the ONE case your key is bound to; record a customer statement "
                "or a banker handoff only with explicit customer confirmation. " + tools.NOTICE)
BUDGET = 3800


def _deny(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": message}},
                        headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)


def _fit(data: dict) -> dict:
    text = json.dumps(data, ensure_ascii=False)
    if len(text) <= BUDGET:
        return data
    trimmed = dict(data)
    for key in ("history", "limitations_he", "facts", "criteria", "documents", "items", "runs", "evidence"):
        for holder in (trimmed, trimmed.get("review") or {}):
            if isinstance(holder.get(key), list) and len(holder[key]) > 3:
                holder[key] = holder[key][:3]
                trimmed["truncated"] = True
        if len(json.dumps(trimmed, ensure_ascii=False)) <= BUDGET:
            break
    return trimmed


def _tool_list() -> list[dict]:
    out = []
    for name, spec in tools.TOOLS.items():
        if not tools.on_channel(name, "mcp"):
            continue
        ann = ({"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
               if spec["write"] else {"readOnlyHint": True, "openWorldHint": False})
        out.append({"name": name, "description": spec["description"],
                    "inputSchema": {**spec["parameters"], "additionalProperties": False}, "annotations": ann})
    return out


def handle(message: Any, case_id: str, key_prefix: str) -> dict | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid JSON-RPC request."}}
    if "id" not in message:
        return None
    method, msg_id, params = message["method"], message["id"], message.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _tool_list()}}
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if not tools.on_channel(name, "mcp"):
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
        allowed = set(tools.TOOLS[name]["parameters"].get("properties", {}))
        extra = set(args) - allowed
        if extra:
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [
                {"type": "text", "text": f"unexpected arguments: {', '.join(sorted(extra))}"}]}}
        ctx = {"case_id": case_id, "channel": "mcp", "actor": f"mcp:{key_prefix}", "turn_id": str(msg_id)}
        try:
            data = _fit(tools.call(name, case_id, args, ctx))
        except tools.ToolError as exc:
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": str(exc)}]}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, default=str)}],
            "structuredContent": data, "isError": False}}
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


@router.post("/mcp")
async def mcp_post(request: Request):
    origin = request.headers.get("origin")
    if origin and not any(origin.startswith(p) for p in ("http://localhost", "http://127.0.0.1")):
        return _deny(403, "Origin not allowed.")
    version = request.headers.get("mcp-protocol-version")
    if version and version not in PROTOCOL_VERSIONS:
        return _deny(400, "Unsupported MCP-Protocol-Version.")
    auth = request.headers.get("authorization") or ""
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    case_id = settings.mcp_keys.get(token)
    if not case_id:
        return _deny(401, "A valid Mortgage Case MCP key is required.")
    try:
        message = json.loads(await request.body())
    except ValueError:
        return JSONResponse(status_code=400, content={"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error."}})
    if isinstance(message, list):
        return JSONResponse(content={"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Batch requests are not supported."}})
    answer = handle(message, case_id, token[:8])
    if answer is None:
        return Response(status_code=202)
    if message.get("method") == "tools/call":
        repo.audit(case_id, f"mcp:{token[:8]}", "mcp_call", (message.get("params") or {}).get("name", ""), None)
    return JSONResponse(content=answer)


@router.get("/mcp")
@router.delete("/mcp")
def mcp_other():
    return Response(status_code=405, headers={"Allow": "POST"})

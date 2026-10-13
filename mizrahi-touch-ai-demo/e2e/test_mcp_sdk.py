"""Mortgage Case MCP server checked with the official MCP Python SDK client over Streamable HTTP:
handshake, tool catalog, MCP-vs-app consistency, write guard, case binding, and HTTP-level refusals.
Read-only against the case except for one write attempt that the server must refuse.

Run (backend on :8790, ideally after e2e/test_journey.py so the case has documents and findings):
    backend/.venv/bin/python e2e/test_mcp_sdk.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
import demo_auth  # noqa: E402  (e2e/ is on sys.path when a suite runs as a script)

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8790")
demo_auth.install(BASE)                   # the service has no anonymous access (see demo_auth.py)
CASE, OTHER = "DEMO-MTZ-2026-001", "DEMO-MTZ-2026-002"
ROOT = Path(__file__).resolve().parent
ENV = ROOT.parent / "backend" / ".env"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} · {name}{' · ' + detail if detail else ''}", flush=True)


def case_keys() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ENV.read_text(encoding="utf8").splitlines() if not os.environ.get("E2E_MCP_KEY") else []):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    return {CASE: os.environ.get("E2E_MCP_KEY") or values["MCP_DEMO_KEY"], OTHER: os.environ.get("E2E_MCP_KEY_2") or values["MCP_DEMO_KEY_2"]}


async def with_session(key: str, work):
    client = create_mcp_http_client(headers={"Authorization": f"Bearer {key}"})
    async with client, streamable_http_client(f"{BASE}/mcp", http_client=client) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            return await work(session, init)


async def bound_case_calls(session: ClientSession, init) -> dict:
    listed = await session.list_tools()
    return {
        "init": init,
        "tools": listed.tools,
        "overview": await session.call_tool("get_case_overview", {}),
        "open": await session.call_tool("list_open_items", {"audience": "all"}),
        "documents": await session.call_tool("list_documents", {}),
        "unconfirmed_write": await session.call_tool("record_customer_statement",
                                                     {"statement": "בדיקת MCP", "customer_confirmed": False}),
    }


async def other_case_calls(session: ClientSession, init) -> dict:
    return {"overview": await session.call_tool("get_case_overview", {}),
            "documents": await session.call_tool("list_documents", {})}


def raw(key: str, message: dict, **headers: str) -> httpx.Response:
    return httpx.post(f"{BASE}/mcp", json=message, timeout=30, headers={
        "Authorization": f"Bearer {key}", "Accept": "application/json, text/event-stream", **headers})


def main() -> int:
    keys = case_keys()
    snap = httpx.get(f"{BASE}/api/cases/{CASE}", timeout=30).json()
    app_docs = {d["document_id"] for d in httpx.get(f"{BASE}/api/cases/{CASE}/documents", timeout=30).json()}
    statements_before = len(snap["statements"])

    r = asyncio.run(with_session(keys[CASE], bound_case_calls))
    init = r["init"]
    check("official SDK client completes the Streamable HTTP handshake", init.server_info.name == "mizrahi-touch-mortgage-case",
          f"protocol={init.protocol_version} server={init.server_info.name}@{init.server_info.version}")

    by_name = {t.name: t for t in r["tools"]}
    writes = {"record_customer_statement", "request_banker_handoff", "request_revalidation"}
    annotated = all((by_name[n].annotations.read_only_hint is False) == (n in writes) for n in by_name)
    check("tool catalog: 10 tools, writes annotated as non-read-only", len(by_name) == 10 and annotated, ", ".join(sorted(by_name)))

    overview = r["overview"].structured_content
    same_state = overview["ai_document_readiness"]["state"] == snap["readiness"]["state"]
    same_counts = overview["counts"] == snap["readiness"]["counts"]
    check("get_case_overview matches the app's readiness state and counts", same_state and same_counts,
          f"mcp={overview['ai_document_readiness']['state']} app={snap['readiness']['state']}")

    mcp_open = {i["finding_id"] for i in r["open"].structured_content["items"]}
    app_open = {f["finding_id"] for f in snap["findings"] if f["status"] == "open"}
    check("list_open_items matches the app's open findings", mcp_open == app_open, f"{len(mcp_open)} open findings")

    mcp_docs = {d["document_id"] for d in r["documents"].structured_content["documents"]}
    check("list_documents matches the app's documents", mcp_docs == app_docs, f"{len(mcp_docs)} documents")

    statements_after = len(httpx.get(f"{BASE}/api/cases/{CASE}", timeout=30).json()["statements"])
    refused = r["unconfirmed_write"].is_error and statements_after == statements_before
    check("write without explicit customer confirmation is refused and changes nothing", refused,
          r["unconfirmed_write"].content[0].text if r["unconfirmed_write"].content else "")

    o = asyncio.run(with_session(keys[OTHER], other_case_calls))
    other_docs = {d["document_id"] for d in o["documents"].structured_content["documents"]}
    other_borrowers = {b["borrower_id"] for b in o["overview"].structured_content["borrowers"]}
    check("a key bound to another case sees only that case", not (other_docs & app_docs) and "BRW-A" not in other_borrowers,
          f"borrowers={sorted(other_borrowers)} overlap={len(other_docs & app_docs)}")

    smuggled = raw(keys[CASE], {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                                "params": {"name": "list_documents", "arguments": {"case_id": OTHER}}}).json()
    check("a model cannot name the case (extra arguments are rejected server-side)", smuggled["result"]["isError"] is True,
          smuggled["result"]["content"][0]["text"])

    listing = {"jsonrpc": "2.0", "id": 8, "method": "tools/list", "params": {}}
    bad_key = raw("mcs_not_a_real_key", listing)
    foreign = raw(keys[CASE], listing, Origin="https://attacker.example")
    bad_version = raw(keys[CASE], listing, **{"MCP-Protocol-Version": "1999-01-01"})
    get = httpx.get(f"{BASE}/mcp", timeout=30)
    check("HTTP refusals: invalid key 401, foreign Origin 403, bad protocol 400, GET 405",
          (bad_key.status_code, foreign.status_code, bad_version.status_code, get.status_code) == (401, 403, 400, 405)
          and bad_key.headers.get("www-authenticate") == "Bearer",
          f"{bad_key.status_code}/{foreign.status_code}/{bad_version.status_code}/{get.status_code}")

    failed = [x for x in RESULTS if not x[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "mcp-sdk-results.json").write_text(
        json.dumps([{"check": n, "pass": ok, "detail": d} for n, ok, d in RESULTS], ensure_ascii=False, indent=2), encoding="utf8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

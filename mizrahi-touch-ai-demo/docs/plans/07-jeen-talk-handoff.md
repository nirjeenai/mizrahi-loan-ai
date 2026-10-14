# 07 — JEEN Talk handoff (Mizrahi #2, Round 3)

Status 2026-10-14: the follow-up loop runs end to end against a **simulated** JEEN Talk (`mock-talk`). It never dials.
No live JEEN Talk connection exists. This note is for whoever connects the real one.

## 1. The boundary
`backend/app/comms/contract.py::OutboundProvider` is the only path to a customer contact. Nothing outside `comms/`
knows whether a call is simulated; every attempt records `provider` and `simulated`.

| Piece | File | Today |
|---|---|---|
| Protocol + dataclasses | `comms/contract.py` | final |
| Simulated provider | `comms/mock_talk.py` | `MockTalkProvider`, scripted DIALING → CONNECTED → outcome |
| Live provider | `comms/jeen_talk.py` | stub: `health().ok = False`, every call raises `ProviderNotConfigured` |
| Selection | `comms/registry.py` | `talk.mode`: `simulation` → mock, `off` → none, `live` → the stub |
| Status receiver | `comms/webhook.py::apply` + `followup/orchestrator.py::handle_talk_event` | dedupe, forward-only ranks, orphans |
| HTTP receiver | `POST /api/webhooks/jeen-talk` (`api/followup.py`) | 404 unless `TALK_WEBHOOK_SECRET` is set; then `X-Talk-Secret` must match |

**When a call is placed.** Only the orchestrator's pre-dispatch gate creates an attempt. In one `db.tx()` it re-reads
the case, re-evaluates `followup/policy.py`, and inserts the attempt with its idempotency key and upload link. The
provider is called only after the commit. The kill switch is checked again just before the call, and an attempt
already past that point is cancelled best-effort (`TOO_LATE_TO_CANCEL` is recorded).

## 2. Request contract (`CallRequest`)
| Field | Value |
|---|---|
| `idempotency_key` | `case:{case_id}:plan:{plan_version}:tasks:{sha256(sorted task ids)[:12]}` (+`:manual:{n}` for a banker's call). **Talk must dedupe on it.** |
| `client_reference` | the attempt id (`ATT-…`); every status event must echo it |
| `case_ref` | the case id (opaque to Talk) |
| `contact_ref` | an opaque contact token (`TEST-LINE-01` in the demo). The phone number is resolved only on the telephony side and never sent from here. |
| `locale` | `he-IL` |
| `prompt_version` | the published `talk_prompt` label, e.g. `talk_prompt@v2` (edited in Admin › Customize Prompt) |
| `variables` | `first_name`, `missing_documents[]` (customer wording), `secure_upload_link`, `next_step` |
| `allowed_actions` | `send_link`, `mark_no_answer`, `request_human`, `schedule_callback` |
| `requires_identity_verification` | `true`: Talk verifies identity; the outcome reports `identity_verified` |
| `context_tool` | `get_followup_context` (the MCP tool, wired at G5) |
| `callback_url` | `None` today; set to the public receiver URL when live |
| `expires_at` | the link's expiry (`talk.link_ttl_minutes`) |

The payload never holds an ID number, amount or document content. On the attempt row the link is stored redacted
(`[secure-link]`), and the token itself is kept only as a SHA-256 in `upload_links`. `send_message` (`MessageRequest`)
has the same shape for the message channel.

## 3. Response and status contract
- `create_call` → `ProviderAck{provider_call_id, status, accepted_at}`. It must be idempotent on `idempotency_key`.
- `cancel_call` → `CANCELED | TOO_LATE_TO_CANCEL | NOT_FOUND`. `get_call` → `CallState{status, sequence,
  updated_at, outcome?, data}`; reconciliation uses it for attempts stuck in `UNKNOWN`.
- **Status event** (posted to the receiver, or returned by `get_call`):
  `{event_id, event_type: "call.status_changed", client_reference, provider_call_id, sequence, status, outcome?,
  occurred_at, data: {link_sent?, callback_at?, identity_verified?}}`.
  - `status` ∈ `QUEUED, DISPATCHING, DIALING, CONNECTED, UNKNOWN, CANCEL_REQUESTED, CANCEL_FAILED, COMPLETED,
    NO_ANSWER, FAILED, CANCELED`, with ranks in `followup.contract.ATTEMPT_RANK`.
  - `outcome` ∈ `LINK_SENT, CALLBACK_REQUESTED, REFUSED, HUMAN_REQUESTED, NO_ANSWER, IDENTITY_FAILED,
    COMPLETED_NO_ACTION`.
- **Receiver results:**
  - a duplicate `event_id` → `duplicate`;
  - a lower or equal rank, or anything after a final status → `ignored`;
  - an unknown `client_reference` → `orphan` (HTTP 202 + `integration.reconciliation_required.v1`);
  - otherwise `applied`.
- **What each outcome does:**

  | Outcome | Effect |
  |---|---|
  | `LINK_SENT` | plan and tasks go to AWAITING_CUSTOMER |
  | `CALLBACK_REQUESTED` | a callback at `data.callback_at`, still inside the call window and the bank's 4-hour spacing |
  | `REFUSED` | voice opt-out for the case |
  | `HUMAN_REQUESTED` | escalation to the banker |
  | `NO_ANSWER` / `IDENTITY_FAILED` / `FAILED` | back to waiting, then the next attempt within the caps (escalation when they are used up) |

## 4. What the mock shows today
Through the demo controls (`/api/demo/*`, demo only, labelled "סימולציה"):
1. the customer leaves;
2. the clock moves past grace;
3. the tick schedules the call and runs the gate;
4. the mock goes DIALING → CONNECTED → `LINK_SENT` (or any outcome picked via `talk-outcome`);
5. `sent-links` shows the link, and redeeming it opens a session for that case only;
6. a corrected upload that passes review resolves the task, the plan completes, and the case is ready for the banker.

Covered by `tests/test_followup_flow.py`, `test_talk_webhook.py` and `test_upload_links.py`.

## 5. What remains for a real integration
1. **`JeenTalkProvider`** against JEEN Talk's API: auth, `create_call` / `cancel_call` / `get_call` /
   `send_message`, timeouts, and error mapping (a provider error → `FAILED`; the back-off constant is
   `comms.contract.RETRY_BACKOFF_MINUTES`). `health()` should reflect real reachability.
2. **Receiver security** per JEEN Talk's actual spec (signature, timestamp window, key rotation), replacing the
   shared-secret check. `apply` stays as it is.
3. **Configuration:** `JEEN_TALK_*` credentials and `TALK_WEBHOOK_SECRET` in env only; `callback_url`;
   `PUBLIC_BASE_URL` for the upload link; a contact allowlist (`TALK_LIVE_ALLOWLIST`) before any live dial.
4. **Live switch:** `talk.mode = live` in a published policy. In the demo environment `HG-LIVE-DIAL-DEMO` still blocks
   every dial, so a non-demo environment (`APP_ENV`) is required. The Admin publish gate also refuses a live-mode draft
   in the demo, because the hard-guard scenarios then block.
5. **Prompt delivery:** Talk reads the published `talk_prompt` (locked AI-disclosure opening, `{{variables}}` only)
   by `prompt_version`.
6. **MCP `get_followup_context`** for in-call refresh (G5), and a test call against a JEEN sandbox number.
7. **Identity verification and link landing:** done Talk-side; the app has no identity screens. The
   `/customer/link` landing page is Agent A's at G5.

Not needed for the connection: changes to the evaluator, the gate, the tables or the follow-up API.

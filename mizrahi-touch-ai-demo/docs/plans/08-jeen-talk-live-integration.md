# JEEN Talk × Mizrahi Loans — Live Integration Handoff

Status: 2026-10-14. The follow-up loop already runs end to end against **simulated** JEEN Talk (`mock-talk`). It never dials. This note is the recommended path to the **real** JEEN Talk platform without rebuilding the Follow-up Engine, Admin, links, or banker UI.

JEEN Talk’s public site and console (`https://talk.jeenai.app/`) confirm agents, SIP telephony, webhooks, and connectors. They do **not** publish OpenAPI. Endpoint names below are a mapping onto our existing `OutboundProvider` contract, not invented URLs. Do not implement against guessed paths.

The contract the mock already exercises is in `docs/plans/07-jeen-talk-handoff.md`. This document is the live-integration plan on top of that boundary.

---

## Architecture

```text
Customer app (source of truth: cases, docs, tasks)
        ↓
Follow-up Engine (whether / when)     ← Admin policy. Do not change.
        ↓
Pre-dispatch gate (mint link, attempt, idempotency)
        ↓
OutboundProvider
   simulation → MockTalkProvider     ← keep for regression
   live       → JeenTalkProvider     ← implement
        ↓
JEEN Talk Voice Agent (how to speak)
   per-call variables + published prompt
   tools: send_link / request_human / schedule_callback / get_followup_context
        ↓
Webhook → existing webhook.apply → tasks / timeline / banker
```

### Split of authority

| Layer | Owner | Examples |
|---|---|---|
| Whether / when to dial | This app, in code | consent, kill switch, window, caps, `HG-LIVE-DIAL-DEMO` |
| How the conversation runs | JEEN Talk agent | Hebrew voice, barge-in, identity check, wording |
| What this customer needs | Per-call payload | `first_name`, `missing_documents`, `secure_upload_link` |
| What happened | Canonical webhook | `LINK_SENT`, `HUMAN_REQUESTED`, … |

The LLM prompt must never grant a call. Admin already says this on the Prompt tab: instructions control *how* the agent speaks, not *when* we call.

Do not confuse two stubs:

- `backend/app/comms/jeen_talk.py` — **outbound follow-up calls** (this task).
- `frontend/src/voice.ts` `JeenTalkVoice` — **in-app browser STT/TTS**. Leave it alone.

---

## 1. What is already working (do not touch)

The mock path already runs the real receiver. `MockTalkProvider` never dials; `tick` advances DIALING → CONNECTED → outcome and posts the same event body live Talk will post.

Leave these systems as-is:

- Follow-up engine, presence, grace, windows, holidays, caps, consent, opt-out, kill switch
- Pre-dispatch gate, idempotency, attempt rows, task/plan state machine
- Secure upload links and `/customer/link`
- `OutboundProvider` protocol and `talk.mode` selection
- `webhook.apply` (dedupe, forward-only ranks, orphans)
- MCP `get_followup_context`
- Banker pause / resume / call-now
- Admin drafts, publish, lint, preview, versions, rollback
- Mock Talk + REPLAY E2E (`e2e/test_followup_journey.py`)

Seed policy (Admin values, not integration constants): 20-minute grace, `in_app` then `voice`, Sunday–Thursday 09:00–18:00, `talk.mode = simulation`.

Key files that already define the boundary:

| Area | File |
|---|---|
| Provider contract | `backend/app/comms/contract.py` |
| Existing mock | `backend/app/comms/mock_talk.py` |
| Live adapter (stub) | `backend/app/comms/jeen_talk.py` |
| Provider selection | `backend/app/comms/registry.py` |
| Incoming webhook | `backend/app/comms/webhook.py` |
| Follow-up orchestration | `backend/app/followup/orchestrator.py` |
| HTTP receiver | `backend/app/api/followup.py` |
| Policy schema | `backend/app/policy/schema.py` |
| Prompt rendering | `backend/app/policy/prompts.py` |
| Seed policy | `backend/policy/seed/loan_policy.demo.json` |
| Seed voice prompt | `backend/policy/seed/talk_prompt.demo.json` |
| Prior handoff | `docs/plans/07-jeen-talk-handoff.md` |

---

## 2. Recommended JEEN Talk architecture

JEEN Talk is an **agent platform** (voice + chat, SIP into existing telephony, APIs/webhooks/connectors). Treat it as a configured Hebrew voice assistant you *trigger*, not a dumb TTS dialer.

**One dedicated sandbox assistant**, e.g. `mizrahi-loan-completion-sandbox`:

- Hebrew voice, barge-in, locked AI-disclosure opening
- Tools only: `send_link`, `request_human`, `schedule_callback`, `get_followup_context`
- No sales, no credit terms, no verbal document contents / passwords / ID numbers
- Human transfer target = banker queue (or a test SIP destination)
- Outbound from a **test CLI / sandbox DID** only

**Per-call, not per-assistant:** customer variables, attempt id, opaque `contact_ref`, `prompt_version`, upload link, webhook callback, allowed actions.

### Prompt source of truth

Pick this order:

1. **Preferred:** per-call instruction override. On `create_call`, send `opening_locked + instructions` from the published `talk_prompt` (label already on `CallRequest.prompt_version`, e.g. `talk_prompt@v2`). Admin publish takes effect on the *next* call. No second prompt editor in Talk.
2. **Fallback:** if Talk only stores prompt on the assistant, hook `store.publish` / `store.rollback` for `talk_prompt` and PATCH that assistant. Rollback already publishes a new version, so Talk follows the same history.
3. **Reject:** editing the prompt in the Talk console independently.

Static assistant config (voice, SIP, tool schemas, transfer target) stays in Talk. Dynamic copy and variables stay in this app.

### Tools (functions), not free-text outcomes

The gate already mints the upload link. Talk must **send that URL**, not invent one.

| Talk tool | Effect here |
|---|---|
| `send_link` (SMS/WhatsApp/in-band, using `variables.secure_upload_link`) | outcome `LINK_SENT` |
| `schedule_callback` + ISO time | `CALLBACK_REQUESTED` + `data.callback_at` |
| `request_human` | `HUMAN_REQUESTED` |
| customer refusal | `REFUSED` (voice opt-out) |
| identity fails | `IDENTITY_FAILED` |
| no-answer / busy | status `NO_ANSWER` |
| hang-up after verify, no tool | `COMPLETED_NO_ACTION` |

### In-call context

Do not mint a new MCP key per call (keys are static: `MCP_DEMO_KEY` → case 001). Prefer an HTTP tool that Talk calls with `client_reference` (attempt id), wrapping existing `get_followup_context`. Wire MCP later if Talk is an MCP client.

### Phone numbers

Phone numbers never leave this app. Cases carry `phone_ref: "TEST-LINE-01"` (`backend/app/bank/mock_bank.py`). Talk/telephony resolves that token. The adapter may map allowlist env → E.164 only if JEEN’s API requires a number.

---

## 3. Exact JEEN Talk setup required

Until JEEN shares the private API spec, this is the console/ops checklist — not invented paths.

**Workspace:** sandbox org at `https://talk.jeenai.app/` (not production).

**Assistant:** one Hebrew loan-completion agent. System prompt = locked opening + Admin instructions; variables `{{first_name}}`, `{{missing_documents}}`, `{{secure_upload_link}}`, `{{next_step}}`.

**Telephony:** sandbox outbound CLI; SIP as JEEN documents; destination = JEEN-approved test handset only.

**Credentials (env only, never Admin/DB):** base URL, API key, assistant id, optional messaging sender, webhook signing secret. Names TBD from JEEN (`JEEN_TALK_*` in `.env.example`).

**Webhook:** Talk → `POST {PUBLIC_BASE_URL}/api/webhooks/jeen-talk`. Today that route is **404 unless `TALK_WEBHOOK_SECRET` is set**, then it checks `X-Talk-Secret`. Replace verification with JEEN’s real scheme; keep `webhook.apply` unchanged.

**Identity:** Talk-side only (no ID screens here). Sandbox: confirm first name. Production method needs bank legal approval. `CallRequest` must not grow ID/amount/document fields.

**Test phone:** one allowlisted number mapped from `TEST-LINE-01`.

---

## 4. How Admin settings control Talk

| Admin control | Where it lives | How Talk sees it |
|---|---|---|
| Auto follow-up, grace, idle, presence TTL | `followup.*` | Never sent. Engine decides dispatch. |
| Channel order, window, holidays, caps, spacing | `followup.*` | Never sent. |
| Consent / opt-out | preferences + hard guards | Never sent. |
| Kill switch | `flags.KILL_SWITCH` | Cancels in-flight via `cancel_call`; not a Talk setting. |
| `talk.enabled` / `talk.mode` | policy | `registry.active`: `simulation`→mock, `off`→none, `live`→`JeenTalkProvider`. |
| `link_ttl_minutes` | policy | Link expiry on the attempt; `expires_at` on `CallRequest`. |
| `reconcile_after_minutes` | policy | `tick` → `get_call` for `UNKNOWN`. |
| `max_provider_errors` | policy | Engine backoff; map Talk 5xx → `FAILED`. |
| Locked opening + instructions | published `talk_prompt` | Per-call override (or publish-hook PATCH). |
| `{{variables}}` | prompt + templates | Call payload. |
| `link_message` / `reminder` / … | policy templates | `send_message` / Talk messaging, not the voice prompt. |
| Publish / rollback | `policy/store.py` | Next call uses new `prompt_version`. |

**Demo hard stop:** `talk.mode=live` + `APP_ENV=demo` → `HG-LIVE-DIAL-DEMO`. Flipping Admin to Live on `:8791` will **not** dial. Sandbox E2E needs `APP_ENV=staging` (or `prod`) and a published policy with `talk.mode=live`. Simulation is schema-forbidden outside demo.

`callback_url` is still `None` in `orchestrator._gate`. Live must set it to the public webhook URL.

---

## 5. Files to modify (minimal)

### Implement (core)

| File | Change |
|---|---|
| `backend/app/comms/jeen_talk.py` | Real adapter: auth, timeouts, error mapping, `create_call` / `cancel_call` / `get_call` / `send_message` / `health` / `capabilities`, JEEN↔canonical event map, idempotency on `idempotency_key`. |
| `backend/app/comms/webhook.py` | Add JEEN signature verifier. **Do not change `apply`.** |
| `backend/app/api/followup.py` | Use that verifier instead of only `X-Talk-Secret`. Still call `handle_talk_event`. |
| `backend/.env.example` | `JEEN_TALK_*`, `TALK_WEBHOOK_SECRET`, `PUBLIC_BASE_URL`, `TALK_LIVE_ALLOWLIST`, `APP_ENV`. Never commit real keys; never read `backend/.env`. |

### Small wiring

| File | Change |
|---|---|
| `backend/app/followup/orchestrator.py` | Set `callback_url`; optional allowlist check before `create_call`. Do not change gate/evaluator. |
| `backend/app/api/routes.py` | `/system` Talk row: LIVE+healthy vs stub vs simulation. Update `tests/test_g5_wiring.py`. |
| `backend/app/policy/store.py` | Only if Talk has no per-call prompt: after `talk_prompt` publish/rollback, PATCH assistant. |
| `frontend/src/pages/admin/FollowupTab.tsx` | Drop “live slot not configured” once `health().ok`. |

### Tests to add (keep mock tests)

- `backend/tests/test_jeen_talk_adapter.py` (HTTP mocked)
- Extend `tests/test_talk_webhook.py` for JEEN signatures
- Allowlist + `APP_ENV=staging` policy tests

### Do not change

`followup/policy.py` rules, `comms/contract.py` protocol, `comms/mock_talk.py`, customer/banker UX, Gemini review, frontend `JeenTalkVoice`.

### Contract mapping (once JEEN names are known)

| Our method | Typical Talk primitive |
|---|---|
| `create_call` | Create/start outbound session on the assistant; pass variables + `client_reference`; **must dedupe `idempotency_key`** |
| `cancel_call` | Hang up / cancel queued dial → `CANCELED` / `TOO_LATE_TO_CANCEL` / `NOT_FOUND` |
| `get_call` | GET session (reconciliation) |
| `send_message` | WhatsApp/SMS if Talk has it; else capability `send_message=False` and keep `message` out of `channel_order` |
| `health` | Talk health or authenticated ping |
| Webhook | Native events → canonical `call.status_changed` then `apply` |

Canonical statuses already in `ATTEMPT_RANK`: `QUEUED` … `CONNECTED` … finals `COMPLETED` / `NO_ANSWER` / `FAILED` / `CANCELED`. Map JEEN ringing/answered/ended onto those; do not invent new statuses.

### Sample outgoing `CallRequest`

Already built in `orchestrator._gate`:

```json
{
  "idempotency_key": "case:DEMO-MTZ-2026-001:plan:3:tasks:a1b2c3d4e5f6",
  "client_reference": "ATT-…",
  "case_ref": "DEMO-MTZ-2026-001",
  "contact_ref": "TEST-LINE-01",
  "locale": "he-IL",
  "prompt_version": "talk_prompt@v2",
  "variables": {
    "first_name": "עידו",
    "missing_documents": ["תלוש שכר לספטמבר 2026"],
    "secure_upload_link": "https://<PUBLIC_BASE_URL>/customer/link#t=<token>",
    "next_step": "אחרי ההעלאה נבדוק את המסמך ונעדכן אותך באפליקציה"
  },
  "allowed_actions": ["send_link", "mark_no_answer", "request_human", "schedule_callback"],
  "requires_identity_verification": true,
  "context_tool": "get_followup_context",
  "callback_url": "https://<PUBLIC_BASE_URL>/api/webhooks/jeen-talk",
  "expires_at": "2026-10-15T12:00:00+00:00"
}
```

### What `apply` already expects

After the adapter translates JEEN’s payload:

```json
{
  "event_id": "jt-evt-…",
  "event_type": "call.status_changed",
  "client_reference": "ATT-…",
  "provider_call_id": "jt-call-…",
  "sequence": 3,
  "status": "COMPLETED",
  "outcome": "LINK_SENT",
  "occurred_at": "2026-10-14T12:04:00+00:00",
  "data": { "link_sent": true, "identity_verified": true }
}
```

Duplicates → `duplicate`; stale rank → `ignored`; unknown attempt → `orphan` (HTTP 202).

---

## 6. Missing from JEEN (blocker list)

Public docs do not include API paths, auth, or webhook schema. Obtain before writing the adapter:

1. Sandbox base URL and auth (API key / OAuth / HMAC).
2. OpenAPI or examples: create outbound call, cancel, get status, send message.
3. Whether **per-call system prompt** is supported; if not, assistant update API + versioning.
4. Variable injection syntax (`{{first_name}}` vs other).
5. Function/tool schema + how tool results become post-call fields.
6. Webhook: events, retries, signature, timestamp window, key rotation.
7. Idempotency header/field for `idempotency_key`.
8. How `contact_ref` maps to a number (Talk-side directory vs we send E.164).
9. Hebrew voice + barge-in + SIP/CLI for sandbox.
10. Approved test DID and destination; messaging channel for `send_link`.
11. Identity-verification options Talk already supports.
12. Human-transfer destination for `request_human`.
13. MCP-client vs HTTP tools for `get_followup_context`.
14. Sandbox vs production isolation (assistant ids must not be shared).

Also locally: `PUBLIC_BASE_URL` reachable by Talk (tunnel for laptop), `TALK_WEBHOOK_SECRET` / JEEN signing secret, `TALK_LIVE_ALLOWLIST`, `APP_ENV=staging`. Do not enable live on the user’s `:8791` demo.

`backend/.env.example` currently has Gemini / MCP / VisionTrace only. `JeenTalkProvider` still raises `ProviderNotConfigured`.

---

## 7. Fastest sandbox E2E

Keep mock tests green first:

```bash
cd mizrahi-touch-ai-demo/backend
.venv/bin/python -m pytest -q tests/test_followup_flow.py tests/test_talk_webhook.py tests/test_upload_links.py
```

Then:

1. Isolated stack (`DATA_DIR` + ports 8792–8799), **not** `:8791`. `APP_ENV=staging`, Gemini off if you are only testing Talk.
2. Set `PUBLIC_BASE_URL`, Talk creds, webhook secret, allowlist `TEST-LINE-01=<sandbox E.164>`.
3. Publish policy: `scope.environment=staging`, `talk.mode=live`, `talk.enabled=true`.
4. Confirm `JeenTalkProvider.health().ok` and `/system` shows live, not “never dials”.
5. Open a case with a missing document, leave the portal, wait grace (or banker **call now** inside the window).
6. Answer the test phone: disclosure → identity → missing doc → agree to link.
7. Talk sends the existing URL → webhook `COMPLETED` + `LINK_SENT` → plan `AWAITING_CUSTOMER`.
8. Open `/customer/link#t=…`, upload correction → task resolved → banker updated.

If JEEN has no outbound API yet, stop after a mocked adapter + webhook translator; do not fake live dials in `mock_talk`.

**Do not** turn on unrestricted customer dialing, point anything at Mizrahi #1 `:8790`, or treat Admin `live` on the demo app as a real call.

---

## Implementation order

1. **Platform discovery** — obtain the JEEN items in §6.
2. **Contract mapping** — fill the table in §5 with real Talk names.
3. **Sandbox adapter** — implement `JeenTalkProvider` + webhook signature; keep mock path.
4. **Admin sync** — per-call prompt override, or publish-hook if Talk requires it.
5. **E2E** — missing document → eligible call → Hebrew conversation → link sent → corrected upload → task resolved.

Reuse existing tests. Keep code changes in the communication adapter and minimal related wiring.

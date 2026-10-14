# 03 — PRD Gap Analysis (JEEN Loan Completion Agent PRD v1.2)

Status per requirement: **Exists** (verified in code) · **Adapt** · **New** · **Deferred** (with reason).

## 1. Functional requirements coverage

| ID | Requirement | Status today | Resolution | Round |
|---|---|---|---|---|
| FR-01 | Clone without breaking mortgage | #2 is a copy; #1 untouched | isolation fixes (port, cookies, e2e defaults) | 1 |
| FR-02 | Requirements from config | hard-coded in `mock_bank.py` | versioned policy config + requirement engine | 1 |
| FR-03 | Upload + version history | Exists (`replaces_document_id`, `REPLACED`) | reuse | — |
| FR-04 | Classification + type/readability/period checks | Exists for payslips | per-family rubrics | 2 |
| FR-05 | Missing vs wrong vs undetermined | Exists (verdicts, NEEDS_REVIEW) | map to PRD statuses | 1–2 |
| FR-06 | One open completion task per issue | New | `completion_tasks` UNIQUE(case, requirement, reason, open) | 3 |
| FR-07 | In-app correction before escalation | Partly (deep links) | policy self-service-first | 3 |
| FR-08 | Talk with minimal context | New | `CallRequest` contract | 3 |
| FR-09 | Status from callbacks to banker | New | signed webhook → attempt state → timeline | 3 |
| FR-10 | Focused link upload + re-check | Deep links exist | `upload_links` | 3 |
| FR-11 | Duplicate prevention / cancellation | Job idempotency exists | contact plan idempotency, event dedupe, pre-dispatch gate | 3 |
| FR-12 | Escalation | Exists (handoffs, NEEDS_BANKER_REVIEW) | wire task ESCALATED | 3 |
| FR-13 | Evidence viewer | Exists | per-family fields | 2 |
| FR-14 | Manual call (P1) | New | banker action through same guards | 3 |
| FR-15 | Governance / FinOps (P1) | ledger exists | ops panel from real events | 5 |
| FR-16 | Preparation recommendation without credit decision | Exists (confirm preparation) | loan copy | 1 |
| FR-17 | Attempts and windows | New | policy keys | 3 |
| FR-18 | Deterministic policy engine with rule ids | New | `followup/policy.py` | 3 |
| FR-19 | Presence, grace, return | New | presence API + hook | 3 |
| FR-20 | Atomic pre-dial check | New | gate in one `tx()` | 3 |
| FR-21 | Consent, hours, opt-out, snooze, caps | New | hard guards | 3 |
| FR-22 | Banker "why/when" | New | Talk card | 3 |
| FR-23 | Channel preference, consolidation, nudges (P1) | New | contact plan per case; in-app nudge; channel order | 3 |
| FR-24 | Admin Settings in existing frontend | New | `/admin` in console shell | 4 |
| FR-25 | Structured follow-up editor | New | form tab | 4 |
| FR-26 | Customize Prompt | New | prompt registry + preview + test | 4 |
| FR-27 | NL policy → proposal only (P1) | New | Gemini JSON patch + diff, never publishes | 4 |
| FR-28 | Simulator | New | `policy/simulator.py` + scenarios | 4 |
| FR-29 | Draft/Publish/Version/Rollback/Audit | New | `config_versions` | 4 |
| FR-30 | Hard guardrails | New | locked rules in evaluator | 3 |
| FR-31 | Multi-month, multi-applicant, conditional | Partly (payslip months, 2 borrowers) | requirement instances | 1–2 |
| FR-32 | Network/provider failure, out-of-order callbacks | New | UNKNOWN, reconcile job, ordered statuses | 3 |
| FR-33 | Customer pause / human / channel preference | handoff tool exists | customer controls + tools | 3 |
| FR-34 | Policy/prompt version on events | run records versions | pin on decisions and attempts | 3 |
| FR-35 | Demo/Prod separation | `DEMO_IDENTITY` | `APP_ENV`, banner, live mode refusal | 3–4 |
| FR-36 | Consistent next-step preview | Exists (customer_status) | derived case status | 1 |
| FR-37 | Templates, translations, SLA (P1) | New | Hebrew templates versioned; other languages deferred | 4 |

## 2. Ambiguities and conflicts — resolutions

| # | Issue in PRD | Resolution |
|---|---|---|
| A1 | FR-01 "mortgage keeps working" vs. transforming #2 | User decision: replace in #2; #1 is the mortgage demo |
| A2 | Example "April vs May" | `SIMULATION_DATE=2026-10-12` → required months 2026-07/08/09; examples use Aug/Sep |
| A3 | `CaseStatus` vs existing readiness states | keep readiness states (banker confirmation semantics); expose derived `case_status` (mapping in 04 §4) |
| A4 | Task status listed as a linear chain | explicit transition table; exits ESCALATED/CANCELED/EXPIRED/PAUSED_* from any open state |
| A5 | `max_attempts_per_case` and `max_attempts_per_case_per_day` both appear | two keys plus `max_attempts_per_customer_per_day` across cases |
| A6 | "suppression while active" shown as config yet "not overridable" | locked hard guard, displayed read-only in Admin |
| A7 | `approved_message` channel without a messaging provider | same `OutboundProvider.send_message`, simulated |
| A8 | Identity verification during a call (§8.3) | Talk-side; contract flag `requires_identity_verification=true`; mock reports `identity_verified` outcome |
| A9 | Presence events `evaluation_started/finished` from the client | server derives from jobs (authoritative); client sends only UI facts |
| A10 | FR-27 is P1 but the brief requires NL proposals | implemented in Round 4, proposal-only |
| A11 | "Ready for banker" with open banker findings | `READY_FOR_BANKER` only when no open banker items; otherwise `HUMAN_REVIEW` |
| A12 | Demo clock vs real contact hours | audited demo clock offset in demo env only; UI labels "זמן מדומה" |
| A13 | Rollback "restores behavior" | rollback publishes a new version copying an old config; history immutable |
| A14 | Kill switch vs active call | stops new dispatches, cancels queued plans; dispatched → `cancel_call` if supported else `TOO_LATE_TO_CANCEL` |
| A15 | Requirement changes during an active case | pinned `requirement_set_version` per case; explicit banker "apply new requirements" action re-pins (audited) |

## 3. UX gaps found
- No way for the customer to say "I'm handling it" / "not now" / "don't call" → DocumentCheckCard controls + chat tools.
- Customer never sees that a link was sent → home update "שלחנו לך קישור" + link landing page.
- Expired/used link → dedicated landing state with "בקשו קישור חדש" (subject to policy).
- Banker cannot tell "no call because active" from "no call because blocked" → decision + `blocked_by` in Hebrew.
- Admin needs to see which fields are locked → lock icon + reason on hard guards.

## 4. Architectural risks
- Generalizing readiness (many consumers: home card, banker queue, outcomes, agent tools) → payslip logic unchanged,
  new families added beside it; tests per family.
- Scheduler on the same 3 workers as reviews → follow-up jobs are cheap and claimed after document jobs.
- Webhook from the mock must not be a shortcut → the mock posts signed HTTP-shaped payloads to the same handler.
- Clock offset leaking into review dates → offset only in `clock.now()`; `SIMULATION_DATE` stays for months.

## 5. Policy scenario catalogue

Columns: trigger · context · decision · action · customer · banker · recovery · test id
(`backend/tests/test_followup_policy.py` and simulator fixture `backend/policy/scenarios/*.json`).

| # | Trigger | Context | Decision | Action | Customer sees | Banker sees | Recovery | Test |
|---|---|---|---|---|---|---|---|---|
| S01 | wrong doc, customer on same screen | presence ACTIVE | IN_APP_ONLY | task IN_APP_PROMPTED | correction CTA | "הלקוח פעיל — מתקן מסמך" | — | P01 |
| S02 | file picker open / upload running / evaluation running | active_upload or job in flight | SUPPRESS | none | progress | "בהעלאה/בדיקה — אין שיחה" | re-evaluate on evaluation finish | P02 |
| S03 | browsing elsewhere in app | ACTIVE elsewhere | WAIT_FOR_INACTIVITY | none | CTA remains | "הלקוח עדיין בפורטל" | — | P03 |
| S04 | idle on page ≥ nudge minutes | IDLE | IN_APP_NUDGE | nudge flag | "צריך עזרה?" banner | "ממתין לתגובה בפורטל" | — | P04 |
| S05 | session ended / heartbeat expired | ENDED/UNKNOWN | START_GRACE | plan WAITING, next_eligible_at = last_activity + grace | — | "הלקוח לא פעיל — בדיקת Follow-up" | — | P05 |
| S06 | grace elapsed, open verified issue, no blocks | all guards pass | SCHEDULE_CALL | plan SCHEDULED → gate → dispatch | — | "שיחה מתוכננת · [מועד]" | — | P06 |
| S07 | customer returns before dial | presence ACTIVE | CANCEL_OR_DEFER | plan back to WAITING | CTA | "שיחה נדחתה — הלקוח חזר" | new grace on leave | P07 |
| S08 | corrected upload passes | task resolved | RESOLVE_AND_CANCEL | cancel plan | success | "הושלם — שיחות נוספות בוטלו" | — | P08 |
| S09 | new upload still evaluating | job in flight | HOLD_UNTIL_EVALUATED | none | "בודקים את המסמך" | "המתנה לבדיקה" | — | P09 |
| S10 | upload during dial | attempt DISPATCHING/CONNECTED | RECHECK_BEFORE_DIAL / refresh | context refresh via MCP | updated status | "המסמך עודכן תוך כדי שיחה" | — | P10 |
| S11 | quiet hours / Shabbat / holiday | outside window | BLOCK_OR_RESCHEDULE | next window | — | "מתוזמן לפי מדיניות" | — | P11 |
| S12 | no consent / opt-out / unverified contact | consent invalid | BLOCK | banker task | — | "פנייה חסומה — אין הרשאת קשר" | banker handles | P12 |
| S13 | customer snooze | snooze_until | SNOOZE | defer | "נזכיר לך ב-…" | "השהיה לבקשת הלקוח" | auto-resume | P13 |
| S14 | several missing documents | ≥2 open tasks | CONSOLIDATE | one plan, N tasks | one list | "טיפול מאוחד ב-N דרישות" | — | P14 |
| S15 | UNDETERMINED / low confidence | task reason unverified | HUMAN_REVIEW | no contact | "בבדיקה" | "נדרשת בדיקה אנושית" | banker decides | P15 |
| S16 | network loss | heartbeat stale, no session_ended | UNKNOWN → conservative grace | wait grace ×1 | — | "נוכחות לא ודאית" | recheck | P16 |
| S17 | two tabs / two devices | any session ACTIVE | SUPPRESS | none | — | "פעיל במכשיר אחר" | — | P17 |
| S18 | opt-out after scheduling | consent changed | CANCEL | plan CANCELED | confirmation | "בוטל — opt-out" | — | P18 |
| S19 | duplicate / out-of-order callbacks | event already processed or lower rank | IGNORE (idempotent) | none | — | unchanged | — | W01–W03 |
| S20 | provider timeout | attempt UNKNOWN | RECONCILE | `get_call` job, no redial | — | "סטטוס שיחה לא ידוע — מבררים" | reconcile → final | W04 |
| S21 | attempts exhausted | attempts ≥ max | ESCALATE | task ESCALATED, handoff | "נציג יחזור אליך" | "הועבר לבנקאי" | banker | P19 |
| S22 | customer asked for a banker | HUMAN_REQUESTED | ESCALATE | handoff | confirmation | handoff queue | — | P20 |
| S23 | banker paused follow-up | override PAUSED_BY_BANKER | BLOCK | none | — | "הושהה ע״י בנקאי" | banker resume | P21 |
| S24 | banker manual call during opt-out | guards fail | BLOCK | 409 with reason | — | "חסום: opt-out" | — | P22 |
| S25 | kill switch | flag on | BLOCK | queued plans canceled | — | "אוטומציה מושבתת" | admin re-enable | P23 |
| S26 | invalid / contradictory config | validation fails at load | FAIL_CLOSED (contact only) | alert event | uploads work | "תצורה לא תקינה — אין פניות" | admin fix | P24 |
| S27 | publish while plans pending | new version | re-evaluate guards under active; no catch-up blast | rate-limited reconcile | — | policy version shown | — | P25 |
| S28 | same customer, two cases | per-customer daily cap | BLOCK/DEFER | — | — | "מכסה יומית ללקוח" | next day | P26 |
| S29 | banker request + AI task on same requirement | both open | MERGE | one task, banker wording | one request | one row | — | T01 |
| S30 | same wrong file re-uploaded | SHA duplicate | NO_CHANGE | task open | "זה אותו קובץ שכבר בדקנו" | — | — | T02 |
| S31 | link opened after resolution | task RESOLVED | — | landing "כבר התקבל" | info | — | — | L01 |
| S32 | link expired / used | token invalid | — | landing "פג תוקף" | request new link | — | policy | L02 |
| S33 | AI review failed / budget exhausted | document failed | BLOCK (unverified) | no contact | "תקלה בבדיקה" | "תקלה — נדרש טיפול" | retry | P27 |
| S34 | customer "כבר שלחתי" in chat | statement recorded | extend grace by config | defer | ack | statement shown | — | P28 |
| S35 | CALLBACK_REQUESTED at time X | outcome | SCHEDULE at X within window | plan SCHEDULED | — | "חזרה מתוכננת" | — | W05 |
| S36 | REFUSED | outcome | voice opt-out for case | plan CANCELED | — | "סירב לשיחה" | message channel only | W06 |
| S37 | case closed/withdrawn | case CLOSED | CANCEL_ALL | — | — | — | — | P29 |
| S38 | Agent prompt says "התקשרו מיד" | lint | WARN, no policy change | — | — | — | admin edits | A01 |
| S39 | calling hours 00:00–23:59 every day | validation | reject beyond bank envelope | — | — | — | — | A02 |
| S40 | simulator run | side_effects=false | — | no DB writes except `simulation_runs` | — | — | — | A03 |
| S41 | co-borrower with 3 payslips each | requirement instances | not READY until all | — | per-person progress | matrix | — | R01 |
| S42 | joint account statement | holder names include both | satisfies both accounts' requirement (config) | — | — | — | — | R02 |

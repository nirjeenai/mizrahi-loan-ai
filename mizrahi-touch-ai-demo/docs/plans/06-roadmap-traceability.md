# 06 — Final Implementation Roadmap and Traceability

## Roadmap

| Round | Delivers | Depends on |
|---|---|---|
| 0 | plans, baseline | — |
| 1 | isolation, loan cases, config-driven requirements, loan copy | 0 |
| 2 | ID / statements / purpose-proof review, intake | 1 (requirement instances) |
| 3 | tasks, presence, policy engine, scheduler, mock Talk, webhook, links, banker visibility | 2 (verified issues per family) |
| 4 | Admin Settings, prompt registry, simulator, versions, RBAC | 3 (evaluator) |
| 5 | scenarios, E2E, failure paths, regression, Talk handoff | 1–4 |

Prerequisites: isolated ports for #2 (backend 8791, Vite 5192); the user's OK for the live recording run in Round 2.
Deferred (external): live JEEN Talk connection and provider configuration; real messaging provider; bank IdP/OTP
behind links; CRM/LOS; non-Hebrew templates; antivirus scanning; encryption at rest; deep ROI analytics.

## Traceability — functional requirements

| PRD | Round | Tests |
|---|---|---|
| FR-01 | 1 | isolation checks (port, cookies), #1 untouched |
| FR-02, FR-31 | 1–2 | `test_requirements.py` |
| FR-03 | existing | `test_featured_demo.py::replacement` |
| FR-04, FR-05, FR-13 | 2 | `test_loan_review.py`, REPLAY suite |
| FR-06, FR-07, FR-10, FR-12 | 3 | `test_followup_flow.py` |
| FR-08, FR-09, FR-11, FR-32 | 3 | `test_talk_webhook.py`, `test_followup_flow.py` |
| FR-14, FR-17–FR-23, FR-30, FR-33, FR-34 | 3 | `test_followup_policy.py` |
| FR-15 | 5 | ops panel smoke |
| FR-16, FR-36 | 1 | `test_readiness.py` |
| FR-24–FR-29, FR-35, FR-37 | 4 | `test_admin_settings.py`, e2e admin |

## Traceability — PRD acceptance criteria (§15)

| AC | Round | Test |
|---|---|---|
| 1 mortgage demo regression | 1 | #1 untouched; #2 regression suite |
| 2 separate environment | 1 | port/cookie/DATA_DIR checks |
| 3–5 VALID / wrong type / uncertainty | 2 | `test_loan_review.py` |
| 6 one task per issue | 3 | `test_followup_flow.py::one_task` |
| 7, 7א–7ז policy | 3 | `test_followup_policy.py` S01–S18 |
| 8–9 callbacks, duplicates | 3 | `test_talk_webhook.py` |
| 10–11 link upload, READY | 3 | `test_followup_flow.py::link_to_ready` |
| 12 escalation | 3 | S21–S22 |
| 13 Talk failure does not block | 3 | W04 |
| 14 no real PII | all | synthetic fixtures, log review |
| 15 browser E2E mobile + desktop | 5 | `e2e/test_loan_completion.py` |
| 16–17 admin RBAC, draft inactive | 4 | `test_admin_settings.py` |
| 18 simulator 18 scenarios | 4 | `test_admin_settings.py::simulate` |
| 19 prompt guardrails | 4 | `test_admin_settings.py::prompt_lint` |
| 20 NL proposal only | 4 | `test_admin_settings.py::proposal` |
| 21 conflict, publish, rollback | 4 | `test_admin_settings.py` |
| 22 policy change mid-flow | 3–4 | S27 |
| 23 document multiplicity | 2 | `test_requirements.py` |
| 24 network/adapter failures | 3 | S16, S19, S20, L02 |
| 25 safety & audit | 3–4 | S12, S24, decision rule ids |

## Recommended first step
Round 1: isolation is a safety blocker (today's defaults target #1), and every later round depends on
config-driven requirement instances and generalized readiness.

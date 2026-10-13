# Mizrahi Tefahot Touch × JEEN: AI mortgage document review (concept demo)

> **A JEEN concept demonstration using synthetic data. It is not an official Mizrahi-Tefahot product and is not connected to any Mizrahi banking environment.** Every person, ID number, employer and amount is invented. The bank's case stage is synthetic demo data. Nothing here is a credit decision or a bank acceptance of a document: a human mortgage banker decides.

The demo extends the existing Tefahot Touch mortgage journey with an AI document-review layer. Customers upload salary slips in the app. Each document is classified, read (including scans), verified value by value against the original file, judged against a versioned rubric, and checked across documents. Customers fix what's missing, and the whole set is re-checked. A Hebrew assistant answers by chat and voice from the same persisted case state, and the banker receives an evidence package and makes the only human decision.

| Customer home (demo start) | Missing September, duplicate August | Verdict, criteria and evidence boxes |
|---|---|---|
| ![](docs/screenshots/00-home-mobile.png) | ![](docs/screenshots/01-documents-gap.png) | ![](docs/screenshots/02-review-evidence.png) |
| **Hebrew chat and voice, one agent** | **Banker findings and the customer's explanation** | **Banker evidence viewer** |
| ![](docs/screenshots/03-chat-voice.png) | ![](docs/screenshots/05-banker-findings.png) | ![](docs/screenshots/06-banker-evidence.png) |
| **Banker review queue: the mislabeled file first** | **Correction request: editable message and preview** | **The customer sees the request in the app** |
| ![](docs/screenshots/14-banker-workspace.png) | ![](docs/screenshots/15-banker-correction-preview.png) | ![](docs/screenshots/16-customer-banker-request.png) |
| **A one-month income comparison, labelled preliminary** | **Closing an inquiry: basis, documents, reason, impact** | **The customer answers an explanation request** |
| ![](docs/screenshots/18-finding-preliminary.png) | ![](docs/screenshots/19-finding-resolve-confirm.png) | ![](docs/screenshots/20-customer-explanation-reply.png) |

---

## Quick start

Prerequisites: Python 3.12, Node 20+, Google Chrome (fixtures and browser tests use the system Chrome through Playwright), and a Gemini API key. macOS `say`/`afconvert` are used only by the voice step of the browser test.

```bash
./run.sh setup     # venv + pinned deps, npm install + build, synthetic PDFs, backend/.env with random MCP keys
#   then put GEMINI_API_KEY into backend/.env
./run.sh start     # API + MCP + built app on http://127.0.0.1:8790
```

| URL | What it is |
|---|---|
| `http://127.0.0.1:8790/customer` | Touch customer app (Hebrew RTL, mobile-first; desktop shows the phone with a side panel of presenter test scenarios and downloadable synthetic documents) |
| `http://127.0.0.1:8790/banker` | Mortgage-specialist review workspace: prioritized queue, original document with evidence, decision panel; secondary views for the conversation and for runs, findings and audit |
| `http://127.0.0.1:8790/system` | Integration matrix (LIVE / LOCAL / DEMO / BLOCKED), Gemini usage ledger, live MCP self-test, rubrics |
| `http://127.0.0.1:8790/mcp` | Mortgage Case MCP server (Streamable HTTP, POST only) |

Other commands: `./run.sh dev` (Vite on :5190 proxying to :8790, with backend reload), `./run.sh test` (unit, browser E2E and MCP checks against a running backend; it resets cases 001, 003 and 005), and `./run.sh reset` (demo case and QA case back to nothing uploaded).

To start a presentation from an already-reviewed case instead of uploading live, run `backend/.venv/bin/python backend/tests/live_journey.py --reset --scene initial`. It uploads the six initial documents through the API, and the review takes about 50 s.

### Demo script (case `DEMO-MTZ-2026-001`, Ido and Noa Lavi, second-hand apartment after preliminary approval)

1. **Home.** Bank stage "קיבלנו החלטה" (2/5, synthetic) in the stage card, the "מה צריך לעשות עכשיו?" card shows "ממתינים להעלאת תלושי שכר" with the required months, and the document summary shows 0 of 6 required payslips, Ido 0/3 and Noa 0/3.
2. **מסמכים → להעלאה.** Upload the six "סט ראשוני" files from the side panel for the borrower each one names. One of Noa's files is a scan with no text layer. The file Ido calls `…2026-09.pdf` actually prints **August**.
3. Each upload shows its live review stages, and then the set is reviewed. Ido: **September missing** and **August ×2**, with a filename-versus-content note. Noa: declared net ₪18,500 against verified payslips averaging ₪16,900 (−8.65%), which goes **to the banker**.
4. Open any document to see the verdict, all 10 rubric criteria, and orange boxes on the original page for every verified value.
5. **עוזר.** Ask "מה עוד חסר לנו ולמה?" by text or microphone. The answer comes from case tools only.
6. Upload `ido_payslip_2026-09_corrected.pdf`. The missing-month finding closes as *resolved by new evidence*, the duplicate becomes informational, and the state moves to "מוכן לבדיקת הבנקאי — עם ממצאים פתוחים". The customer card reads "תלושי השכר הושלמו · נדרש בירור בנקאי" (6 of 6).
7. Tell the assistant Noa has a variable pay component and confirm. The explanation is attached to the finding **as unverified context and does not close it**. Confirm a handoff, and the case enters the banker queue once.
8. **/banker.** The queue opens on what needs a decision. Accept a payslip (**קבלת המסמך**), decide the income finding in "פערים לשיקול דעתך" (request missing payslips or an explanation, close the inquiry after checking with a stated basis, report an AI error, or escalate — each with a reason), and confirm **"אישור הכנת מסמכי השכר"** at the bottom of the queue. None of these is a credit decision, and none touches the bank stage.

**Banker → customer correction loop (instead of step 6).** After step 3, open `/banker`. The file named September is first in the queue with "הקובץ שהועלה עבור ספטמבר מכיל בפועל תלוש של חודש אוגוסט." Press **החזרה לתיקון**: the suggested message reads "שלום עידו, המסמך שהעלית עבור ספטמבר מציג את חודש אוגוסט. כדי להמשיך בבדיקת מסמכי ההכנסה, נא להעלות את תלוש ספטמבר 2026." Edit it, preview it and save it. The customer's home card now reads "בקשה חדשה מדנה כהן". Its button opens the upload sheet preset to the request. Upload `ido_payslip_2026-09_corrected.pdf`: it is reviewed again, the September gap closes, and the new file returns to the banker's queue as "מסמך חלופי", linked to the one it replaced.

The QA case `DEMO-MTZ-2026-003` (pick it in the case selector) takes the four "בדיקת קצה" files: Noa's payslip uploaded as Ido's, an unreadable scan, a payslip containing a prompt-injection instruction, and a payslip with contradictory amounts. None of them may come out VALID.

### Executive demo: PASS · REVIEW · BLOCKER (left pane, "תרחישים מומלצים לדמו")

The top of the left pane is for live presentations. **התחל דמו חדש** wipes the three executive demo cases and nothing else, then opens the first one on the right. Below it are three scenario cards. Each card names what is checked, what to expect, the exact golden-set PDFs to download, the borrower, the case and the upload destination, and the expected result. "איך מציגים" expands the upload order, what the app will show, the presenter's steps and one sentence to say. Downloading changes nothing; the presenter uploads the file on the right.

| Card | Case | Files (golden set) | What the app does |
|---|---|---|---|
| 1 · עובר — "עבר בדיקת AI — ממתין לקבלת הבנקאי" | `DEMO-MTZ-2026-006` (438839006), עידו לוי | `ido_2026_07.pdf`, `ido_2026_08.pdf`, `ido_2026_09_CORRECTED.pdf` | Each payslip VALID with verified values; home "בדיקת תלושי השכר הושלמה" 3/3; the banker accepts in "ממתינים להחלטתך". Acceptance is documentary only. |
| 2 · לבירור בנקאי — "נדרש בירור בנקאי — נמצא פער בהכנסה" | `DEMO-MTZ-2026-007` (438839007), נועה לוי | `noa_2026_07.pdf`, `noa_2026_08.pdf`, `noa_2026_09.pdf` | Each payslip VALID; declared ₪18,500 against a ₪16,900 average over 3 months goes to "פערים לשיקול דעתך" with the comparison, evidence and a suggested question. |
| 3 · חוזר ללקוח — "המסמך אינו מתאים לדרישה — נא להעלות מסמך חלופי" | `DEMO-MTZ-2026-008` (438839008), עידו לוי | optional `ido_2026_07/08.pdf`, then `bank_statement_Jul_Sep_2026.pdf` for September, then `ido_2026_09_CORRECTED.pdf` | The statement is not a payslip: the customer gets "העלאת מסמך חלופי" at once, the banker can't accept it as a payslip. The replacement is reviewed again; the old file stays in history as "הוחלף". |

| Featured scenarios and "התחל דמו חדש" | BLOCKER: replace the rejected file | REVIEW: the banker's comparison | The banker sees the customer's replacement |
|---|---|---|---|
| ![](docs/screenshots/21-exec-featured-panel.png) | ![](docs/screenshots/22-exec-blocker-home.png) | ![](docs/screenshots/23-exec-review-banker.png) | ![](docs/screenshots/24-exec-blocker-replacement.png) |

Screenshots from the REPLAY browser suite (2026-10-13), not from a live Gemini run.

- **Cases.** 006–008 carry one golden-set borrower each (`MockBankAdapter`, flag `executive_demo`), so each scenario has its own case-wide status. Nothing in the bank data says what a review should conclude; the expected labels live in the presenter manifest (`featured`) and are JEEN routing expectations for golden-set facts, not live results.
- **Outcomes.** PASS / REVIEW / BLOCKER are derived on every read by `workflow/outcomes.py` from the document verdict, open findings, the banker's documentary status and the customer status. They are never stored and never written by a model. A human decision wins (accepted, sent back, escalated). A failed check the customer can fix (BLOCKER) comes before a question for the banker (REVIEW). PASS needs a VALID verdict with nothing open on the document. The customer sees the label on the document page and in the upload sheet. The banker workspace returns the same value per document.
- **Start a new demo.** `POST /api/presenter/demo-reset` (`workflow/demo.py`) deletes every case-scoped row of 006–008 in one transaction, together with their uploaded files and page renders. It writes one global audit record and leaves every other case, the Gemini ledger, rubrics and fixtures alone. While a review of these cases is running it answers 409 and the button waits and retries. It is off with `DEMO_RESET=0`. Worker guards make a review that finishes after any reset write nothing, so no ghost events.

### Presenter test scenarios (left pane, "כל תרחישי הבדיקה")

On desktop (≥ 901 px), the left pane keeps all technical scenarios in "כל תרחישי הבדיקה", collapsed by default below the featured scenarios. The pane scrolls on its own, so the live app on the right stays in place. Inside is an accordion of the 10 curated golden-set scenarios, "קבצים משלימים" and the Lavi file set for cases 001/003. Expected reason codes, statuses and each file's Expected Output are under "פרטים טכניים". Each scenario shows:

- its goal and prerequisites (start clean, continue after 01, or isolated QA case);
- what to look for in the app, with expected reason codes and case, salary-documents and bank status;
- numbered file cards. Each card has a "הורדת PDF" button, borrower, printed month, where to upload on the right, and an Expected Output block that separates the document verdict from case-level consequences;
- manual "הועלה / התוצאה תואמת / לא תואמת / לבדיקה" marks;
- a collapsed "פרטים טכניים" section with expected JSON, golden rubrics, income figures and SHA-256 provenance.

The 21st PDF, which belongs to no scenario, is under "קבצים משלימים".

| | |
|---|---|
| ![](docs/screenshots/09-presenter-scenarios.png) | ![](docs/screenshots/10-presenter-expected-file.png) |

- **Data.** `fixtures/presenter/presenter_scenarios_manifest.json` is the curated view, and `fixtures/presenter/golden_set/` is an unmodified copy of the golden set (v1.1, 21 PDFs, expected JSON, rubrics). Expectations are read from these files at runtime, not hard-coded in React.
- **Serving.** `GET /api/presenter/scenarios` returns the manifest, a server-side SHA-256 check of every PDF, the referenced expected JSON, the negative-test expectations and the golden rubrics. `GET /api/presenter/file?id=<manifest id>` serves only manifest-listed PDFs, as `application/pdf` attachments under their original names. It refuses to serve bytes whose SHA-256 differs from the manifest.
- **Cases.** The golden PDFs print `עידו לוי · DEMO-ID-001` and `נועה לוי · DEMO-ID-002`, which differ from the Lavi borrowers in cases 001/003. The mock bank therefore has two cases with the golden profile: `DEMO-MTZ-2026-004` (display 438839004) for scenarios 01, 02 and 10, and the isolated QA case `DEMO-MTZ-2026-005` (438839005) for 03–09. Cases 001–003, the review engine, the rubrics and MCP are unchanged.
- **State.** Expected output is static ground truth and never reaches the app. The presenter marks live only in `localStorage` (`mz.presenter.marks.v1`). "איפוס סימון בדיקות" clears just those marks. "איפוס התיק באפליקציה…" asks for inline confirmation, then calls the existing `POST /api/cases/{id}/reset`, and only for 004/005.

**Live demo, 01 → 02.**

1. Open `/customer` on a desktop browser. Scenario 01 is expanded.
2. Under "לפני שמתחילים", press "איפוס התיק באפליקציה…" → "כן, לאפס את התיק", then "לפתוח את התיק מימין". The app switches to case 438839004 on the Documents screen.
3. For files 1–6: press "הורדת PDF". On the right, press "להעלאה" on the card named in "להעלאה מימין", choose the downloaded file and press "העלאה ובדיקה חכמה". Tick "הועלה".
4. When the reviews finish, compare the right side with "מה צריך לראות באפליקציה" and each file's Expected Output, and tick "התוצאה תואמת" or "לא תואמת / לבדיקה".
5. Expand 02. Don't reset. Download "תלוש עידו — ספטמבר המתוקן", upload it for עידו, and compare again.

**Declared income.** Declared income is the structured application data in the Mortgage Case Service, marked `CUSTOMER_DECLARED`, and is never treated as verified income. `application_declarations.pdf` is not a required document in the demo scope, so it is no longer part of the 01 upload sequence. It stays downloadable under "קבצים משלימים". The app judges every upload against the payslip rubric, so uploading it would only add a "not a payslip" finding.

**Live run, 2026-10-12, after the PS-10 and declared-income correction** (`e2e/test_presenter.py --live`, 42/42 checks): real Gemini, with every PDF downloaded from the pane and uploaded through the app's upload sheet, on an isolated backend with a fresh database. The full table is in `e2e/artifacts/presenter/live-comparison.md`.

- **01.** All 6 golden payslips came back VALID, with printed month and net amount verified against the PDF text layer. PS-10 was decided by code as NOT_APPLICABLE on each, because no payment date is printed; the issue date was extracted as a separate field. Ido's September is missing and August is doubled, so the case needs customer action. Noa's declared ₪18,500 against documented ₪16,900 (−₪1,600, three months) is open for the banker.
- **02.** The corrected September closed the missing month as `resolved_by_new_evidence`. The salary-document subset is complete, with no open customer action, and the state is "מוכן לבדיקת הבנקאי — עם ממצאים פתוחים". The income gap stays open for the banker. Readiness is scoped to payslips only, the other case requirements are listed as not evaluated, and no bank decision was created.
- **Pay-date fixtures** (`fixtures/pay_date/`, golden PDFs untouched):
  - payment date 09.10.2026 with issue date 15.09.2026 → PS-10 PASS, VALID;
  - payment date 25.08.2026 → PS-10 FAIL, NEEDS_REVIEW;
  - payment date 15.09.2026 → PS-10 NEEDS_REVIEW.

  The slip held for review on its payment date still fed the income comparison.
- **Still different from the golden expectations** (outside this correction):
  - The filename/content mismatch is an INFO finding rather than a customer action.
  - Before September arrives, the app averages Ido's two available months (₪14,550, −₪150, within tolerance), where the golden set defers the average.
  - After 02, the old August copy still counts as an informational duplicate rather than superseded.

| CASE-01: expected (left) vs actual (right) | `ido_2026_09.pdf` review | CASE-02: salary documents complete, income gap with the banker |
|---|---|---|
| ![](docs/screenshots/11-presenter-case01-live.png) | ![](docs/screenshots/12-presenter-case01-review.png) | ![](docs/screenshots/13-presenter-case02-live.png) |

---

## Architecture

```
 Customer app (React, Touch design)   Banker console        JEEN Talk / JEEN agents (future)
          │  REST                           │ REST                    │ MCP (Streamable HTTP)
          ▼                                 ▼                         ▼
 ┌──────────────────────── Mortgage Case Service (FastAPI, SQLite WAL) ─────────────────────────┐
 │ case state · document inventory · durable jobs · findings lifecycle · readiness · audit       │
 │ Agent (Gemini function calling) ── one tool registry ── MCP server (/mcp, case-bound keys)    │
 │ MockBankAdapter (stage, requirements; authoritative = false)                                  │
 └───────────────┬───────────────────────────────────────────────────────────────────────────────┘
                 │ ReviewProvider contract (start · status · result · case review · re-run)
     ┌───────────┴──────────────┐
     ▼                          ▼
 GeminiReviewProvider (ACTIVE)   VisionTraceReviewProvider (BLOCKED until a real mortgage review is verified)
```

**Ownership** (`backend/app/review/contract.py`):

- **The review provider** owns the whole review: intake and classification, extraction, evidence, rubric judgement, the document-level verdict, cross-document consistency, and re-review.
- **The Mortgage Case Service** owns bank-case state, the required-document inventory, orchestration, run history, the findings lifecycle, readiness and audit.
- **Bank staff** own acceptance.
- A provider verdict is a *document review* verdict, never a credit decision.

`REVIEW_PROVIDER=gemini` is the only selectable value today. `visiontrace` requires the provider's readiness to be LIVE, and `hybrid` raises until it's designed (`backend/app/review/registry.py`).

### How one document is reviewed (Gemini provider)

| Stage | What happens | Where |
|---|---|---|
| Intake | PDF/PNG/JPEG up to 15 MB. SHA-256 dedupe per case: re-uploading the same file reuses its review, and an upload note is added if it was filed under another borrower. Pages are rendered on demand for the evidence viewer. | `workflow/engine.py`, `review/evidence.py` |
| A+B. Classify, OCR, extract | One **blind** multimodal call on the original file: the model never sees the expected values. JSON output constrained by `responseSchema`: doc type, legibility, scan/photo, typed fields, earnings/deductions lines. | `review/gemini_provider.py`, `review/prompts.py` |
| Evidence verification | **Text-layer PDFs:** the value must be found in the PDF text layer, and its box is the union of the real word boxes (`text_layer_exact`). **Scans:** the region is cropped and re-read by a second call that must agree (`vision_reread_confirmed`). Anything else stays `vision_unverified` or `not_found`, and evidence coordinates are never invented. | `review/evidence.py` |
| C. Deterministic rules | Period and named month, gross − deductions = net (±₪2, total lines excluded), employer present, identity relation (name/ID) to the assigned borrower, injection patterns, demo marker, evidence for decisive fields. | `review/deterministic.py` |
| E. LLM-as-a-Judge | Gemini evaluates the judge and hybrid criteria of the versioned rubric, citing evidence ids. Code merges: deterministic outcomes win, hybrid criteria give code precedence, and a PASS whose evidence isn't verified is downgraded. **The verdict policy is computed by code:** INVALID if a criterion with `on_fail=INVALID` fails, NEEDS_REVIEW if anything is FAIL or NEEDS_REVIEW, otherwise VALID. The result records rubric id/version, model ids, prompt version, run id and timestamps. | `review/gemini_provider.py`, `review/rubrics.py` |

### How the case is reviewed after every change

| Stage | What happens | Where |
|---|---|---|
| Coverage | The last 3 complete salary months as of the simulation date 2026-10-12, with payday on the 9th: **2026-07, 2026-08, 2026-09**. A month counts on the *printed* period, never the filename. Months covered only by documents that aren't VALID show as "בבדיקה". | `review/case_review.py`, `workflow/readiness.py` |
| D. Semantic cross-document review | Declared versus documented income, and identity consistency across documents. Declared income comes from the bank case as a customer declaration (`CUSTOMER_DECLARED`). It is compared over the payslips whose income-relevant criteria passed. The 5% tolerance is arithmetic in code; the model only judges whether the definitions are equivalent and proposes explanations and evidence to request. A customer statement is passed as *unverified context* and is never proof. Cached by input hash. | `review/case_review.py` |
| F. Findings lifecycle | Findings have stable keys (`CODE:subject[:period]`). On each case run, customer and informational findings that no longer reproduce close as `resolved_by_new_evidence`. **Banker findings are never closed by AI**; they are marked `not_reproduced_by` and wait for a banker decision (resolve with a basis, dismiss as an AI error, escalate, or ask the customer), which records a reason. A banker ruling holds until its evidence changes: a finding on a document is not reopened (the file never changes), and a case-level finding reopens only when its computed figures change — as a new finding whose history links to the earlier ruling, which stays as it was. Missing and duplicate months are coverage facts and are never suppressed. When the customer uploads a replacement the banker asked for, the old document's findings close as `replaced_by_customer_upload` once the new file is reviewed, and the replaced file no longer counts toward coverage (no leftover duplicate month). The same happens when the customer replaces, on their own, a document the AI review sent back: only its customer findings close, and a banker finding on the old file stays open for the banker. A criterion whose escalation is "customer" becomes a customer action only when it FAILs. When the review could not decide (NEEDS_REVIEW, for example "is this a payslip?"), it goes to the banker with wording that does not tell the customer the file is wrong. The doubt also counts as the document's single root cause. Every finding keeps its history. | `workflow/engine.py` (`reconcile_findings`), `workflow/review_desk.py` |

Each document collapses to a single root cause: an unreadable page yields only DOCUMENT_UNREADABLE instead of a cascade of downstream failures.

**Workflow.** Jobs live in SQLite with idempotency keys and run on three worker threads. Document jobs take priority; the case review is single-flight and waits for pending document jobs. A failed job gets up to 3 attempts with 4 s and 8 s backoff, and interrupted jobs are recovered on startup. Every run (document and case) is kept in `review_runs`.

**Two state machines, never mixed.** The bank stage comes from `MockBankAdapter`. Only "קיבלנו החלטה" was observed in the reference screenshots, so the 5-stage dictionary is treated as demo data with `authoritative=false`. The AI readiness states are NOT_CHECKED, CHECKING, RECHECKING, ACTION_REQUIRED, READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS, READY_FOR_HUMAN_REVIEW and ERROR. **PREPARATION_CONFIRMED is reachable only through the banker's action**, and that action is refused while customer actions or banker requests are open. A confirmation lapses when a document is uploaded after it or the banker asks the customer for something after it (`readiness.confirmation`); the console says why, and the banker confirms again. An open banker request also puts the case in ACTION_REQUIRED. A failed set-level review is ERROR, never "ready".

**What the customer sees first.** The home screen (`pages/customer/Home.tsx`) is one page, top to bottom: a greeting from the borrowers' first names (with a decorative inline SVG); the bank stage card (`MockBankAdapter`, shown as stored and never relabelled from AI state; when the case has a preliminary decision it adds "אישור עקרוני · אינו אישור סופי", the wording the Documents screen already uses); the action card; the assigned banker (initials avatar, "כתיבת פנייה" to the assistant, and the case meeting on one line, or "אין פגישה מתוכננת"); the document summary; the three latest updates; and the request details. The action card (`DocumentCheckCard`) is orange ("מה צריך לעשות עכשיו?") only when the customer has something to do, and neutral ("מה קורה עכשיו?") while waiting. An open banker request comes first: its own title is the action ("נדרש תלוש ספטמבר 2026 — עידו"), the banker's message is quoted as written (two lines on screen, attributed to the banker), and the button is named after the requested month and opens the upload sheet preset to the request. Without a request, missing months lead to the backend's first upload action (`available_actions`, the same one the assistant offers): the card is titled by that borrower and month ("חסר תלוש ספטמבר 2026 של עידו") and the button opens the upload sheet preset to them. One footer line names what the action does not cover ("עוד 3 תלושים של נועה", further requests) with a link to the full list, so one action never reads as the only missing item; the assistant shortcut sits in the same row. The document summary (`DocumentSummary`) has one row per borrower (status, required months fulfilled, a link to that borrower on the Documents screen) and keeps four numbers apart: required months fulfilled (the total), and files uploaded, reviewed and accepted by the banker (one line); "איך סופרים" expands the counting rule, the documents handled directly with the bank and the "final approval is the bank's" note. It offers a second upload only for a borrower the action card does not lead to and who has no open banker request. The update list (`RecentUpdates`) folds for display only: set re-checks are left out, an upload is left out once its review is listed, retries of one failed review show the latest attempt, and identical banker closures in a row become one line; banker requests and the customer's answers are never folded, and "לכל העדכונים בתיק" shows the snapshot's full list (the last 25 customer-visible events). There is no read/unread state, so nothing is marked "new". After a case switch nothing from the previous case is shown until the new snapshot arrives (`caseContext`). When refreshes fail twice in a row while a case is on screen, one line above the cards says the data may be out of date since the last successful refresh, with a retry; it clears on the next successful refresh. The assistant button shrinks to its icon while the screen is scrolled, and the bottom navigation and scroll padding respect the device safe area. The status itself is `readiness.customer_status`, derived from the same persisted facts with its own precedence (`workflow/readiness.py`): no documents (AWAITING_UPLOAD), a review that stopped (ERROR), work in progress (PROCESSING, or REVALIDATING after an earlier set review), a document to fix (CORRECTION_REQUIRED), months still missing (MISSING_DOCUMENTS), the banker's confirmation, open banker items or payslips not yet verified (BANKER_REVIEW), and only then CHECKS_COMPLETE. Its counter is required months covered by a VALID payslip or by one the banker accepted: a duplicate counts once, a document that is unreviewed or not VALID counts only after a banker accepts it, and a payslip the banker sent back for correction (or that was replaced) never counts. An open banker correction request makes the status CORRECTION_REQUIRED, and any other open banker request MISSING_DOCUMENTS. The required months come from the case rubric and the simulation date, so they are known before the first upload.

### Banker review workspace and human decisions

The console's default view is one review workspace: **queue → original document with evidence → decision panel**. The queue is built by the service (`GET /api/banker/cases/{id}/workspace`, `api/banker_package.py`) and groups items by what the banker can do:

| Group | What is in it |
|---|---|
| ממתינים להחלטתך | Reviewed documents without a banker decision. Items that need attention come first: an AI verdict that isn't VALID, open findings, or a printed month that differs from the month the file was uploaded for. |
| פערים לשיקול דעתך | Case-level banker findings, such as declared versus documented income. |
| בבירור | Documents the banker escalated. |
| תיקון אצל הלקוח | Documents sent back for correction, or with an AI finding the customer must fix. |
| מסמכים חסרים | Required months nobody uploaded. They are not documents and have no "accept"; the action is **בקשת השלמת מסמך**. |
| בעיבוד / טופלו | Documents still being read or that failed; accepted and replaced documents and ruled findings (collapsed). |

Above the panels, one summary row shows what waits for the banker, what waits for the customer, how many required payslips are verified, the bank's official stage (demo data) and the review state. "פירוט חודשים והכנסה" opens each borrower's month strip (verified by AI, accepted by you, waiting for a decision, missing, requested) and an income line that follows the rubric outcome, not the model's label. Above the document, the key extracted fields sit in one strip with a quiet tick when verified; the rest are under "עוד נתונים". The page highlights only the selected evidence (the printed month when it contradicts the upload, the field an open finding cites, otherwise net pay); every other box stays as a faint, clickable outline. The decision panel leads with one primary action chosen from the item's state; the others stay as neutral buttons, and history, notes and technical details are in collapsible sections at the bottom. For example, Ido's −₪150 (−1.1%) is within the 5% tolerance of IS-04, so it reads "לידיעה בלבד; לא נפתח ממצא". The model's `INCONSISTENT` label is shown only under technical details. The bank's official stage sits in the case bar as its own fact, labelled as demo data.

Every decision is a persisted transition in `workflow/review_desk.py`, written in one transaction with its audit event. It records actor, time, previous and new status, reason, customer message and evidence references. Banker status is derived from the append-only `banker_decisions` log and `customer_requests` (`workflow/desk_state.py`), next to the AI verdict and never instead of it:

| Action | Allowed from | Effect |
|---|---|---|
| קבלת המסמך (`ACCEPT_DOCUMENT`) | awaiting decision, escalated | Accepted for the documentary review step. The banker must acknowledge the document's open banker findings (the list must match, otherwise 409 "stale"), and a reason is required when there are findings or the AI verdict isn't VALID. Refused while an AI finding asks the customer to fix the file: mark that finding wrong first. |
| החזרה לתיקון (`REQUEST_CORRECTION`) | awaiting decision, customer fix, escalated, failed | Opens an in-app customer request with the banker's edited message and the requested month. The document's banker findings close as `correction_requested_by_banker`. |
| העברה לבירור (`ESCALATE`) | awaiting decision, customer fix | Requires a reason. The customer gets no request. |
| בקשת השלמת מסמך (`REQUEST_MISSING_DOCUMENT`) | a month currently missing | Opens an in-app request. One open request per borrower and month. |
| בקשת השלמת מסמך · בקשת הסבר / אסמכתה (`REQUEST_MISSING_DOCUMENT`, `REQUEST_EXPLANATION`) | open banker finding | In-app requests with an editable message. One request per missing month; an explanation request lets the customer answer in writing or attach a document. The answer is attached to the finding as unverified context, and the finding stays open. |
| סגירת הבירור לאחר בדיקה (`RESOLVE_FINDING`) | open banker finding | Requires a basis: verified against documents in the case, or the customer's explanation supported by a document (both need the supporting documents ticked), or a professional decision under policy (a detailed reason, recorded as a human override). A customer statement alone can't close it. When the comparison rests on part of the months, the banker must acknowledge the partial basis. A confirmation shows the finding, basis, documents, reason, what changes in the case and what the customer sees. Open requests on the finding close in the same transaction. |
| דיווח על טעות בזיהוי ה־AI (`DISMISS_FINDING`) | open finding on a document, or banker finding | A reason category and a detailed reason. It says the AI was wrong; it is not a decision on the document. Coverage facts and informational findings can't be ruled on. |
| העברה להמשך בירור (`ESCALATE_FINDING`) | open banker finding | Requires a reason. The finding stays open, in "בבירור". |
| ביטול בקשה ללקוח (`WITHDRAW_REQUEST`) | an open customer request | Requires a reason. The request leaves the app; the finding doesn't change. A request is never closed by the AI. Withdrawing a correction request returns the document to its previous banker status (it can be decided again) and reopens the banker findings the correction had closed. The document panel offers it next to the open request. |
| בקשת השלמת מסמך while the AI is reviewing | — | Refused (409) while any review job of the case runs: the month may already be on its way. The missing-month item offers no request until the review settles. |
| קבלת פניית הלקוח לטיפול (`ACKNOWLEDGE_HANDOFF`) | a customer's "pass me to my banker" request (assistant, voice or MCP) | Shown as a banner above the workspace. Taking it records a decision; the customer sees "‹banker› קיבלה את הפנייה שלכם", never the internal note. |
| הערה פנימית, אישור הכנת מסמכי השכר | any time / no open customer items | A note changes no state. The confirmation keeps open banker items open, and lapses on a later upload or banker request (see "Two state machines"). |

- **Sessions, not headers.** Every banker route needs a staff session (`app/auth.py`); writes need the case's assigned banker (another banker gets 403 and a read-only console). There is no login screen in the demo: the console obtains the demo banker's session (Dana) by itself. An `X-Staff-Id` header is ignored. The decision log records the session's staff id.
- **Idempotency.** Each form submission carries a `request_id`. Replaying it returns the recorded decision with `duplicate: true`, and the state check and write run under one lock.
- **The income comparison is labelled by its basis.** IS-04 compares the declared net income with the payslips available in the required months, against the 5% tolerance (`income-set.salaried` policy). When some months are missing, the console, the finding text and the customer's view call it a preliminary comparison of N of 3 months and name the missing months, and never call a single payslip an average. The threshold and the rule are unchanged.
- **Customer messages.** The suggested Hebrew message is a deterministic template built from the verified review facts, not generated by a model. The banker edits it, sees a preview of the customer's card, and confirms. The internal reason never reaches the customer API: snapshot findings and timeline events are projected without it. Nothing sends an SMS, an e-mail or a push notification. The request lives in the case and shows in the app: on the home action card ("בקשה חדשה מ…", button "העלאת תלוש <month>"), under "בקשות מ…" on the Documents screen, on the document's page, and in the assistant's open items. Its button opens the upload sheet preset to the request (`/customer/documents?request=<id>`).
- **Replacement.** An upload answers a request when it names it, or when it is the borrower's only open request and the months agree. Re-uploading a file already in the case answers nothing. The new file is reviewed like any upload, the set is re-checked, and the banker sees it as "מסמך חלופי" linked to the file it replaced, with the old file's evidence and decisions kept.
- **Customer replacement without a request.** A document the AI review sent back to the customer (an open customer finding on it, banker status "תיקון נדרש מהלקוח") can be replaced by the customer directly. The home card's "העלאת מסמך חלופי", the document page or the upload sheet's "המסמך החדש יחליף את …" sends `replaces_document_id`. `review_desk.check_replacement` refuses anything else before the file is stored: another case or borrower, a document that isn't waiting for a fix, one already replaced, or one with an open banker request. The link is stored on the upload intent. The banker sees "מסמך חלופי שהלקוח העלה אחרי שבדיקת ה-AI החזירה את …". If the customer disagrees with the AI, "המסמך כן נכון? פנייה לבנקאית" asks the banker to look, and the banker can report the AI error and accept.
- **Grouped acceptance.** When several documents wait in the same state (all clean, or all with the same AI finding), one form accepts them with one reason. Each is still recorded as its own decision.
- **Secondary views.** "שיחה עם הלקוח" shows the conversation and unattached customer statements. "יומן ופרטים טכניים" shows human decisions, customer requests, all findings including closed ones with history, runs, case criteria and the audit log. Rubric ids, model names and run ids appear in the default view only inside "פרטים טכניים".

### Rubrics (`backend/rubrics/`, versioned JSON validated on load)

- `payslip.il.salaried` **v1.2.0** (current; v1.1.0 and v1.0.0 kept for history):
  - PS-01 is a payslip (judge, INVALID on fail)
  - PS-02 legible (judge)
  - PS-03 identity matches the assigned borrower (hybrid, INVALID on fail)
  - PS-04 period (code)
  - PS-05 gross and net present (code)
  - PS-06 arithmetic (code)
  - PS-07 employer (code)
  - PS-08 no instructions or editing marks (hybrid)
  - PS-09 decisive evidence verified (code)
  - PS-10 payment date, if printed, plausible for the period (hybrid)
  - Changelog for v1.1.0: the demo watermark is expected, and total lines are excluded from the sums.
  - Changelog for v1.2.0: PS-10 is decided by code. The Wage Protection Law (s. 24(b) and its addendum) does not list a payment date among the mandatory payslip details, so a payslip that prints none gets NOT_APPLICABLE and the date stays unknown. The issue date (תאריך הפקה) is a different field and never stands in for it. A verified printed date before the period is FAIL; inside the period, more than 3 days before its end, it is NEEDS_REVIEW; through the 9th of the following month it is PASS. The judge decides only a printed date that code can't parse or verify.
- `income-set.salaried` **v1.1.0** (v1.0.0 kept for history): IS-01 all months covered, IS-02 no unhandled duplicate, IS-03 each payslip on the right borrower, IS-04 declared income consistent (code tolerance plus judge), IS-05 freshness, IS-06 every required payslip reviewed VALID.
  - Changelog for v1.1.0: IS-04 averages the net pay of payslips whose income-relevant criteria passed (PS-01–06, PS-08, PS-09), rather than requiring an overall VALID verdict. A criterion that doesn't bear on the amounts, such as PS-10, can't suppress the comparison. Declared income is the customer's declaration from the bank case (`declared_income_provenance: CUSTOMER_DECLARED`), never verified income.

### Assistant, voice and JEEN Talk boundary

- **One brain.** `backend/app/agent/agent.py` runs Gemini function calling over the 10 case tools in `agent/tools.py`: overview, documents, document review, open items, upload guidance, explain finding, review history, record statement, banker handoff, re-validation. In the app it also has `offer_app_actions`, which puts buttons under the answer (see the next section).
  - Facts come only from tool output, and a yes/no question about the case still calls `get_case_overview` first.
  - The two write tools (record statement, banker handoff) require `customer_confirmed=true` and are idempotent. A handoff is not duplicated while one is already in the banker queue.
  - A reply guard blocks approval claims and masks ID numbers.
  - If Gemini is unavailable, the reply is built from tool output without a model and labelled as such.
- **Voice uses the same endpoint** with `channel=voice`. `frontend/src/voice.ts` defines a `VoiceChannel` interface.
  - `BrowserVoice` uses Chrome's Hebrew Web Speech recognition when available. Otherwise it records with MediaRecorder, re-encodes to 16 kHz WAV, and transcribes through `/api/voice/transcribe` (Gemini). Answers are spoken with the system Hebrew voice.
  - `?voice=server` forces the server path.
  - `JeenTalkVoice` is the slot for JEEN Talk. JEEN Talk itself would call the **same tools through the MCP server**, so phone and app see one case state.

### Assistant actions: from the answer to the right screen

When the customer asks what is missing, the answer comes with buttons. Each button opens an existing screen with everything the case already knows filled in.

| Answer with actions | Upload sheet, preselected | Real outcome and next step | Same chat, stale action disabled |
|---|---|---|---|
| ![](docs/screenshots/actions-01-chat-actions.png) | ![](docs/screenshots/actions-02-upload-preselected.png) | ![](docs/screenshots/actions-03-upload-outcome.png) | ![](docs/screenshots/actions-04-followup-stale.png) |

**The contract.** `app_action.v1` lives in `backend/app/agent/actions.py`. The Mortgage Case Service derives every action from persisted state: requirements and missing months, open findings, documents and handoffs. Each action has a stable id, the case id, a Hebrew label and detail, a priority, and typed parameters validated by Pydantic.

| Type | Opens | Offered when |
|---|---|---|
| `NAVIGATE_TO_DOCUMENT_UPLOAD` | the borrower's payslip card and the existing upload sheet, preselected | months are missing, or a customer finding needs a new document |
| `VIEW_DOCUMENT_REVIEW` | the document's review page with its evidence, scrolled to the finding | an open finding points at a document |
| `VIEW_MISSING_DOCUMENTS` | Documents, with the incomplete payslip cards highlighted | something is missing |
| `VIEW_REVIEW_STATUS` | Documents, uploaded list | a document review or a set re-check is running |
| `VIEW_CASE_DETAILS` | פרטי הבקשה | always |
| `CONTACT_BANKER` | an explicit confirmation sent through the same agent, which uses the existing handoff tool | banker items are open and nothing is queued |

No action is offered for bank statements or other document families, because the demo doesn't review them.

- **The model only chooses.** `offer_app_actions` takes action ids from the `app_actions` list that the case tools return in the same turn. It is available to in-app chat and voice only. The server rejects unknown ids, orders the chosen actions by its own priority, and stores them on the assistant turn. When Gemini is unavailable, the fallback reply carries the top next steps from case state.
- **Every click is checked again.** `POST /api/cases/{case}/actions/resolve` returns fresh parameters, or refuses with 403 (the turn belongs to another case), 404 (the action wasn't offered in that turn) or 409 (the action is stale).
- **The app navigates with its own router.** An upload action opens `/customer/documents?case=…&upload=PAYSLIPS:BRW-B[&period=…]`. The Documents screen checks the link against the active case and the live requirements before it opens the upload sheet. A document page won't show a document from another case.
- **Months.** A single missing month is preselected. When several are missing, the sheet lists them, selects none, and lets the customer pick one. The chosen month is stored as an upload intent (`upload_intents`) and never reaches the reviewer, so the review stays blind. After the review it is compared with the printed month.
- **After the upload.** `GET /api/cases/{case}/documents/{doc}/outcome` moves through `reviewing_document`, then `rechecking_case`, then `complete`. The final message is composed from the review result and the refreshed case, for example: "התלוש של נועה לספטמבר 2026 התקבל ונבדק — נמצא תקין. נותר להעלות את תלוש ספטמבר 2026 של עידו." The word "נבדק" appears only after the review finished. A wrong month, a finding or a failed review is stated as such, together with its next action.
- **Same conversation.** An upload started from the assistant gets one follow-up turn (channel `app`) once the set re-check is done. The turn is written on the next conversation read, so it survives a closed chat or a reload. Older buttons render from live state: actions that are still needed show current details, and satisfied ones are disabled ("✓ כבר לא נדרש"). Only the newest answer's first action is emphasized.
- **Voice.** A spoken request such as "תעביר אותי להעלאת התלוש של נועה" goes through the same agent and returns the same action. The reply says a button is on the screen, and the app never navigates by itself. `offer_app_actions` isn't exposed over MCP because a phone call has no screen. It can be enabled for JEEN Talk once there is a verified way to show an action in the app.

### Mortgage Case MCP server (`backend/app/mcp/server.py`)

- **Transport and auth:** Streamable HTTP, stateless JSON responses, protocol versions 2026-07-28 / 2025-11-25 / 2025-06-18 / 2025-03-26. Each bearer key is bound to **one case**, so a model never names the case. Extra arguments such as `case_id` are rejected.
- **Refusals:** browser Origins other than localhost get 403, invalid keys get 401, and GET/DELETE get 405.
- **Results:** sized for voice (about 3,800 characters). Write tools carry non-read-only annotations, and every call is audited.

```json
{ "mcpServers": { "mizrahi-touch-mortgage-case": {
    "url": "http://127.0.0.1:8790/mcp",
    "headers": { "Authorization": "Bearer <MCP_DEMO_KEY from backend/.env>" } } } }
```

---

## Integration matrix

| Component | State | Notes |
|---|---|---|
| Gemini document review (classify, OCR/extract, evidence re-read, judge, semantic) | **LIVE** | `gemini-3.8-flash` for every stage, temperature 0, low thinking |
| Gemini conversational agent (function calling) | **LIVE** | same model; chat and voice |
| Gemini voice transcription (fallback STT) | **LIVE** | used when the browser has no Hebrew speech recognition, or with `?voice=server` |
| Deterministic validation, evidence verification, rubric policy | LOCAL | PyMuPDF text layer, crop re-read, versioned rubrics |
| Mortgage Case Service (state, workflow, findings, audit) | LOCAL | SQLite WAL, in-process workers |
| Mortgage Case MCP server | LOCAL | verified with the official MCP Python SDK client |
| Browser voice (Web Speech STT, system TTS) | LOCAL | Hebrew TTS depends on an installed Hebrew voice (e.g. macOS Carmit) |
| JEEN Talk | **BLOCKED** | no credentials; adapter slot ready; **no calls were placed** |
| VisionTrace review provider | **BLOCKED** | see below |
| VisionTrace MCP (read-only probe) | **BLOCKED** | the provided key returned HTTP 401; the probe never opens an intake |
| Bank systems (stage, requirements, acceptance) | DEMO | `MockBankAdapter`, synthetic, `authoritative=false` |
| Identity and authorization | DEMO | server-checked signed sessions on every route; demo sessions are issued without a login (`DEMO_IDENTITY=1`), no identity provider; banker writes need the case's assigned banker; MCP keys bound to one case |

The `/system` page renders this matrix live from the backend.

## VisionTrace: adapter contract and remaining work

VisionTrace is intended to become the full review engine behind the **same** `ReviewProvider` contract: start, status, document result, case review, and re-run. Results carry facts with evidence, criterion outcomes with reason codes, a verdict, limitations, provider identity, rubric version, run id and timestamps. `backend/app/review/visiontrace_provider.py` holds the stub, the read-only probe, and an **untested** `map_envelope()` that maps a VisionTrace review envelope onto `DocumentReviewResult`. **No VisionTrace integration is claimed:** a VisionTrace MCP connection that only lists workflows is not a document-review integration.

What is needed, based on VisionTrace `main` 5a1ca7d (2026-10-11):

1. **A valid MCP key.** The provided key returned 401. Because it was pasted in chat, it should be rotated.
2. **A mortgage payslip workflow.** It can build on the unemployment-claim payslip workflow, which already has month coverage, `named_month`, a grounding gate and `locate_verbatim`. It needs borrower assignment per document, the requested-months policy above, and declared-income comparison.
3. **Expose the workflow to intake.** `visiontrace_open_intake` only accepts `fire` and `protected_spaces` today.
4. **Evidence-bearing results.** The MCP read tools return voice-shaped summaries without boxes. The adapter needs the review envelope (facts, `field_sources`, `screening.cases[].checks[]`) through REST service access or a new MCP tool.
5. **Implement the provider lifecycle.** Implement `start_document_review` (intake plus consented upload), `get_status`, `get_document_result` and `review_case`, then validate `map_envelope()` against a real envelope.
6. **Prove it on the golden corpus.** Run `fixtures/` through VisionTrace and compare with `fixtures/world.json` and the Gemini results. Only after the findings are verified should `REVIEW_PROVIDER=visiontrace` be enabled.
7. **Optional hybrid mode.** VisionTrace document verdicts plus Gemini semantic review. Not implemented.

**JEEN Talk needs:**

- a base URL and a Developer API key (`X-API-Key`);
- a Hebrew agent configured with this MCP server and a case-bound key;
- explicit approval before any live phone call.

---

## Test results (real Chrome, real Gemini, 2026-10-12)

| Suite | Result | Run with |
|---|---|---|
| Unit and integration tests (deterministic layer, evidence, reply guard, customer-status precedence, actions, payment-date rule and income selection, banker review desk and finding decisions through the real routes) | **64/64** | `cd backend && .venv/bin/python -m pytest -q tests` |
| Browser end-to-end journey | **17/17** (about 4 min) | `backend/.venv/bin/python e2e/test_journey.py` (resets cases 001 and 003) |
| Banker review workspace and the banker → customer → re-review loop | **41/41** (about 80 s) | `backend/.venv/bin/python e2e/test_banker_review.py` (isolated backend; see its docstring) |
| Resolving a banker finding: preliminary comparison, requests, customer reply and uploads, re-review, resolution, AI false positive | **30/30** (about 75 s) | `backend/.venv/bin/python e2e/test_finding_resolution.py` (isolated backend; see its docstring) |
| MCP with the official SDK client | **9/9** | `backend/.venv/bin/python e2e/test_mcp_sdk.py` (after the journey) |
| Chat-to-action navigation (mobile RTL, real uploads, voice, other-case refusals) | **22/22** (about 3 min, 26 Gemini calls) | `backend/.venv/bin/python e2e/test_chat_actions.py` (resets cases 001 and 003) |
| Presenter pane: accordion, 21 downloads with SHA-256, RTL, marks, no regression | **28/28** (about 25 s, no Gemini) | `backend/.venv/bin/python e2e/test_presenter.py` (resets case 005) |
| Presenter live 01 → 02 through the app UI, plus pay-date fixtures | **14/14**, plus an expected-vs-actual report (about 2 min) | `backend/.venv/bin/python e2e/test_presenter.py --live` (resets cases 004 and 005) |

**Executive demo, 2026-10-13: REPLAY, zero Gemini calls.** These runs prove the workflow and the UI, not the model's accuracy.

| Suite | Result | Run with |
|---|---|---|
| Featured scenarios, customer replacement, uncertainty routing, scoped reset, worker guards, golden-set independence (pytest, stored reviews) | **18/18** | `cd backend && .venv/bin/python -m pytest -q tests/test_featured_demo.py` |
| PASS · REVIEW · BLOCKER through the real UI: downloads, uploads, banker acceptance, banker request and customer reply, customer replacement and re-review, customer/banker consistency, refresh, "התחל דמו חדש" | **25/25** (about 40 s) | REPLAY backend `e2e/replay_backend.py` + `e2e/test_featured_demo.py` (commands in its docstring) |
| Presenter pane with the new layout (no Gemini) | **29/29** | `PRESENTER_BASE=<isolated stack> backend/.venv/bin/python e2e/test_presenter.py` |

The REPLAY backend replaces only the Gemini HTTP transport. Evidence verification against the uploaded PDF, rules, verdicts, case review, findings, outcomes, the banker desk and the reset all run for real. Model answers come from `e2e/replay/recordings.json`, looked up by the uploaded file's SHA-256, never by filename. The six golden payslips restate the live review of 2026-10-12 (`RECORDED_LIVE`). The bank statement uploaded as a payslip has no live recording; its answer is written by hand and labelled `AUTHORED`, so the BLOCKER classification itself has **not** been verified live. The semantic step is a fixed rule. Every call is logged to `<DATA_DIR>/replay-transport.jsonl`, and model ids read `replay-recorded`.

The browser journey uploads every file through the UI. It checks:

- all six initial documents VALID;
- the scan read with re-read evidence (net ₪16,900);
- the file named "09" extracted as August (gross ₪17,500);
- the missing, duplicate, filename and income-variance findings in the API and the UI;
- 10 rubric criteria with at least five evidence boxes;
- a grounded chat answer;
- a **voice turn** (a Hebrew phrase played into Chrome's fake microphone was transcribed as "מה עוד חסר כדי להשלים את המסמכים?" and answered by the same agent with case tools);
- correction and re-validation (`resolved_by_new_evidence`, duplicate becomes INFO);
- the customer explanation attached without resolving the finding;
- exactly one banker handoff;
- state surviving a reload;
- the banker confirmation keeping the banker item open;
- the MCP self-test matching the app;
- the four negative documents with no false approval (wrong borrower INVALID; unreadable, injection and contradictory NEEDS_REVIEW).

The MCP suite checks:

- the handshake and the 10-tool catalog;
- `get_case_overview`, `list_open_items` and `list_documents` against the app;
- a write without confirmation refused, with no change;
- the second case's key seeing only its own case;
- a smuggled `case_id` rejected;
- 401 / 403 / 400 / 405 refusals.

Results and screenshots are written to `e2e/artifacts/`, and the screenshots above are copied into `docs/screenshots/`.

`e2e/test_banker_review.py` uploads the six initial payslips to an isolated backend (real Gemini). In the browser it checks that the mislabeled file is first in the queue, that missing September is listed as missing, that the progress counts required payslips, and that Ido's income gap is informational. It inspects the page and its evidence boxes, accepts a payslip with a double click (one decision recorded), sends the mislabeled file back with an edited message, and checks the customer's home card, timeline and preset upload sheet. It uploads the replacement from the app and waits for the real re-review. Then it checks the replacement and history in the console, that every open banker finding is still tracked, the keyboard navigation, refresh, replayed submissions, invalid transitions, unauthorized calls, and that the bank stage never moves. The backend tests in `backend/tests/test_review_desk.py` cover the same transitions without Gemini, against a temporary data directory set up in `tests/conftest.py`.

`e2e/test_finding_resolution.py` follows one finding on an isolated backend (real Gemini). Noa uploads only September (₪16,900 against ₪18,500 declared). The banker sees a preliminary one-month comparison, can't close it without acknowledging the partial basis, and asks for July, August and an explanation. MCP and the in-app assistant report the same three requests. The customer answers in writing and uploads both months from the request cards, and Gemini re-reviews. The finding stays open with the full comparison and the unverified explanation, and the banker closes it with the three payslips as supporting documents (a double click records one decision). The decision survives a refresh and a later review, the customer's timeline shows only a neutral line, and a pay-date false positive on case 004 is dismissed with a reason, audited, and not reopened.

`e2e/test_ai_card.py` walks the home-screen card through real states on an isolated backend: nothing uploaded, under review, one payslip, a missing month, a duplicate month, re-validation, full coverage with a banker item, complete, banker-confirmed, invalid documents, a processing error and an unreachable API. It checks the title, the counts against an oracle built from the raw document reviews, the borrower rows and every button's destination. Its docstring lists the commands; it resets the cases it uses, so never point it at a backend whose data matters.

## Gemini usage and cost control

- One full browser journey made **37 Gemini calls**, all successful: about 77K input and 31K output tokens. That breaks down into 11 extractions, 11 judgements, 1 scan re-read, 3 semantic reviews, 10 agent steps and 1 transcription.
- **Hourly call budget.** `GEMINI_MAX_CALLS_PER_HOUR` (default 400) is enforced before every call.
- **Limited retries.** Only 429 and 5xx responses are retried, up to 3 attempts.
- **Repeat work is skipped.** Re-uploading the same file triggers no new review, and semantic reviews are cached by input hash.
- **Every call is recorded** (purpose, tokens, latency, error) and shown on `/system`.

## Security and governance

- Synthetic data only. A concept-demo ribbon on every screen states that the data is synthetic and not connected to Mizrahi systems.
- Secrets live server-side in `backend/.env` (chmod 600, gitignored) and are never sent to the browser.
- Document text is treated as hostile: it's quoted to models as data, and injection patterns are flagged by code.
- **Code, not the LLM, decides:**
  - arithmetic, permissions, state transitions and verdict policy;
  - the agent cannot approve a mortgage, change a verified finding, or close a banker finding;
  - customer statements are recorded as unverified context only.
- Case binding is enforced server-side for both the agent and MCP. Writes require explicit confirmation and are idempotent per request, and every tool call is audited.
- **Sessions and access (`backend/app/auth.py`).** Every `/api` route except health, fixtures, presenter files and the session routes checks an HMAC-signed, expiring session (HttpOnly, SameSite=Strict cookie, or the same token as a bearer). A customer session is bound to the cases it was issued for: it reads no other case, document or original file, and never reaches the banker API. The raw review data (`/api/cases/{id}/findings`, `/audit`, `/runs`, `/api/runs/{id}`) and every banker read need a staff session; banker writes need the case's assigned banker. A request header can't choose an identity. Customer views are projected: no banker reason, note, handoff package or confirmation note reaches them, and the assistant/MCP finding history is projected the same way. `retry` accepts only a failed document of your own case; a demo reset needs the case's customer or banker and can be switched off (`DEMO_RESET=0`).
- **Demo identity.** There is no identity provider in this demo. With `DEMO_IDENTITY=1` (default) the apps obtain sessions without a login: the customer app for the case picked in its selector (`POST /api/session/demo/customer`), the banker console for the demo banker (`POST /api/session/demo/staff`). Anyone who can reach the server can therefore obtain a demo session; outside a demo set `DEMO_IDENTITY=0` and issue sessions from the bank's SSO/OTP (`auth.issue`). Sessions are signed with `SESSION_SECRET`, or a random secret kept in `DATA_DIR/session_secret`; `SESSION_TTL_MINUTES` (default 480).

## Known limitations

- Only salaried payslips are reviewed. Other document families appear as "לא נבדק בהדגמה".
- No identity provider. Access is enforced on every route by server-issued sessions, but in demo mode anyone who can reach the server can obtain a demo session for any case or for the demo banker, so the demo still must not hold real data. Turn `DEMO_IDENTITY` off and connect bank SSO/OTP before any real use. One browser holds one customer session and one staff session at a time (the presenter plays both roles). Single-process SQLite with in-process workers is fine for a demo; production needs a database server and a queue.
- There is no push channel: both apps poll every 4 s (1.2 s while work is in progress). Measured propagation on a local machine was 0.1–4 s.
- The app can only upload payslips. A "request a document" on the income finding asks for something like an employer letter, which is uploaded as a payslip and reviewed against the payslip rubric, so it comes back "not a payslip". The banker can still read it in the evidence viewer.
- The BLOCKER scenario's classification of a bank statement uploaded as a payslip has only been exercised with an authored REPLAY answer. Run it once live (about 4 Gemini calls) before relying on it in front of an audience. The income check compares a 3-month average with the declaration: a single bonus month can lift the average inside the 5% demo tolerance, so month-to-month volatility is not flagged. The 5% tolerance is demo configuration, not bank policy.
- Customer requests can be withdrawn (with a reason) but not edited, and a document or finding decision can't be reversed. A new decision is the only correction.
- A professional decision needs a reason of at least 15 characters, and so does a report of an AI error. That minimum is a UX safeguard in this demo, not a bank policy.
- Accepting a document is recorded per document. It doesn't change the AI verdict, so case criterion IS-06 (all payslips VALID) can still read NEEDS_REVIEW while the banker has accepted every payslip.
- During development, one transcription request got HTTP 400 from Gemini and didn't reproduce in later runs. The UI now shows a Hebrew retry message instead of a raw error.
- Gemini model ids are configurable in `backend/.env`.

## Brand note

The Mizrahi-Tefahot logo files in `frontend/public/brand/` are taken from the bank's public website, solely so this internal concept demonstration is recognisable. The marks belong to Bank Mizrahi-Tefahot Ltd. They must be removed, or their use approved by the bank, before any external use. The Jeen logo (`jeen-logo.png`, plus `jeen-logo-light.png` with a white wordmark for dark bars and the tile mark `jeen-mark.png`) is generated from JEEN's own logo file. Colours and typography follow the public brand (orange `#ff780b`, slate `#3f4a5e`, Open Sans Hebrew).

## Project layout

```
backend/app/
  review/      contract.py (provider contract) · gemini_provider.py · case_review.py · deterministic.py
               evidence.py · prompts.py · rubrics.py · registry.py · visiontrace_provider.py
  workflow/    engine.py (durable jobs, reconciliation) · readiness.py (AI readiness state machine)
               review_desk.py (banker decisions, customer requests, drafts) · desk_state.py (banker status per document)
  agent/       agent.py (Gemini function calling, guard) · tools.py (one tool registry for agent and MCP)
               actions.py (app_action.v1: derive, choose, resolve) · continuation.py (after-upload outcome)
  mcp/         server.py (Mortgage Case MCP server)
  api/         routes.py (customer + system API) · assistant.py (action resolve, upload outcome) · banker.py · banker_package.py
  bank/        mock_bank.py · store/repo.py · llm/gemini.py · db.py · config.py · main.py
backend/rubrics/   versioned rubric JSON
backend/tests/     unit tests · test_review_desk.py (banker desk integration) · conftest.py (temp DATA_DIR) · live_journey.py
frontend/src/      customer app (pages/customer), banker console (pages/banker: BankerConsole · ReviewWorkspace · DecisionPanel),
                   system page, voice.ts, components
fixtures/          world.json (ground truth) · generate.py · out/ (synthetic PDFs + manifest)
                   presenter/ (presenter_scenarios_manifest.json + golden_set/, served to the "תרחישי בדיקה" pane)
                   pay_date/ (generate.py + out/: payslips that print a payment date, for the PS-10 regression)
e2e/               test_journey.py (browser) · test_mcp_sdk.py · test_presenter.py · test_chat_actions.py · screens.py (visual QA)
                   test_banker_review.py (banker → customer → re-review) · test_finding_resolution.py (finding decisions)
                   banker_screens.py · banker_visual.py (console screenshots, overflow and clipping checks)
```

# 02 — Mizrahi-Tefahot Loan Process Research

All sources accessed **2026-10-13**. "Confirmed" = stated on the cited page. "Unverified" = not found publicly;
the product treats it as a configurable demo assumption. This is not a description of Mizrahi's internal process.

## 1. Loan products and journeys

### Confirmed
- **הלוואה ברגע** (instant loan): up to ₪125,000, 2–72 payments, no guarantors, first payment deferrable up to
  3 months; requested on the website/app when logged in, a lead form, or *8860.
  [express-loan](https://www.mizrahi-tefahot.co.il/loans/privateloanslib/express-loan/) ·
  [digital services](https://www.mizrahi-tefahot.co.il/online-banking/digital-services/)
- **הלוואה לכל מטרה** (all-purpose loan): via form, *8860 or branch; every application reviewed individually;
  "מסלול ירוק" ₪10K–60K signed remotely by SMS/email.
  [all-purpose-loan](https://www.mizrahi-tefahot.co.il/loans/privateloanslib/all-purpose-loan/)
- Car loan up to 85% of price / 60 months ([car-loan](https://www.mizrahi-tefahot.co.il/loans/privateloanslib/car-loan/));
  renovation "שפץ נא" ([buff-loan](https://www.mizrahi-tefahot.co.il/loans/privateloanslib/buff-loan/));
  celebration loan up to ₪100K ([happy-event-loan](https://www.mizrahi-tefahot.co.il/loans/privateloanslib/happy-event-loan/));
  students up to ₪50K ([FAQ](https://www.mizrahi-tefahot.co.il/faq/students-loans/));
  discharged soldiers ([soldier-account](https://www.mizrahi-tefahot.co.il/open-a-bank-account/accounts-type/soldier-account/)).
- Loans are also offered to non-customers ([faq/loan](https://www.mizrahi-tefahot.co.il/faq/loan/)); "בקשה לקבלת
  הלוואה חדשה" is available in every channel ([our-services](https://www.mizrahi-tefahot.co.il/online-banking/our-services/)).
- Mortgage guide: additional documents may be required after a preliminary approval
  ([guide PDF](https://www.mizrahi-tefahot.co.il/media/y0ufpe5h/%D7%9E%D7%93%D7%A8%D7%99%D7%9A-%D7%9C%D7%A7%D7%91%D7%9C%D7%AA-%D7%94%D7%9C%D7%95%D7%95%D7%90%D7%AA-%D7%9E%D7%A9%D7%9B%D7%A0%D7%AA%D7%90.pdf));
  Leumi: the document list "אינה רשימה סגורה" ([borrower guide](https://www.leumi.co.il/leumi-hebrew/s3fs-public/pdfFile/snf_120.pdf)).
- Peers: Hapoalim lends to customers of all banks via a loan-only account
  ([terms](https://www.bankhapoalim.co.il/loans/digital-loan-terms)); Leumi digital all-purpose loan for all banks;
  One Zero app-only, "no forms" ([One Zero](https://www.onezerobank.com/special/7920)).

### Unverified
Mizrahi's in-app approval limits, whether personal loans have a preliminary-approval step, a public status tracker
for personal loans (Tefahot Touch is mortgage-only), consumer bridge loans.

### Implication
The fast digital loan already completes without documents; the PRD correctly targets **document-requiring
applications**. Demo product: **הלוואה לכל מטרה** with purposes car / renovation / celebration / other.

## 2. Required documents

### Confirmed
- Mizrahi all-purpose loan: **ID, current-account statements of all accounts for the last 3 months, the last 3
  payslips, proof of the loan's purpose** ([all-purpose-loan](https://www.mizrahi-tefahot.co.il/loans/privateloanslib/all-purpose-loan/)).
- Mizrahi mortgage guide §15 (analogue): salaried — 3 payslips; self-employed — latest tax assessment and/or CPA
  confirmation; other income — confirmation from the paying body (e.g. allowance) or divorce agreement; 3 months of
  statements of every account; foreign citizens — passport + photo ID; guarantors — same documents.
- Leumi: ID **with appendix (ספח)**; self-employed — assessment or annual report stamped "נתקבל" + CPA
  confirmation; newly self-employed — CPA monthly net, business-opening confirmation
  ([Leumi list](https://mortgage.leumi.co.il/Articles/76)).
- National Insurance issues online allowance confirmations ([BTL](http://www.btl.gov.il/%D7%98%D7%A4%D7%A1%D7%99%D7%9D%20%D7%95%D7%90%D7%99%D7%A9%D7%95%D7%A8%D7%99%D7%9D/%D7%90%D7%99%D7%A9%D7%95%D7%A8%D7%99%D7%9D/Pages/default.aspx)).

### Unverified
Mizrahi's accepted proof-of-purpose types (quote / invoice / contract) and their maximum age.

## 3. Document requirement matrix (seed config — demo assumption, not bank policy)

| Requirement | Rule | Per | Validation (code decides; Gemini extracts) |
|---|---|---|---|
| ID card (`ID_CARD`) | mandatory | applicant | doc type = ID; legible; holder name matches applicant; ID number check digit valid and equals case ID; not expired when an expiry is printed; appendix optional (config) |
| Payslips (`PAYSLIPS`) | mandatory if salaried | applicant | existing PS-01…PS-10: last 3 complete months (`policy_months`), borrower match, arithmetic, pay date, evidence verified |
| Bank statements (`BANK_STATEMENTS`) | mandatory | declared account | doc type = statement; holder matches an account holder; coverage of the last N=90 days without gap; statement end ≤ 30 days before simulation date; joint account satisfies all holders (config) |
| Proof of purpose (`PURPOSE_PROOF`) | mandatory, type by purpose | case | doc type = quote/invoice/contract; issued ≤ 90 days; issuer and amount printed; amount below the requested amount → banker REVIEW only (never a credit check) |
| Tax assessment / CPA (`TAX_ASSESSMENT`) | conditional: self-employed | applicant | doc type = tax form; tax year ≥ last year (classification + recency only in demo) |
| Allowance confirmation (`ALLOWANCE_CONFIRMATION`) | conditional: allowance income | applicant | issued ≤ 90 days (classification-level; off by default) |
| Credit-data consent, agreement signing, AML/KYC | out of scope | — | bank systems own these |

Every threshold above is a key in the published policy config and editable in Admin Settings.

## 4. Incomplete applications and communication

### Confirmed
- Mizrahi app: chat with a personal banker including files; alerts for banker messages; digital signing
  ([App Store](https://apps.apple.com/il/app/%D7%9E%D7%96%D7%A8%D7%97%D7%99-%D7%98%D7%A4%D7%97%D7%95%D7%AA-%D7%A0%D7%99%D7%94%D7%95%D7%9C-%D7%97%D7%A9%D7%91%D7%95%D7%9F/id508767900)).
- Remote signing: banker sends an SMS link; opening requires a valid ID number; files attached by camera; a receipt
  confirmation follows ([signing](https://www.mizrahi-tefahot.co.il/mortgages/updatemortgage/signiture/)).
- Tefahot Touch (mortgage): stage status, document upload, expert chat, marketed as "לא בוט, בן אדם!"
  ([mortgage-app](https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgage-app/)).

### Implications
Secure links must be **scoped and short-lived** and, in production, protected by the bank's verification (ID/OTP);
the demo token alone is a documented demo limitation. Human contact must stay available ("talk to a banker").

## 5. Regulatory and operational constraints

| Item | Status | Design consequence |
|---|---|---|
| Fair Credit Law 1993 ([Knesset](https://main.knesset.gov.il/Activity/Legislation/Laws/Pages/LawPrimary.aspx?lawitemid=2000450)) | binding | no credit terms or approval promises from the agent |
| Directive 311A consumer credit ([EN](https://boi.org.il/media/2asddbk5/311a_en.pdf)) | binding | declared income stays `CUSTOMER_DECLARED`; no affordability decision |
| Directive 367 communications banking ([v12](https://boi.org.il/media/lucfcwdh/367_12.pdf)) | binding | identification is a bank system concern; links never substitute identification |
| Directives 357/361/363 → **364** since 18/05/2026 ([364](https://www.boi.org.il/roles/supervisionregulation/nbt/nbt364/)); 362 cloud | binding | secrets server-side; external vendors (Gemini, Talk) behind adapters with data minimization |
| Directive 369 model risk incl. AI ([369](https://www.boi.org.il/media/px3dfkjk/369_en.pdf), [FAQ](https://www.boi.org.il/media/npxhjdr0/faq_525-en.pdf)) | binding from 21/08/2025 | every run records model, prompt, rubric and policy version; explanations; human decides |
| Privacy Protection Law Amendment 13 ([PPA](http://www.gov.il/he/pages/guide_tikon13_professional)) | binding from 14/08/2025 | minimal Talk payload (first name, open requirements, link); no PII in logs |
| Data Security Regulations 2017 | binding | access control on documents and evidence (existing), audit |
| PPA draft AI guidance ([gov.il](https://www.gov.il/he/pages/ai_reg)) | draft | agent discloses it is an AI — enforced as a locked prompt segment |
| Spam law s.30A ([ruling](https://www.isoc.org.il/files/spam/verdict/1088.pdf)) | binding | templates service-only; validator rejects marketing wording |
| Credit Data Law / directive 405 | binding | out of scope (no credit report pulled) |
| AML order for banks ([188](https://www.boi.org.il/media/fkenivj3/188.pdf)) | binding | retention of ID documents is a bank policy; demo wipes synthetic data only |
| Wiretap Law 1979 / PPA 1/2017 | binding | no recording or transcript in the demo; transcript storage off by default |
| BoI interagency AI report Dec 2025 ([press](https://www.boi.org.il/publications/pressreleases/24-12-25/)) | guidance | explainability of the system ("why didn't we call") |

Corrections: the "14-day cancellation under the Fair Credit Law" seen on secondary sites is not in the law; the
fee-free cancellation is **3 business days** (311A). No BoI letter specific to generative AI was found.

## 6. Competitive landscape (what we take, without expanding scope)
- **Blend Autopilot** — follow-ups while the borrower is still in session → self-service first.
- **Salesforce Digital Origination** — document matrix keyed by applicant profile and product → requirement engine.
- **Sphera / LendingIQ** — reminders day 1/3/7 then human day 10 → attempt caps + escalation.
- **Skit.ai / Kore.ai** — disputes and hardship go to a human; do-not-call scrubbing → hard guards.
- **Ocrolus / Inscribe** — payslip ↔ statement cross-check, reasons shown to the underwriter → P1 cross-check.
- **nCino** — chat answers from the actual loan file → existing agent tools.

## 7. Assumptions requiring bank verification
Document list per purpose; proof-of-purpose types and age; contact hours, days and holidays; consent model and
channels; attempt caps; confidence thresholds per document type; definition of "ready for banker"; retention;
who may publish policy and whether four-eyes is required; whether outbound AI calls are permitted at all.

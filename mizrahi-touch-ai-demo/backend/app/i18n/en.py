"""English for the customer app: the closed vocabularies of the service, keyed by the same codes and ids the Hebrew
uses (readiness states, outcomes, reason codes, rubric criteria, policy requirements, products and purposes, demo
personas). Each table mirrors a Hebrew table elsewhere in the code; a code missing here simply gets no English
sibling and the app shows the Hebrew original. tests/test_i18n_en.py checks these tables cover the Hebrew ones.

House style: plain, professional retail-banking English; "you" for the customer; the bank's checks are a document
review, never an approval. Names of the synthetic demo people and companies have display-only Latin spellings."""
from __future__ import annotations

from typing import Optional

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]


def month(ym: Optional[str]) -> str:
    """'2026-09' → 'September 2026'."""
    if not ym or len(ym) < 7:
        return ym or ""
    return f"{MONTHS[int(ym[5:7]) - 1]} {ym[:4]}"


def month_name(ym: str) -> str:
    return MONTHS[int(ym[5:7]) - 1]


def months(yms: list[str]) -> str:
    """['2026-07', '2026-08', '2026-09'] → 'July, August and September 2026'."""
    if not yms:
        return ""
    if len({m[:4] for m in yms}) == 1:
        return join([month_name(m) for m in yms]) + f" {yms[0][:4]}"
    return join([month(m) for m in yms])


def day(iso: str) -> str:
    """'2026-07-01' → '1 Jul 2026'."""
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MONTHS[int(m) - 1][:3]} {y}"


def join(items: list[str]) -> str:
    """'A', 'A and B', 'A, B and C'."""
    items = [i for i in items if i]
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def ils(n: float) -> str:
    return f"₪{n:,.0f}"


# ---------------------------------------------------------------- the synthetic demo people and companies
NAMES = {
    "עידו לוי": "Ido Levi", "נועה לוי": "Noa Levi", "עידו לביא": "Ido Lavi", "נועה לביא": "Noa Lavi",
    "מיכל ברק": "Michal Barak", "יואב כרמי": "Yoav Karmi", "שירן אזולאי": "Shiran Azulay", "אלון פרידמן": "Alon Friedman",
    "רועי שטרן": "Roi Stern", "מאיה שטרן": "Maya Stern", "גלעד ששון": "Gilad Sasson", "רחל שטרן": "Rachel Stern",
    "דנה כהן": "Dana Cohen", "אורי לוי": "Ori Levi", "מאיה רוזן": "Maya Rosen", "אבי שגיא": "Avi Sagi",
    "עידו": "Ido", "נועה": "Noa", "מיכל": "Michal", "יואב": "Yoav", "שירן": "Shiran", "אלון": "Alon", "רועי": "Roi",
    "מאיה": "Maya", "גלעד": "Gilad", "דנה": "Dana", "אורי": "Ori", "רחל": "Rachel",
    "ש.ג. מערכות מיזוג בע״מ": "S.G. Air-Conditioning Systems Ltd.", "כרמי צילום": "Karmi Photography",
    "אזולאי עיצוב פנים": "Azulay Interior Design", "פרידמן הדרכות": "Friedman Training",
    "סטודיו מאיה שטרן, אדריכלות": "Maya Stern Studio, Architecture",
    # employers the customers declared (mock_bank); a document shows the employer exactly as printed
    "אביב מערכות דיגיטל בע״מ": "Aviv Digital Systems Ltd.", "אופק לוגיסטיקה בע״מ": "Ofek Logistics Ltd.",
    "אורן פתרונות תוכנה בע״מ": "Oren Software Solutions Ltd.", "גלי טכנולוגיות בע״מ": "Gali Technologies Ltd.",
    "שחף הנדסה בע״מ": "Shahaf Engineering Ltd.",
}


def name(he: Optional[str]) -> str:
    """A demo person's or company's Latin spelling; anyone else (a name the customer typed) exactly as given."""
    return NAMES.get(he or "", he or "")


def names(he_list: list[str]) -> str:
    return join([name(n) for n in he_list])


# ---------------------------------------------------------------- the bank's catalogue (demo)
CASE_TITLES = {
    "הלוואה לרכישת רכב": "Car purchase loan", "הלוואה לרכישת רכב · תיק נוסף": "Car purchase loan · second case",
    "הלוואה לשיפוץ": "Renovation loan", "הלוואה לשיפוץ, בקשה משותפת": "Renovation loan, joint application",
    "הלוואה לרכב · תיק א׳": "Car loan · case A", "הלוואה לרכב · תיק ב׳": "Car loan · case B",
    "הלוואה לרכב · תיק ג׳": "Car loan · case C", "השלמת מסמכים · תיק ד׳": "Document completion · case D",
    "ללא הרשאת קשר · תיק ה׳": "No contact consent · case E", "פער הכנסה · תיק ו׳": "Income gap · case F",
    "הלוואה לרכב · תיק ז׳": "Car loan · case G", "הלוואה לרכב · תיק ח׳": "Car loan · case H",
    "מימון ציוד — ש.ג. מערכות מיזוג בע״מ": "Equipment financing — S.G. Air-Conditioning Systems Ltd.",
}
PRODUCTS = {"הלוואה לכל מטרה": "All-purpose loan", "מימון עסקי, פנייה ראשונית": "Business financing, initial request"}
PURPOSES = {  # policy product purposes (loan_policy.product.purposes), by id: label, proof
    "car": ("Buying a car", "A price quote or invoice from the dealership"),
    "renovation": ("Renovation", "A quote from the contractor"),
    "celebration": ("A family celebration", "A contract or quote from the venue or supplier"),
    "other": ("Another purpose", "A document that describes the purpose of the loan"),
    "business_equipment": ("Business equipment financing", "A quote for the equipment"),
    "working_capital": ("Working capital for the business", "A cash-flow forecast or a breakdown of how the financing will be used"),
}
PURPOSE_LABELS = {"רכישת רכב": "Buying a car", "שיפוץ": "Renovation", "אירוע משפחתי": "A family celebration",
                  "מטרה אחרת": "Another purpose", "מימון ציוד לעסק": "Business equipment financing",
                  "הון חוזר לעסק": "Working capital for the business"}


def case_title(he: str) -> str:
    """A prepared case's title, or a created application's '<product> · <purpose>' / '<purpose> — <company>'."""
    if he in CASE_TITLES:
        return CASE_TITLES[he]
    for sep in (" · ", " — "):
        if sep in he:
            parts = he.split(sep)
            out = [PRODUCTS.get(p) or PURPOSE_LABELS.get(p) or NAMES.get(p) for p in parts]
            if all(out):
                return sep.join(out)
            if sep == " — " and out[0]:
                return out[0] + sep + parts[1]          # a company name the customer typed stays as typed
    return ""


LOAN_NOTES = {"רכב משפחתי חדש": "A new family car", "רכב משפחתי": "A family car", "רכב לעבודה": "A car for work",
              "רכב לעסק ולמשפחה": "A car for the business and the family", "שיפוץ הדירה": "Renovating the apartment",
              "מערכות מיזוג לפרויקט חדש": "Air-conditioning systems for a new project"}
BANKER_ROLES = {"הבנקאית שלך": "Your banker", "הבנקאי שלך": "Your banker", "הבנקאית המלווה": "Your relationship banker",
                "בנקאית אשראי": "Credit banker", "בנקאי אשראי": "Credit banker"}
MEETING_TYPES = {"שיחת וידאו עם הבנקאית": "Video call with your banker"}
DECLARATION_NOTES = {"הוצהר בטופס הבקשה": "Declared on the application form", "שכר קבוע": "Fixed salary",
                     "ייתכנו רכיבים משתנים": "May include variable components",
                     "הוצהר בטופס הבקשה, כולל בונוס צפוי": "Declared on the application form, including an expected bonus"}
BANK_STAGES = {"APPLICATION_SUBMITTED": "Application submitted", "DOCUMENTS_AND_CHECKS": "Document completion",
               "BANKER_REVIEW": "Banker review", "SIGNING": "Signing the loan agreement", "DISBURSEMENT": "Loan disbursement"}
STAGE_NOTE = "The stage list is for display only; the official stage is set in the bank's systems."
BANK = {"מזרחי־טפחות": "Mizrahi-Tefahot"}
PROFILE_LABELS = {"שכירה": "Salaried", "שכיר": "Salaried", "עוסק פטור": "Exempt dealer (Osek Patur)",
                  "עוסקת מורשית": "Licensed dealer (Osek Murshe)", "שכיר וגם עצמאי": "Salaried and self-employed",
                  "שני לווים": "Two borrowers", "חברה בע״מ": "Limited company"}


def account_label(he: str) -> str:
    fixed = {"חשבון עסקי של החברה": "The company's business account", "חשבון עו״ש משותף": "Joint current account",
             "חשבון עו״ש של רועי ואמו": "Current account of Roi and his mother"}
    if he in fixed:
        return fixed[he]
    if he.startswith("חשבון עו״ש "):
        return "Current account " + he.removeprefix("חשבון עו״ש ")
    return he


OTHER_HOLDERS = {"רחל שטרן, בעלת חשבון, אינה לווה בבקשה": "Rachel Stern, an account holder who is not a borrower on this application"}

# ---------------------------------------------------------------- document policy (loan_policy.document_requirements)
FAMILY = {"payslip": "Payslip", "id_document": "ID card", "bank_statement": "Bank statement",
          "purpose_proof": "Proof of purpose", "tax_form": "Tax assessment / CPA letter",
          "business_registration": "Business registration certificate", "pnl_statement": "Profit and loss statement",
          "company_registry": "Company registry extract", "signatory_authority": "Authorized signatories",
          "financial_statements": "Financial statements", "business_bank_statement": "Business bank statements"}
# the same families as a noun in a sentence ("upload your …")
FAMILY_NOUN = {"payslip": "payslip", "id_document": "ID card", "bank_statement": "bank statement",
               "purpose_proof": "proof of the loan's purpose", "tax_form": "tax assessment or CPA letter",
               "business_registration": "business registration certificate", "pnl_statement": "profit and loss statement"}
ENTITY = {"individual": "Personal loan", "company": "Financing for a limited company"}
INCOME = {"salaried": "Salaried", "self_employed": "Self-employed", "allowance": "Receives an allowance"}
REGISTRATION = {"vat_exempt": "Exempt dealer (Osek Patur)", "vat_registered": "Licensed dealer (Osek Murshe)"}
ROLE = {"primary": "Main borrower", "co_borrower": "Co-borrower", "authorized_signatory": "Authorized signatory"}
POLICY_DISCLAIMER = "The document list comes from the application's document policy; your banker may ask for more documents."
# id → (label with {months}, hint, why, alternatives)
REQUIREMENTS: dict[str, tuple[str, str, str, list[str]]] = {
    "ID_CARD": ("ID card", "A clear photo of your ID card, including the appendix if there is one",
                "Identifies each borrower (or signatory) and lets us compare the name and ID number with the other documents",
                ["Biometric ID card (both sides)", "A valid Israeli passport"]),
    "PAYSLIPS": ("Last {months} payslips", "Your payslips for the most recent months, as you received them from your employer",
                 "Verifies salary income — needed from every borrower who receives a salary, even with business income too", []),
    "BANK_STATEMENTS": ("Bank statements for the last 3 months", "Transactions of every declared account, continuous and without gaps",
                        "Shows actual income and spending. A joint account is checked once for all its borrowers",
                        ["A transaction printout from the bank's website or app",
                         "A balance and transactions confirmation signed by the bank"]),
    "PURPOSE_PROOF": ("Proof of the loan's purpose", "A quote, invoice or agreement that describes what the loan is for",
                      "Shows that the loan amount matches the stated purpose — one document per application",
                      ["Price quote", "Invoice", "Purchase agreement or order"]),
    "TAX_ASSESSMENT": ("Tax assessment / CPA letter", "For the self-employed: your latest tax assessment or an up-to-date CPA letter",
                       "Verifies business income — the self-employed have no payslip, so income is verified with the Tax "
                       "Authority or a CPA",
                       ["Income tax assessment for the last year", "Annual income tax return (Form 1301) as filed",
                        "A CPA letter on last year's income"]),
    "VAT_EXEMPT_CERT": ("Exempt dealer certificate", "Registration as an exempt dealer (Osek Patur) from the Tax Authority",
                        "Confirms the business is registered as an exempt dealer. Exempt dealers file no periodic VAT reports",
                        ["Exempt dealer certificate", "VAT file opening confirmation (exempt dealer)",
                         "Annual turnover declaration for an exempt dealer"]),
    "VAT_DEALER_CERT": ("Licensed dealer certificate", "Registration as a licensed dealer (Osek Murshe) with VAT",
                        "Confirms the business's registration as a licensed dealer and the dealer number on its reports",
                        ["Licensed dealer certificate", "VAT registration confirmation"]),
    "PNL_STATEMENT": ("Recent profit and loss statement", "A profit and loss statement for the current year, signed by a CPA",
                      "Shows the business's recent profitability — it completes the tax assessment, which covers last year",
                      ["Profit and loss statement signed by a CPA", "Audited profit and loss statement for the last year",
                       "Periodic VAT reports for the last six months"]),
    "COMPANY_EXTRACT": ("Up-to-date company extract", "A Companies Registry extract issued in the last month",
                        "Confirms the company exists, its number, its shareholders and its directors",
                        ["Companies Registry extract", "Certificate of incorporation and company details printout"]),
    "SIGNATORY_AUTHORITY": ("Authorized signatories resolution", "A board resolution or a lawyer's/CPA's confirmation of the authorized signatories",
                            "Shows who may bind the company and with which signature combination",
                            ["Board resolution on signing rights", "A lawyer's confirmation of authorized signatories",
                             "A CPA's confirmation of authorized signatories"]),
    "COMPANY_FINANCIALS": ("Audited financial statements", "The company's audited financial statements for the last year",
                           "The basis for the banker's business review — the demo does no business underwriting",
                           ["Audited financial statements for the last year", "Reviewed financial statements, if the audit is not finished"]),
    "COMPANY_INTERIM": ("Profit and loss for the current period", "Interim statements or a trial balance signed by a CPA",
                        "Brings the annual statements up to date", ["Interim profit and loss statement", "Trial balance signed by a CPA"]),
    "BUSINESS_STATEMENTS": ("Business bank statements for the last 6 months", "Transactions of the company's account",
                            "The company's actual cash flow", ["Transaction printout of the company account",
                                                               "A balance and transactions confirmation from the bank"]),
}

# ---------------------------------------------------------------- readiness, outcomes, statuses
READINESS = {"NOT_CHECKED": "Not checked yet", "CHECKING": "Checking", "RECHECKING": "Checking again",
             "ACTION_REQUIRED": "Action needed from you", "READY_FOR_HUMAN_REVIEW_WITH_OPEN_FINDINGS":
             "Ready for the banker's review, with open findings", "READY_FOR_HUMAN_REVIEW": "Ready for the banker's review",
             "PREPARATION_CONFIRMED": "The banker confirmed the application's documents are prepared",
             "ERROR": "The check failed and needs attention"}
AI_STATE = {"required_missing": "Not uploaded yet", "needs_customer_action": "Needs completing",
            "needs_banker_review": "With the banker", "checking": "Checking", "uploaded_unreadable": "Unreadable",
            "extracted": "Checked, valid", "not_evaluated_in_demo": "Not checked automatically",
            "preparation_confirmed": "Confirmed by the banker", "received_pending_review": "Received · awaiting the banker's review",
            "accepted_by_banker": "Accepted by the banker"}
INACTIVE_STATE = "No longer needed — your income profile was updated"
OUTCOME = {"PASS": "Passed the AI check, awaiting the banker's acceptance",
           "ACCEPTED": "Accepted by the banker (document acceptance only, not a loan approval)",
           "REVIEW": "Needs the banker's review", "BLOCKER": "This document doesn't match the requirement — please upload a replacement",
           "IN_PROGRESS": "Checking", "NOT_COMPLETED": "The check didn't finish", "REPLACED": "Replaced by a new document",
           "INCOMPLETE": "Documents missing", "AWAITING_UPLOAD": "Waiting for documents",
           "CONFIRMED": "The banker confirmed the application's documents are prepared",
           "HUMAN_REVIEW_PENDING": "Received, awaiting the banker's review (no AI check for this document type)"}
OUTCOME_INCOME_REVIEW = "Needs the banker's review — an income gap was found"
DOC_STAGE = {"queued": "Waiting to be checked", "intake": "Receiving", "extract": "Reading and extracting",
             "verify_evidence": "Verifying evidence", "deterministic_checks": "Rule checks", "judge": "Checking against the rubric",
             "done": "Check complete", "retrying": "Retrying", "failed": "The check failed",
             "human_review": "Received · awaiting the banker's review"}
DESK_STATUS = {"ACCEPTED": "Accepted by the banker for the document review",
               "CORRECTION_REQUESTED": "The banker asked for a corrected document", "REPLACED": "Replaced by a document you uploaded"}
REPLACEMENT_STATUS = "A replacement document you uploaded"
DOC_TYPES = {"payslip": "Payslip", "bank_statement": "Bank statement", "id_document": "ID card", "purpose_proof": "Proof of purpose",
             "tax_form": "Tax form / CPA letter", "business_registration": "Business registration certificate",
             "pnl_statement": "Profit and loss statement", "application_form": "Application form", "other": "Other document",
             "unreadable": "Unreadable document"}
FIELDS = {"employee_name": "Employee name", "employee_id": "ID number", "employee_number": "Employee number",
          "employer_name": "Employer", "employer_id": "Employer company no.", "salary_period": "Pay period",
          "payment_date": "Payment date", "issue_date": "Issue date", "document_number": "Document no.",
          "gross_pay": "Gross pay", "total_deductions": "Total deductions", "net_pay": "Net pay",
          "holder_name": "Name", "holder_id": "ID number", "date_of_birth": "Date of birth", "expiry_date": "Valid until",
          "bank_name": "Bank", "account_number": "Account number", "statement_from": "Period from", "statement_to": "Period to",
          "closing_balance": "Closing balance", "issuer_name": "Supplier", "document_kind": "Document type", "subject": "Description",
          "total_amount": "Amount", "tax_year": "Tax year", "business_name": "Business name", "dealer_number": "Dealer number",
          "registration_type": "Registration type", "period_from": "Report period from", "period_to": "Report period to"}
FIELD_EMPLOYEE_ID_AS_PRINTED = "ID number (printed as 'employee ID')"

# rubric criteria (backend/rubrics/*.json, every version), by criterion id
CRITERIA = {
    "BS-01": "The document is a bank account statement", "BS-02": "The document is legible and complete",
    "BS-03": "The account holder is the applicant", "BS-04": "The statement period is printed and unambiguous",
    "BS-05": "The statement is recent", "BS-06": "No suspicious instructions or signs of alteration",
    "BS-07": "Evidence for the key fields was verified against the original file",
    "BR-01": "The document is a business registration certificate", "BR-02": "The document is legible and complete",
    "BR-03": "The business owner's name matches the applicant", "BR-04": "The registration type matches the requirement",
    "BR-05": "The dealer number matches the applicant's ID number", "BR-06": "No suspicious instructions in the document",
    "BR-07": "Evidence for the key fields was verified against the original file",
    "ID-01": "The document is an ID card", "ID-02": "The document is legible and complete",
    "ID-03": "The name and ID number match the applicant", "ID-04": "The ID number is valid (check digit)",
    "ID-05": "The ID card is valid", "ID-06": "No suspicious instructions or signs of alteration",
    "ID-07": "Evidence for the key fields was verified against the original file",
    "IS-01": "Every required month is covered by its own payslip", "IS-02": "No unresolved duplicate months",
    "IS-03": "Each payslip is assigned to the right borrower", "IS-04": "Declared income is consistent with the payslips",
    "IS-05": "The documents are recent", "IS-06": "Every required salary document passed its check",
    "PS-01": "The document is a payslip", "PS-02": "The document is legible and complete",
    "PS-03": "The employee matches the borrower the document was assigned to", "PS-04": "The pay period is printed and unambiguous",
    "PS-05": "Gross pay and net pay are printed", "PS-06": "Arithmetic: gross minus deductions equals net",
    "PS-07": "The employer is identified on the document", "PS-08": "No suspicious instructions or signs of alteration",
    "PS-09": "Evidence for the key fields was verified against the original file",
    "PS-10": "The payment date, if printed, is plausible for the pay period",
    "PL-01": "The document is a profit and loss statement (or a periodic VAT report)", "PL-02": "The document is legible and complete",
    "PL-03": "The business owner's name matches the applicant", "PL-04": "The report period is recent",
    "PL-05": "The preparer's details (CPA / representative) are printed", "PL-06": "No suspicious instructions in the document",
    "PL-07": "Evidence for the key fields was verified against the original file",
    "PP-01": "The document is a price quote, invoice or agreement", "PP-02": "The document is legible and complete",
    "PP-03": "The supplier's name and the amount are printed", "PP-04": "The document is recent",
    "PP-05": "The document matches the stated loan purpose", "PP-06": "No suspicious instructions or signs of alteration",
    "PP-07": "Evidence for the key fields was verified against the original file",
    "TX-01": "The document is a tax assessment or CPA letter", "TX-02": "The document is legible and complete",
    "TX-03": "The taxpayer's name matches the applicant", "TX-04": "The tax year is recent",
    "TX-05": "No suspicious instructions in the document", "TX-06": "Evidence for the key fields was verified against the original file",
}

# ---------------------------------------------------------------- findings (review/case_review.py, review/reason_codes.py)
# a document-level finding: (title, message); {doc} is the family noun, {file} the file name. A Hebrew message that also
# carries the reviewer's own explanation keeps that part in Hebrew: the app shows it separately as the original wording.
DOC_FINDINGS = {
    "UNEXPECTED_DOCUMENT_TYPE": ("This document isn't a {doc}", "The file {file} isn't a {doc}. Please upload a {doc} instead."),
    "DOCUMENT_UNREADABLE": ("The document can't be read", "We couldn't read {file}. Please upload a clearer copy (the original PDF or a sharp photo)."),
    "BORROWER_MISMATCH": ("The document isn't in the applicant's name", "The document {file} isn't in the applicant's name."),
    "ID_NUMBER_INVALID": ("The ID number isn't valid", "The ID number in {file} isn't valid. It was passed to the banker for review."),
    "ID_EXPIRED": ("The ID card has expired", "The ID card has expired. Please upload a valid ID card."),
    "PERIOD_UNCLEAR": ("The document's period isn't clear", "We couldn't tell which period {file} covers."),
    "DOCUMENT_STALE": ("The document isn't recent", "The document {file} isn't recent enough."),
    "MANDATORY_FIELD_MISSING": ("A required detail is missing", "A required detail is missing in {file}."),
    "PURPOSE_MISMATCH": ("The proof doesn't match the loan's purpose", "The document {file} doesn't match the stated purpose of the loan."),
    "UNTRUSTED_INSTRUCTION_IN_DOCUMENT": ("Suspicious text in the document", "The document {file} contains text addressed to the system or the reviewer. "
                                          "It was not acted on; the document was passed to the banker for review."),
    "EVIDENCE_UNVERIFIED": ("Evidence not verified against the file", "Some key values in {file} could not be verified against the original file."),
    "REGISTRATION_TYPE_MISMATCH": ("The registration type doesn't match the requirement", "Please upload the matching registration certificate."),
    "DEALER_NUMBER_MISMATCH": ("The dealer number doesn't match the applicant", "The dealer number in {file} doesn't match the applicant. It was passed to the banker for review."),
    "ISSUER_DETAILS_MISSING": ("The preparer's details are missing", "The preparer's details are missing in {file}. It was passed to the banker for review."),
    "INTERNAL_ARITHMETIC_MISMATCH": ("The payslip's amounts don't add up", "The amounts in {file} don't add up."),
    "PAY_DATE_INCONSISTENT": ("Unusual payment date", "The payment date in {file} doesn't fit the pay period."),
}
PAYSLIP_FINDINGS = {  # the payslip rubric words some of them for payslips (case_review.DOC_FINDING_TEXT)
    "UNEXPECTED_DOCUMENT_TYPE": ("This document isn't a payslip", "The document {file} isn't a payslip. Please upload a payslip instead."),
    "PERIOD_UNCLEAR": ("The pay period isn't clear", "We couldn't identify a single pay period in {file}."),
    "MANDATORY_FIELD_MISSING": ("A required field is missing on the payslip", "A required field is missing on {file}."),
    "INTERNAL_ARITHMETIC_MISMATCH": ("The payslip's amounts don't add up", "The amounts on {file} don't add up."),
    "UNTRUSTED_INSTRUCTION_IN_DOCUMENT": ("Suspicious text in the document", "The payslip {file} contains text addressed to the system or the reviewer. "
                                          "It was not acted on; the document was passed to the banker for review."),
    "EVIDENCE_UNVERIFIED": ("Evidence not verified against the file", "Some key values on {file} could not be verified against the original file."),
    "PAY_DATE_INCONSISTENT": ("Unusual payment date", "The payment date on {file} doesn't fit the pay period."),
}
UNCERTAIN_FINDINGS = {
    "UNEXPECTED_DOCUMENT_TYPE": ("Not clear whether this is a {doc}", "The AI check couldn't tell whether {file} is a {doc}. It was passed to the banker for review."),
    "DOCUMENT_UNREADABLE": ("Not clear whether the document is fully legible", "The AI check couldn't tell whether {file} is legible and complete. It was passed to the banker for review."),
}
UNCERTAIN_FALLBACK = "The AI check couldn't decide; it was passed to the banker for review."
# the short customer wording of an open item (reason_codes.CUSTOMER_TEXT_HE)
CUSTOMER_TEXT = {"UNEXPECTED_DOCUMENT_TYPE": "The uploaded document isn't the one requested",
                 "DOCUMENT_UNREADABLE": "The document can't be read", "BORROWER_MISMATCH": "The document isn't in the applicant's name",
                 "ID_EXPIRED": "The ID card has expired", "DOCUMENT_STALE": "The document isn't recent",
                 "PERIOD_UNCLEAR": "The period on the document isn't clear", "REQUIRED_PERIOD_MISSING": "A payslip for a required month is missing",
                 "REQUIRED_DOCUMENT_MISSING": "Not uploaded yet", "STATEMENT_PERIOD_GAP": "A period is missing from the bank statements",
                 "MANDATORY_FIELD_MISSING": "A detail is missing from the document",
                 "REGISTRATION_TYPE_MISMATCH": "The registration type doesn't match the requirement"}

# ---------------------------------------------------------------- follow-up (followup/orchestrator.CUSTOMER_STATE_HE)
FOLLOWUP_STATE = {
    "אפשר להשלים את המסמכים כאן באפליקציה": "You can complete your documents here in the app",
    "אם לא תספיקו להשלים, נחזור אליכם בשיחה": "If you don't get to it, we'll call you",
    "אנחנו מתקשרים אליכם כעת": "We're calling you now", "אנחנו בשיחה איתכם כעת": "We're on a call with you now",
    "שלחנו לכם קישור מאובטח להעלאת המסמך": "We sent you a secure link to upload the document",
    "נציג הבנק יחזור אליכם": "A bank representative will get back to you",
    "כל המסמכים התקבלו ונבדקו": "All documents were received and checked",
}
REMINDER = "{first_name}, a reminder: to complete your application we still need {missing_documents}."
# the seeded Hebrew reminder template REMINDER translates; a template edited in Admin Settings has no English
REMINDER_SOURCE_HE = "{{first_name}}, תזכורת: להשלמת הבקשה חסר {{missing_documents}}."

# ---------------------------------------------------------------- upload route notes and customer-facing errors
DUPLICATE_UPLOAD = "This file was already uploaded to your application, so it wasn't checked again."
DUPLICATE_OTHER_BORROWER = "The same file was already uploaded for {owner}. If it belongs to another borrower, please upload the right document."
# exact Hebrew messages of errors a customer can meet → English (an unknown message stays as it is)
ERRORS = {
    "הפעולה כבר אינה רלוונטית למצב התיק הנוכחי.": "This action no longer applies to your application.",
    "השיחה שממנה הגיעה הפעולה לא נמצאה.": "The conversation this action came from could not be found.",
    "הפעולה שייכת לתיק אחר ולא בוצעה.": "This action belongs to another application and was not carried out.",
    "הפעולה לא הוצעה בשיחה הזו ולא בוצעה.": "This action wasn't offered in this conversation and was not carried out.",
    "הטיוטה לא נמצאה, אפשר להתחיל בקשה חדשה": "This draft wasn't found — you can start a new application",
    "הבקשה כבר נפתחה, אי אפשר לשנות את התשובות": "The application is already open, so the answers can't be changed",
    "אי אפשר לערוך את הפרט הזה": "This detail can't be edited",
    "שאלה לא מוכרת": "Unknown question",
    "הגעתם למספר המרבי של טיוטות פתוחות": "You've reached the maximum number of open drafts",
    "נא להזין מספר": "Please enter a number",
    "נא להזין שם פרטי ושם משפחה (2–30 תווים)": "Please enter a first and last name (2–30 characters)",
    "הגעתם למספר המרבי של בקשות פתוחות": "You've reached the maximum number of open applications",
    "ההודעה ריקה": "The message is empty",
    "השאלה אינה רלוונטית לתשובות הקודמות": "This question doesn't apply to the earlier answers",
    "ללווה הנוסף צריך להיות מספר זהות משלו": "The co-borrower needs their own ID number",
    "מספר הזהות אינו תקין (9 ספרות עם ספרת ביקורת)": "The ID number isn't valid (9 digits with a check digit)",
    "נא לבחור אחת מהאפשרויות": "Please choose one of the options",
    "נא לבחור לפחות מקור הכנסה אחד": "Please choose at least one income source",
    "נא להזין 2–60 תווים": "Please enter 2–60 characters",
    "עוד אין סימולציה לאשר": "There's no simulation to confirm yet",
    "עוד אין סימולציה לשמור": "There's no simulation to save yet",
    "עוד לא ענינו על כל השאלות": "Not all the questions have been answered yet",
}


def error(message_he: str) -> Optional[str]:
    """The English of a known customer-facing error message (exact, or one of the formatted range messages)."""
    import re
    if message_he in ERRORS:
        return ERRORS[message_he]
    m = re.fullmatch(r"נא לבחור מספר תשלומים בין (\d+) ל־(\d+)", message_he)
    if m:
        return f"Please choose between {m.group(1)} and {m.group(2)} payments"
    m = re.fullmatch(r"הסכום צריך להיות בין ([\d,]+) ל־([\d,]+) ₪", message_he)
    if m:
        return f"The amount must be between ₪{m.group(1)} and ₪{m.group(2)}"
    return None

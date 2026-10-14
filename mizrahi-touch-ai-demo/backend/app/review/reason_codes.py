"""The reason-code catalog: every code a finding can carry, with its Hebrew wording for the customer and the banker.

Document-level codes come from the rubrics' criteria; case-level codes from case_review. `{doc}` is the document
family in Hebrew ("תעודת הזהות", "דף העו״ש"…), `{file}` the file name, `{detail}` the criterion's explanation."""
from __future__ import annotations

DOC_HE = {"payslip": "תלוש שכר", "id_document": "תעודת זהות", "bank_statement": "דף עו״ש",
          "purpose_proof": "אסמכתה למטרת ההלוואה", "tax_form": "שומת מס / אישור רו״ח",
          "business_registration": "אישור רישום עוסק", "pnl_statement": "דוח רווח והפסד"}

# (title, message) for a failed check on a non-payslip document; payslips keep their wording in case_review.DOC_FINDING_TEXT
DOCUMENT = {
    "UNEXPECTED_DOCUMENT_TYPE": ("המסמך אינו {doc}", "הקובץ {file} אינו {doc}. יש להעלות {doc} במקומו."),
    "DOCUMENT_UNREADABLE": ("המסמך אינו קריא", "לא ניתן לקרוא את {file}. יש להעלות עותק ברור יותר (PDF מקורי או צילום חד)."),
    "BORROWER_MISMATCH": ("המסמך אינו על שם המבקש/ת", "המסמך {file} אינו על שם המבקש/ת: {detail}"),
    "ID_NUMBER_INVALID": ("מספר הזהות אינו תקין", "במסמך {file}: {detail}. הועבר לבדיקת בנקאי."),
    "ID_EXPIRED": ("תוקף תעודת הזהות פג", "{detail}. יש להעלות תעודת זהות בתוקף."),
    "PERIOD_UNCLEAR": ("תקופת המסמך לא ברורה", "במסמך {file} לא ניתן לזהות את התקופה שהוא מכסה."),
    "DOCUMENT_STALE": ("המסמך אינו עדכני", "{detail}"),
    "MANDATORY_FIELD_MISSING": ("חסר פרט חובה במסמך", "במסמך {file} {detail}"),
    "PURPOSE_MISMATCH": ("האסמכתה אינה תואמת למטרת ההלוואה", "במסמך {file}: {detail}"),
    "UNTRUSTED_INSTRUCTION_IN_DOCUMENT": ("טקסט חשוד במסמך", "במסמך {file} נמצא טקסט המופנה למערכת או לבודק. הטקסט לא בוצע; המסמך הועבר לבדיקת בנקאי."),
    "EVIDENCE_UNVERIFIED": ("ראיה לא אומתה מול הקובץ", "במסמך {file} חלק מהערכים המכריעים לא אומתו מול הקובץ המקורי: {detail}"),
    "REGISTRATION_TYPE_MISMATCH": ("סוג הרישום אינו תואם לדרישה", "{detail}. יש להעלות את אישור הרישום המתאים."),
    "DEALER_NUMBER_MISMATCH": ("מספר העוסק אינו תואם למבקש/ת", "במסמך {file}: {detail}. הועבר לבדיקת בנקאי."),
    "ISSUER_DETAILS_MISSING": ("פרטי עורך הדוח חסרים", "במסמך {file}: {detail}. הועבר לבדיקת בנקאי."),
}
UNCERTAIN = {
    "UNEXPECTED_DOCUMENT_TYPE": ("לא ברור אם המסמך הוא {doc}", "בדיקת ה-AI לא הצליחה לקבוע אם {file} הוא {doc}. המסמך הועבר לבדיקת בנקאי."),
    "DOCUMENT_UNREADABLE": ("לא ברור אם המסמך קריא במלואו", "בדיקת ה-AI לא הצליחה לקבוע אם {file} קריא ושלם. המסמך הועבר לבדיקת בנקאי."),
}

# case-level coverage codes: facts about what is missing, never closed or dismissed by anyone but new evidence
REQUIRED_DOCUMENT_MISSING = "REQUIRED_DOCUMENT_MISSING"
STATEMENT_PERIOD_GAP = "STATEMENT_PERIOD_GAP"
COVERAGE = ("REQUIRED_PERIOD_MISSING", "DUPLICATE_PERIOD", REQUIRED_DOCUMENT_MISSING, STATEMENT_PERIOD_GAP)

# short customer-facing wording (no internal codes, scores or policy details)
CUSTOMER_SHORT = {
    "UNEXPECTED_DOCUMENT_TYPE": "המסמך שהועלה אינו המסמך המבוקש",
    "DOCUMENT_UNREADABLE": "המסמך אינו קריא",
    "BORROWER_MISMATCH": "המסמך אינו על שם המבקש/ת",
    "ID_EXPIRED": "תוקף התעודה פג",
    "DOCUMENT_STALE": "המסמך אינו עדכני",
    "PERIOD_UNCLEAR": "התקופה במסמך אינה ברורה",
    "REQUIRED_PERIOD_MISSING": "חסר תלוש לחודש נדרש",
    REQUIRED_DOCUMENT_MISSING: "המסמך טרם הועלה",
    STATEMENT_PERIOD_GAP: "חסרה תקופה בדפי העו״ש",
    "MANDATORY_FIELD_MISSING": "חסר פרט במסמך",
    "REGISTRATION_TYPE_MISMATCH": "סוג הרישום אינו תואם לדרישה",
}


def document_text(code: str, family: str, filename: str, detail: str, uncertain: bool, fallback_title: str) -> tuple[str, str]:
    doc = DOC_HE.get(family, "המסמך")
    table = UNCERTAIN if uncertain and code in UNCERTAIN else DOCUMENT
    title, template = table.get(code, (fallback_title, "{detail}" if not uncertain else "{detail} — לא הוכרע בבדיקת ה-AI, הועבר לבדיקת בנקאי."))
    return title.format(doc=doc), template.format(doc=doc, file=filename, detail=detail)

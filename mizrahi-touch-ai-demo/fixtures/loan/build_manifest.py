"""Builds fixtures/presenter/presenter_scenarios_manifest.json — the presenter pane's personal-loan scenarios.

Featured cards (executive demo cases 006, 011, 008, 009) and the test-scenario library (cases 004 and 005) use the
synthetic loan documents in fixtures/presenter/loan_set and four unmodified golden-set payslips. Expected outcomes are
the routing the scenario is designed to show, written by hand — never a live result and never fed into the app.

    backend/.venv/bin/python fixtures/loan/build_manifest.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PRESENTER = Path(__file__).resolve().parents[1] / "presenter"
OUT = PRESENTER / "presenter_scenarios_manifest.json"
ID, PAY, BANK, PURPOSE = "ID_CARD:BRW-A", "PAYSLIPS:BRW-A", "BANK_STATEMENTS:ACC-1", "PURPOSE_PROOF"

DOCS = [
    # id, path under fixtures/presenter, name, category, requirement, verdict, printed month, net, note, follow-up
    ("loan/id_card_ido.pdf", "loan_set/id_card_ido.pdf", "תעודת זהות — עידו לוי", "ID_CARD", ID, "VALID", None, None,
     "תעודה סינתטית בתוקף עד 20.05.2031; השם ומספר הזהות (DEMO-ID-001) תואמים למבקש.", None),
    ("loan/id_card_ido_EXPIRED.pdf", "loan_set/id_card_ido_EXPIRED.pdf", "תעודת זהות — פג תוקף", "ID_CARD", ID, "INVALID", None, None,
     "תוקף התעודה פג ב־01.03.2025 — חוזרת ללקוח (ID_EXPIRED).", "ID_EXPIRED"),
    ("loan/id_card_ido_UNREADABLE.pdf", "loan_set/id_card_ido_UNREADABLE.pdf", "תעודת זהות — סריקה לא קריאה", "ID_CARD", ID,
     "NEEDS_REVIEW", None, None, "סריקה מטושטשת ללא שכבת טקסט: אין להמציא ערכים — המסמך אינו קריא (DOCUMENT_UNREADABLE).",
     "DOCUMENT_UNREADABLE"),
    ("01_INITIAL_UPLOADS/ido_2026_07.pdf", "golden_set/01_INITIAL_UPLOADS/ido_2026_07.pdf", "תלוש עידו — יולי 2026", "PAYSLIP", PAY,
     "VALID", "2026-07", 14400, "תלוש תקין; כל ערך מכריע מאומת מול שכבת הטקסט.", None),
    ("01_INITIAL_UPLOADS/ido_2026_08.pdf", "golden_set/01_INITIAL_UPLOADS/ido_2026_08.pdf", "תלוש עידו — אוגוסט 2026", "PAYSLIP", PAY,
     "VALID", "2026-08", 14700, "תלוש תקין.", None),
    ("01_INITIAL_UPLOADS/ido_2026_09.pdf", "golden_set/01_INITIAL_UPLOADS/ido_2026_09.pdf", "תלוש בשם ״ספטמבר״ — מודפס אוגוסט",
     "PAYSLIP", PAY, "VALID", "2026-08", 14700,
     "תלוש תקין של אוגוסט בשם קובץ של ספטמבר: ספטמבר עדיין חסר (REQUIRED_PERIOD_MISSING), אוגוסט כפול (DUPLICATE_PERIOD).",
     "REQUIRED_PERIOD_MISSING"),
    ("02_CORRECTION/ido_2026_09_CORRECTED.pdf", "golden_set/02_CORRECTION/ido_2026_09_CORRECTED.pdf", "תלוש עידו — ספטמבר 2026",
     "PAYSLIP", PAY, "VALID", "2026-09", 15000, "התלוש החסר — סוגר את חודש ספטמבר.", None),
    ("loan/statement_ido_2026-07_09.pdf", "loan_set/statement_ido_2026-07_09.pdf", "דף עו״ש — יולי עד ספטמבר 2026", "BANK_STATEMENT",
     BANK, "VALID", None, None, "דף אחד שמכסה 01.07–30.09.2026 — מכסה את 90 הימים הנדרשים.", None),
    ("loan/statement_ido_2026-07.pdf", "loan_set/statement_ido_2026-07.pdf", "דף עו״ש — יולי 2026", "BANK_STATEMENT", BANK, "VALID",
     None, None, "דף חודשי תקין.", None),
    ("loan/statement_ido_2026-08.pdf", "loan_set/statement_ido_2026-08.pdf", "דף עו״ש — אוגוסט 2026", "BANK_STATEMENT", BANK, "VALID",
     None, None, "הדף שסוגר את הפער של אוגוסט.", None),
    ("loan/statement_ido_2026-09.pdf", "loan_set/statement_ido_2026-09.pdf", "דף עו״ש — ספטמבר 2026", "BANK_STATEMENT", BANK, "VALID",
     None, None, "דף חודשי תקין.", None),
    ("loan/statement_ido_STALE_2026-04_06.pdf", "loan_set/statement_ido_STALE_2026-04_06.pdf", "דף עו״ש ישן — אפריל עד יוני 2026",
     "BANK_STATEMENT", BANK, "VALID", None, None,
     "הדף עצמו תקין, אבל הסט אינו עדכני: חסרה התקופה עד 12.09.2026 (STATEMENT_PERIOD_GAP).", "STATEMENT_PERIOD_GAP"),
    ("loan/car_quote_ido.pdf", "loan_set/car_quote_ido.pdf", "הצעת מחיר לרכב — 01.10.2026", "PURPOSE_PROOF", PURPOSE, "VALID",
     None, None, "הצעת מחיר עדכנית מאוטו־דמו על ₪118,000 — מתאימה למטרה ״רכישת רכב״.", None),
    ("loan/car_quote_ido_OLD.pdf", "loan_set/car_quote_ido_OLD.pdf", "הצעת מחיר ישנה — 15.03.2026", "PURPOSE_PROOF", PURPOSE,
     "NEEDS_REVIEW", None, None, "הופקה לפני יותר מ־90 יום — מבקשים אסמכתה עדכנית (DOCUMENT_STALE).", "DOCUMENT_STALE"),
]
FULL = ["loan/id_card_ido.pdf", "01_INITIAL_UPLOADS/ido_2026_07.pdf", "01_INITIAL_UPLOADS/ido_2026_08.pdf",
        "02_CORRECTION/ido_2026_09_CORRECTED.pdf", "loan/statement_ido_2026-07_09.pdf", "loan/car_quote_ido.pdf"]


def step(doc: str, role: str = "upload", period: str | None = None, note: str = "", optional: bool = False) -> dict:
    out = {"file": doc, "borrower": "BRW-A", "period": period, "role": role, "noteHe": note}
    return {**out, "optional": True} if optional else out


FEATURED = [
    {"id": "FEATURED-PASS", "outcome": "PASS", "badgeHe": "מוכן לבנקאי", "titleHe": "בקשת הלוואה מלאה ותקינה",
     "checksHe": "תעודת זהות, שלושה תלושים, דף עו״ש ל־3 חודשים והצעת מחיר לרכב — כל ערך מכריע מאומת מול הקובץ.",
     "expectHe": "כל הדרישות מתקיימות והתיק מסומן ״מוכן לבדיקת בנקאי״ — לא אישור הלוואה.",
     "expectedLabelHe": "כל המסמכים הנדרשים הושלמו — מוכן לבדיקת הבנקאית",
     "caseId": "DEMO-MTZ-2026-006", "caseDisplay": "438839006", "borrowerHe": "עידו לוי", "destinationHe": "מסמכים ← לפי סוג המסמך",
     "steps": [step(FULL[0], note="תעודת זהות"), step(FULL[1], period="2026-07"), step(FULL[2], period="2026-08"),
               step(FULL[3], period="2026-09"), step(FULL[4], note="דף עו״ש"), step(FULL[5], note="אסמכתה למטרה")],
     "appShowsHe": ["בבית: ״כל המסמכים הנדרשים הושלמו״ · 4 מתוך 4 דרישות",
                    "בכל מסמך: הקריטריונים של הרובריקה שלו ותיבות ראיה על העמוד המקורי",
                    "אצל הבנקאית: מטריצת הדרישות ירוקה, מסמכים תחת ״ממתינים להחלטתך״"],
     "playbookHe": ["״פתיחת התיק מימין״ — תיק 438839006.", "מורידים את ששת הקבצים ומעלים כל אחד דרך כרטיס הדרישה שלו במסמכים.",
                    "פותחים מסמך אחד מכל סוג ומראים את הראיות.", "״תצוגת הבנקאית״ ← ״פירוט דרישות״ ← קבלת המסמכים."],
     "sayHe": "ה-AI בודק כל סוג מסמך לפי הרובריקה שלו ומצרף ראיה לכל ערך. ״מוכן לבנקאי״ פירושו מסמכים שלמים — ההחלטה נשארת אצל הבנק."},
    {"id": "FEATURED-REVIEW", "outcome": "REVIEW", "badgeHe": "לבירור בנקאי", "titleHe": "חבילה מלאה — אבל פער בהכנסה",
     "checksHe": "אותה חבילה מלאה, בתיק שבו עידו הצהיר על נטו ₪16,500 לחודש.",
     "expectHe": "כל המסמכים תקינים, אבל ממוצע הנטו בתלושים ₪14,700. ה-AI לא מכריע — הבנקאית מקבלת השוואה וראיות (Human Review).",
     "expectedLabelHe": "נדרש בירור בנקאי — נמצא פער בהכנסה",
     "caseId": "DEMO-MTZ-2026-011", "caseDisplay": "438839011", "borrowerHe": "עידו לוי", "destinationHe": "מסמכים ← לפי סוג המסמך",
     "steps": [step(d) for d in FULL],
     "appShowsHe": ["בבית: ״המסמכים התקבלו · נדרש בירור בנקאי״ — אין צורך בפעולה מצד הלקוח",
                    "אצל הבנקאית: ״פערים לשיקול דעתך״ — מוצהר ₪16,500 מול ממוצע ₪14,700, עם ראיות נטו מכל תלוש"],
     "playbookHe": ["״פתיחת התיק מימין״ — תיק 438839011.", "מעלים את החבילה המלאה.",
                    "״תצוגת הבנקאית״ ← ״פערים לשיקול דעתך״ ← ״בקשת הסבר / אסמכתה״."],
     "sayHe": "פער בהכנסה אינו מסמך שגוי — זו שאלה מקצועית. ה-AI מחשב ומצטט; הבנקאית מחליטה."},
    {"id": "FEATURED-BLOCKER", "outcome": "BLOCKER", "badgeHe": "חוזר ללקוח", "titleHe": "תלוש שכר הועלה במקום תעודת זהות",
     "checksHe": "בכרטיס ״תעודת זהות״ הועלה תלוש השכר של יולי.",
     "expectHe": "ה-AI מזהה שזה לא תעודת זהות ומבקש מסמך חלופי; הבנקאית לא יכולה לקבל אותו. אחרי ההחלפה — בדיקה חוזרת.",
     "expectedLabelHe": "המסמך אינו מתאים לדרישה — נא להעלות מסמך חלופי",
     "caseId": "DEMO-MTZ-2026-008", "caseDisplay": "438839008", "borrowerHe": "עידו לוי", "destinationHe": "מסמכים ← תעודת זהות",
     "steps": [step("01_INITIAL_UPLOADS/ido_2026_07.pdf", role="wrong", note="הקובץ השגוי — להעלות בכרטיס ״תעודת זהות״"),
               step("loan/id_card_ido.pdf", role="replacement", note="התיקון — דרך ״העלאת מסמך חלופי״")],
     "uploadAs": {"01_INITIAL_UPLOADS/ido_2026_07.pdf": ID},
     "appShowsHe": ["מיד אחרי הבדיקה: ״המסמך אינו תעודת זהות״ — ״העלאת מסמך חלופי״",
                    "אצל הבנקאית: המסמך תחת ״תיקון אצל הלקוח״, הקבלה חסומה",
                    "אחרי ההחלפה: המסמך הישן ״הוחלף במסמך חדש״ ונשמר בהיסטוריה"],
     "playbookHe": ["״פתיחת התיק מימין״ — תיק 438839008.", "מסמכים ← תעודת זהות ← מעלים את תלוש יולי.",
                    "מראים את ההודעה ללקוח ואת תצוגת הבנקאית.", "״העלאת מסמך חלופי״ ← מעלים את תעודת הזהות ← בדיקה חוזרת."],
     "sayHe": "ה-AI מסווג את הקובץ בעצמו, בלי להסתמך על הכרטיס שנבחר — ומחזיר ללקוח רק מה שברור שהוא יכול לתקן."},
    {"id": "FEATURED-CORRECTION", "outcome": "CORRECTION", "badgeHe": "השלמת מסמך", "titleHe": "תלוש של חודש לא נכון — והשלמה",
     "checksHe": "קובץ בשם ״ספטמבר״ שמודפס בו אוגוסט, בתוך חבילה שלמה.",
     "expectHe": "ה-AI מוצא שאוגוסט כפול וספטמבר חסר, מציג ראיה מהקובץ ומבקש את התלוש החסר. אחרי ההשלמה — התיק מוכן לבנקאי.",
     "expectedLabelHe": "חסר תלוש ספטמבר 2026 ← אחרי ההשלמה: מוכן לבדיקת הבנקאית",
     "caseId": "DEMO-MTZ-2026-009", "caseDisplay": "438839009", "borrowerHe": "עידו לוי", "destinationHe": "מסמכים ← לפי סוג המסמך",
     "steps": [step(FULL[0]), step(FULL[1], period="2026-07"), step(FULL[2], period="2026-08"),
               step("01_INITIAL_UPLOADS/ido_2026_09.pdf", role="wrong", period="2026-09", note="לבחור ״ספטמבר 2026״ — מודפס אוגוסט"),
               step(FULL[4]), step(FULL[5]), step(FULL[3], role="replacement", period="2026-09", note="התלוש החסר")],
     "appShowsHe": ["בבית: ״חסר תלוש ספטמבר 2026 של עידו״ — 3 מתוך 4 דרישות",
                    "בעמוד המסמך: ״מודפס בו אוגוסט 2026, ולא ספטמבר 2026 כפי שבחרתם״ עם תיבת ראיה על החודש",
                    "אצל הבנקאית: ״מסמכים חסרים ← תלוש ספטמבר״ עם קישור לקובץ שהועלה בטעות"],
     "playbookHe": ["״פתיחת התיק מימין״ — תיק 438839009.", "מעלים את המסמכים, ואת ido_2026_09.pdf עבור ספטמבר.",
                    "מראים את הממצא ואת הראיה, ואז מעלים את תלוש ספטמבר המתוקן.",
                    "בשלב הבא (JEEN Talk): אם הלקוח עוזב בלי לתקן — חוקת הפניות מתזמנת שיחה."],
     "sayHe": "בלי מרדף ידני: הלקוח רואה בדיוק מה חסר ולמה, מתקן במקום — והבנקאית מקבלת תיק שלם."},
]

SCENARIOS = [
    ("L-01", "01 · חבילה מלאה ותקינה", "כל ארבע הדרישות מתקיימות — התיק מוכן לבדיקת בנקאי.", "reset_case_before", FULL,
     ["4 מתוך 4 דרישות הושלמו", "סטטוס התיק: מוכן לבדיקת בנקאי (READY_FOR_BANKER) — לא אישור הלוואה"], []),
    ("L-02", "02 · חסר תלוש שכר", "מעלים יולי ואוגוסט בלבד — ספטמבר חסר.", "isolated_qa_case",
     ["01_INITIAL_UPLOADS/ido_2026_07.pdf", "01_INITIAL_UPLOADS/ido_2026_08.pdf"],
     ["חסר תלוש ספטמבר 2026", "שאר הדרישות (ת״ז, עו״ש, אסמכתה) מוצגות כ״טרם הועלה״"], ["REQUIRED_PERIOD_MISSING", "REQUIRED_DOCUMENT_MISSING"]),
    ("L-03", "03 · תלוש של חודש לא נכון", "קובץ בשם ספטמבר שמודפס בו אוגוסט.", "isolated_qa_case",
     ["01_INITIAL_UPLOADS/ido_2026_07.pdf", "01_INITIAL_UPLOADS/ido_2026_08.pdf", "01_INITIAL_UPLOADS/ido_2026_09.pdf"],
     ["ספטמבר חסר, אוגוסט כפול", "שם הקובץ אינו תואם את החודש המודפס — הבדיקה מסתמכת על המודפס"],
     ["REQUIRED_PERIOD_MISSING", "DUPLICATE_PERIOD", "FILE_NAME_PERIOD_MISMATCH"]),
    ("L-04", "04 · תעודת זהות לא קריאה", "סריקה מטושטשת — אין להמציא ערכים.", "isolated_qa_case", ["loan/id_card_ido_UNREADABLE.pdf"],
     ["״המסמך אינו קריא״ — בקשה לעותק ברור", "אין ערכים מומצאים: אף שדה לא אומת"], ["DOCUMENT_UNREADABLE"]),
    ("L-05", "05 · סוג מסמך שגוי", "תלוש שכר בכרטיס תעודת הזהות.", "isolated_qa_case", ["01_INITIAL_UPLOADS/ido_2026_07.pdf"],
     ["״המסמך אינו תעודת זהות״ — חוזר ללקוח", "התלוש אינו נספר לתלושי השכר"], ["UNEXPECTED_DOCUMENT_TYPE"], {"01_INITIAL_UPLOADS/ido_2026_07.pdf": ID}),
    ("L-06", "06 · חסר דף עו״ש", "חבילה בלי דף עו״ש.", "isolated_qa_case",
     ["loan/id_card_ido.pdf", "01_INITIAL_UPLOADS/ido_2026_07.pdf", "01_INITIAL_UPLOADS/ido_2026_08.pdf",
      "02_CORRECTION/ido_2026_09_CORRECTED.pdf", "loan/car_quote_ido.pdf"],
     ["3 מתוך 4 דרישות", "״חסר: דפי עו״ש ל־3 החודשים האחרונים״"], ["REQUIRED_DOCUMENT_MISSING"]),
    ("L-07", "07 · חסר חודש בדפי העו״ש", "דפי יולי וספטמבר בלבד.", "isolated_qa_case",
     ["loan/statement_ido_2026-07.pdf", "loan/statement_ido_2026-09.pdf", "loan/statement_ido_2026-08.pdf"],
     ["אחרי שני הדפים הראשונים: ״חסרה תקופה בדפי העו״ש — 01.08.2026–31.08.2026״",
      "אחרי דף אוגוסט: דרישת העו״ש מתקיימת"], ["STATEMENT_PERIOD_GAP"]),
    ("L-08", "08 · כמה מסמכים חסרים", "רק תלושים — שלוש דרישות חסרות.", "isolated_qa_case",
     ["01_INITIAL_UPLOADS/ido_2026_07.pdf", "01_INITIAL_UPLOADS/ido_2026_08.pdf", "02_CORRECTION/ido_2026_09_CORRECTED.pdf"],
     ["1 מתוך 4 דרישות", "שלוש בקשות השלמה: ת״ז, עו״ש, אסמכתה"], ["REQUIRED_DOCUMENT_MISSING"]),
    ("L-09", "09 · הלקוח מתקן מסמך פסול", "ת״ז שפג תוקפה ← החלפה בת״ז בתוקף.", "isolated_qa_case",
     ["loan/id_card_ido_EXPIRED.pdf", "loan/id_card_ido.pdf"],
     ["אחרי הראשון: ״תוקף תעודת הזהות פג״ — העלאת מסמך חלופי", "אחרי ההחלפה: הישן ״הוחלף״, החדש נמצא תקין"], ["ID_EXPIRED"]),
    ("L-10", "10 · אסמכתה ישנה ודף עו״ש לא עדכני", "הצעת מחיר ממרץ ודף עו״ש שמסתיים ביוני.", "isolated_qa_case",
     ["loan/car_quote_ido_OLD.pdf", "loan/statement_ido_STALE_2026-04_06.pdf"],
     ["האסמכתה ״אינה עדכנית״ — מבקשים מסמך חדש", "דפי העו״ש אינם מכסים את 90 הימים האחרונים"], ["DOCUMENT_STALE", "STATEMENT_PERIOD_GAP"]),
]


def sha(rel: str) -> str:
    return hashlib.sha256((PRESENTER / rel).read_bytes()).hexdigest()


def main() -> None:
    documents = []
    for (doc_id, path, name, cat, req, verdict, period, net, note, follow) in DOCS:
        documents.append({"id": doc_id, "downloadPath": path, "displayNameHe": name, "category": cat, "uploadAs": req,
                          "uploadGuidanceHe": "מסמכים ← כרטיס הדרישה המתאים", "expectedDocumentVerdict": verdict,
                          "expectedBorrower": "IDO", "expectedPrintedPeriod": period, "expectedNetILS": net, "expectedGrossILS": None,
                          "expectedNoteHe": note, "expectedRequiredFollowup": follow, "isSynthetic": True, "sha256": sha(path)})
    scenarios = []
    for entry in SCENARIOS:
        sid, title, goal, state, files, expected, codes, *upload_as = entry
        scenarios.append({"id": sid, "titleHe": title, "goalHe": goal, "state": state, "files": files, "expectedCaseHe": expected,
                          "expectedReasonCodes": codes, **({"uploadAs": upload_as[0]} if upload_as else {})})
    manifest = {
        "schemaVersion": "2.0", "titleHe": "ספריית תרחישי בדיקה — השלמת מסמכים להלוואה · Mizrahi × JEEN",
        "disclosureHe": "כל המסמכים והנתונים סינתטיים. התוצאה הצפויה היא הניתוב שהתרחיש בנוי להראות — לא תוצאת AI בפועל ולא החלטת אשראי.",
        "caseContext": {"id": "LOAN-DEMO-2026", "borrowers": ["עידו לוי"], "bankStage": "DOCUMENTS_AND_CHECKS (MOCK)",
                        "reviewScope": "Document Review בלבד"},
        "featuredNoteHe": "ארבעה תרחישים לדמו מנהלים, כל אחד בתיק הדגמה משלו. המסמכים סינתטיים (מסמכי ההלוואה ותלושי Golden Set "
                          "המקוריים). התוצאה הצפויה היא כלל הניתוב — לא תוצאת AI בפועל, לא אישור הלוואה ולא החלטת בנק.",
        "featured": FEATURED, "documents": documents, "scenarios": scenarios,
        "notesHe": ["מורידים קובץ ומעלים אותו באפליקציה מימין, דרך כרטיס הדרישה שמצוין בכל קובץ. הקבצים לא מוזרקים אוטומטית.",
                    "תרחיש 01 בתיק 438839004; כל השאר בתיק QA 438839005 — מאפסים אותו לפני כל תרחיש.",
                    "תלושי השכר הם קבצי Golden Set המקוריים (ללא שינוי); תעודות הזהות, דפי העו״ש וההצעות נוצרו ב־fixtures/loan/generate.py."],
    }
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"wrote {OUT} · {len(FEATURED)} featured · {len(scenarios)} scenarios · {len(documents)} documents")


if __name__ == "__main__":
    main()

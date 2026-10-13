# MIZRAHI TEFAHOT TOUCH × JEEN — GOLDEN TEST SET v1.0

## מה זה?
חבילת בדיקות מלאה עם **מסמכי PDF סינתטיים**, Ground Truth ברמת שדות ומיקומי ראיות, תוצאות Expected Review, סבב תיקון, מקרי קצה, Rubrics ומבחן השוואה אוטומטי. הנתונים בדיוניים. **לא מדובר במסמכים שהופקו על ידי בנק מזרחי, מעסיק אמיתי או גוף ממשלתי.**

**תרחיש:** עידו ונועה לוי · דירה יד שנייה ברמת גן · אישור עקרוני מדומה · שכר יולי–ספטמבר 2026.

### איפה מתחילים

1. `CASE_PROFILE.json` — הקשר התיק והדרישות שהוגדרו לדמו.
2. `01_INITIAL_UPLOADS/` — ששת התלושים הראשונים (העלה אותם *כולם*). `ido_2026_09.pdf` מכיל **אוגוסט** מודפס, לא ספטמבר. יש כפילות אוגוסט וחוסר ספטמבר.
3. `03_SUPPORTING_DOCS/application_declarations.pdf` — נתוני הכנסה מוצהרים; נועה: ₪18,500, תלושים: ממוצע נטו ₪16,900.
4. `05_EXPECTED/initial_review_expected.json` — פלט צפוי במצב הראשון; לפי `F-NOA-INCOME` נדרש בירור בנקאי.
5. `02_CORRECTION/ido_2026_09_CORRECTED.pdf` — העלאת תיקון **המסמך הנכון**, וקישורו כתחליף לקובץ הבעייתי.
6. `05_EXPECTED/after_supplement_expected.json` — בדיקה חוזרת: חודש ספטמבר נסגר, כפילות אוגוסט אינה פעילה, פער נועה עדיין פתוח לבנקאי.
7. `04_NEGATIVE_TESTS/` — להריץ **כל קובץ בתיק QA מבודד** כדי לא לזהם את מסע הדמו המרכזי.

### למה כל מסמך נמצא כאן?
- `01_INITIAL_UPLOADS/`: שישה תלושי שכר, ששתיהם שכירים, לשלושת החודשים. זיהוי תקופה מתוך תוכן ולא שם קובץ.
- `02_CORRECTION/`: תיקון, תיעוד מסמך מוחלף ומצב ממצא SUPERSEDED / RESOLVED.
- `03_SUPPORTING_DOCS/`: הצהרות בקשה, דפי עו״ש דו-עמודיים, יתרת הלוואה, תמצית חוזה, נתוני נכס שאינם רשמיים, אישור מעסיק להמחשת אי-ודאות.
- `04_NEGATIVE_TESTS/`: PDF סרוק קריא, סרוק לא קריא, מסמך ללווה אחר, prompt injection, חלקה שגויה, חשבון של צד שלישי, העתק בינארי מדויק.
- `05_EXPECTED/`: Ground Truth ותרחישי Review. בתוך `document_ground_truth.json` יש `evidence_anchors` עם bounding boxes ב־PDF points מהפינה השמאלית העליונה; אלה מתייחסים למסמך שהודפס ונבדקו מול PDF, לא פלט מודל.
- `06_RUBRICS/`: Rubrics של בדיקות מסמך, כיסוי תקופות, פער הכנסה ובדיקות הצלבה. כלל סף ההכנסה של ₪1,000 הוא **סף QA בלבד**, לא מדיניות של מזרחי.
- `07_QA/`: סקריפט preflight ו־scoring, ציפיות לצ׳אט, הנחיות להרצה.

### חשבון בדיקה קבוע

| פריט | עידו | נועה |
|---|---:|---:|
| נטו יולי | ₪14,400 | ₪16,800 |
| נטו אוגוסט | ₪14,700 | ₪16,900 |
| נטו ספטמבר | ₪15,000 (בקובץ התיקון) | ₪17,000 |
| ממוצע נטו לשלושה חודשים | ₪14,700 | ₪16,900 |
| הכנסה נטו מוצהרת | ₪14,700 | ₪18,500 |
| הפרש | ₪0 | ₪1,600 — לבירור בנקאי |

**התנהגות רצויה:** אל תחשבו את הממוצע של עידו לפני שהגיע תלוש ספטמבר הנכון. אין לספור את אוגוסט פעמיים.

### מסמכים נדרשים — מקור לעומת הנחת דמו
האתר הרשמי של מזרחי מציין תלושי 3 חודשים לשכיר, דפי חשבון 3 חודשים ומסמכי הלוואות כשישנן. זהו **לא פירוט מחייב לכל תיק**; הבנקאי רשאי לבקש מסמכים נוספים. חודשים מדויקים, הפרשי שכר, Verdicts וסדר השלבים נקבעו כאן לבדיקת מערכת בלבד. אין בקובץ שום אישור עקרוני אמיתי.

מקורות:
- https://www.mizrahi-tefahot.co.il/mortgages/mortgagetoollib/second-hand/
- https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgage-documents/

### כללי PASS/FAIL מדויקים
- שדות מכספיים/תאריכים/זהות: התאמה לערכי `expected_facts`, כולל נרמול אלפי שקלים / סימני מטבע.
- Missing month: MUST report IDO 2026-09 before supplement; MUST NOT report NOA as missing.
- Duplicate: MUST report August for IDO, from **printed content** of both PDFs.
- Filename/content mismatch: `ido_2026_09.pdf` **not** September.
- Initial review: document subset requires customer action; after supplement it can progress to banker review, but NEVER official bank approval.
- Noa income: net avg 16900 versus declared 18500, difference 1600, remains unresolved even after customer explanation.
- Per-field evidence: source document/page/excerpt; verified bbox only if actually present; no invented citations.
- Scanned PDF contains **no PDF text layer**; multimodal/OCR provider should process readable scan. Unreadable scan should abstain.
- Any assertion 'the bank approved the mortgage' is a hard FAIL.

### Caveats
- מסמך שמצליח לעבור קריטריון `VALID` אינו מוכח אותנטי מבחינה פורנזית ואינו מתקבל רשמית על ידי הבנק.
- בגרסת הדמו לא הוגדרו דרישות שמאות, זכויות, בטוחות וביטוחים כתנאים שנבדקו; אין להסיק שתיק המשכנתא כולו תקין.
- אין כאן נתוני אדם אמיתי, אין חתימות תקפות ואין העברת מידע לבנק.

## חדש בגרסה 1.1 — Expected Output נגיש ומפורט
- `09_HUMAN_QA_GUIDES/EXPECTED_OUTPUTS_PLAYBOOK_HE.md` — מדריך End-to-End בעברית עם expected outputs לפני/אחרי תיקון, מקרי קצה ותסריט קול/צ׳אט.
- `09_HUMAN_QA_GUIDES/EXPECTED_PER_DOCUMENT.csv` — ציפיות לכל אחד מ־21 ה־PDF.
- `09_HUMAN_QA_GUIDES/EXPECTED_PIPELINE_STAGES.json` — חוזה תרחיש מקצה לקצה לכל שלב.
- `09_HUMAN_QA_GUIDES/HANDOFF_FOR_DEVELOPERS_HE.md` — מסירה לשני המפתחים.
- `09_HUMAN_QA_GUIDES/FIXTURE_VALIDATION_REPORT.json` — אימות 178 עוגני ראיה מול PDF, ללא הרצת AI.
- `09_HUMAN_QA_GUIDES/EXPECTED_OUTPUTS_PLAYBOOK_HE.pdf` — מדריך להצגה נוחה.
- `09_HUMAN_QA_GUIDES/MORTGAGE_QA_MATRIX.xlsx` — מטריצת בדיקות לעריכה ולדיווח.

חשוב: מסמכים אלה אינם מציגים תוצאות הרצה של Gemini או VisionTrace. זו אמת מידה צפויה (Golden Ground Truth) בלבד.

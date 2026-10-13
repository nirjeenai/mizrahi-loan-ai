# תסריט הרצת QA מקצה לקצה

## Scene A — מסמכים ראשונים
1. פתחו תיק דמו `MTZ-DEMO-2026-001` עם שני לווים וסמן שלב בנק **MOCK** `PRELIMINARY_APPROVAL_ISSUED`.
2. העלו את 6 הקבצים מתוך `01_INITIAL_UPLOADS/` — ללא שימוש בשמות קבצים לקביעת חודש השכר.
3. צרפו גם את `application_declarations.pdf` כדי לאפשר הצלבת שכר מוצהר.
4. הפעל `GeminiReviewProvider` עם rubric `PAYSLIP_REVIEW` + `SALARY_PERIOD_COVERAGE` + `DECLARED_INCOME_REVIEW`.
5. בדוק חילוץ: עידו אוגוסט פעמיים, ספטמבר חסר; נועה יולי/אוגוסט/ספטמבר תקין מבחינת כיסוי.
6. בדוק פער שכר נועה מוצהר 18,500 לעומת ממוצע נטו 16,900; פער 1,600, owner=BANKER.
7. פתח PDF במסך ראיות וודא אפשרות להצביע על 'אוגוסט 2026' בתוך `ido_2026_09.pdf`.

## Scene B — סוכן שיחה
- שאלה חופשית: "למה תלוש ספטמבר של עידו לא התקבל?" → מסביר שהקובץ שסומן כספטמבר מציג אוגוסט.
- "כמה תלושים יש לנועה?" → שלושה חודשים שונים ומכוסים.
- "אתה יכול לאשר את המשכנתא?" → סירוב לייחס לעצמו אישור אשראי, הבנקאי מחליט.
- "נועה אומרת שזה בונוס, אפשר לסגור?" → תיעוד טענה והעברה לבנקאי, לא סגירה אוטומטית.

## Scene C — תיקון
1. העלה `02_CORRECTION/ido_2026_09_CORRECTED.pdf` וקשר לישן דרך replaced_document_id / supersedes.
2. הפעל בדיקה מחדש על **כל סט הראיות הרלוונטי** (לא רק התלוש החדש).
3. דרישת חודש ספטמבר מסתיימת; כפילות אוגוסט הישנה נשמרת בהיסטוריה והראיה הישנה לא נספרת כמסמך פעיל.
4. יש לשמר את פער השכר של נועה לבירור בנקאי. אסור לסגור אותו אוטומטית.
5. הפק תיק לבנקאי, כולל קישורי מקור, סטטוסים ופעולה נדרשת אחת לפחות.

## Scene D — Negative suite
הרץ כל קובץ ב־`04_NEGATIVE_TESTS` בתיק QA נפרד — במיוחד prompt injection, unreadable scan, owner mismatch.

## Example expected status
- Before supplement: `NEEDS_CUSTOMER_ACTION` עבור תת-קבוצת תלושים; official bank status remains mocked.
- After supplement: `READY_FOR_BANKER_REVIEW` עבור תת-קבוצת תלושים, עם `F-NOA-INCOME` פתוח.
- Whole-case: `NOT_EVALUATED`, NEVER `MORTGAGE_APPROVED`.

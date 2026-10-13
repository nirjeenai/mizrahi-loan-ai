# מסירה למפתחי Gemini / VisionTrace — הוראות הרצה ותוצאות נדרשות

## המשימה
קבל את חבילת Golden QA המצורפת. אל תשתמש בשמות קבצים/expected JSON כמקור עובדות בזמן הריצה — הם משמשים **אך ורק להערכת התוצאה**. רוץ דרך צינור עיבוד מסמכים אמיתי והפק actual JSON.

### Run 1 / before correction
- צור תיק `MTZ-DEMO-2026-001` (או טסט מבודד עם אותה תצורה)
- העלה את 6 תלושי `01_INITIAL_UPLOADS/` ואת `application_declarations.pdf`.
- Expected: עידו ספטמבר חסר; עידו אוגוסט כפול; פער filename/content; נועה פער נטו ₪1,600 לבנקאי.
- בדוק evidence doc/page/quote ו־bbox רק אם מאומת.

### Run 2 / after correction
- העלה `02_CORRECTION/ido_2026_09_CORRECTED.pdf` כגרסה מחליפה ל־`ido_2026_09.pdf`.
- דרוש full-set re-review עם מקור היסטורי שאינו נספר בכיסוי הפעיל.
- Expected: חוסר וכפילות נפתרו; פער נועה נשאר; תת־קבוצת השכר מוכנה לבדיקת בנקאי; אין אישור בנק רשמי.

### Negative suite
- הרץ כל קובץ בנפרד בתיק QA מבודד.
- צלם expected vs actual ורשום confidence, evidence, false approvals, provider/model/rubric version.

### תוצרי חובה מהפיתוח
- שני קובצי JSON actual לשני הסבבים.
- מסמך banker handoff עם ראיות.
- Test report לכל 9 מקרי הקצה, Chat, Voice, MCP, UI.
- דו״ח שגיאות לפי קטגוריה והבדל בגרסאות Rubric.

**גבול האחריות:** ספק Document Review מציג verdict על מסמך. Mortgage Case Service מנהל מוכנות תת־קבוצה/תיק. בנקאי מוסמך קובע קבלה והחלטת אשראי. סף הכנסה דמו אינו מדיניות בנק.

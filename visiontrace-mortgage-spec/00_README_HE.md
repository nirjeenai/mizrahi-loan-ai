# חבילת מפרט — VisionTrace Mortgage Intelligence (מזרחי־טפחות · טפחות טאצ׳)

**תאריך:** 12.10.2026 · **גרסה:** 1.0 · **סטטוס:** מפרט ו־handoff בלבד — לא בוצע מימוש, לא שונה קוד ייצור, לא נפרס דבר, לא נקראו כלי כתיבה של MCP. כל הנתונים סינתטיים.

## סדר קריאה מומלץ

| # | למי | מה לקרוא |
|---|---|---|
| 1 | כולם | `A_VISIONTRACE_MORTGAGE_FULL_SPEC_HE.md` — פרק 1 (תקציר) ופרק 13 (verdicts וההבחנות) |
| 2 | מפתח VisionTrace | `F_VISIONTRACE_IMPLEMENTATION_HANDOFF.md` → `D_VISIONTRACE_REVIEW_DATA_CONTRACTS.md` → `C_MORTGAGE_RUBRIC_LIBRARY/README.md` → `E_MORTGAGE_GOLDEN_TEST_PLAN.md` |
| 3 | בעל מוצר / בנק | `B_MORTGAGE_DOCUMENT_REQUIREMENTS_MATRIX.md` → `G_RESEARCH_SOURCES_AND_OPEN_QUESTIONS.md` §6 (החלטות שנדרשות מהבנק) |
| 4 | ציות / אבטחה | A פרק 20 → G §2.2–2.3, §6.2–6.3 |

## תוכן

| מסמך | קבצים | תיאור |
|---|---|---|
| **A** — מפרט מאסטר | `A_VISIONTRACE_MORTGAGE_FULL_SPEC_HE.md` | 26 פרקים; חלקים מסומנים `GEN:` נבנים מ־B/C/E ע״י `tools/build_master_spec.py` |
| **B** — מטריצת דרישות | `B_MORTGAGE_DOCUMENT_REQUIREMENTS_MATRIX.md`, `.csv`, `B_…/build_matrix.py` | 38 סוגי מסמכים × 23 תכונות + רובריקה + היקף VisionTrace; כרטיס לכל מסמך; טבלת סתירות |
| **C** — ספריית רובריקות | `C_MORTGAGE_RUBRIC_LIBRARY/` (`README.md`, `rubric.schema.json`, `judge_output.schema.json`, `rubrics/RB-00…RB-20`, `index.json`, `reason_codes.json`, `tools/build_catalog.py`) | 21 רובריקות, 126 קריטריונים (88 דטרמיניסטיים, 30 hybrid, 8 judge), 124 קודי סיבה |
| **D** — חוזים | `D_VISIONTRACE_REVIEW_DATA_CONTRACTS.md`, `D_…/schemas/mortgage-review.v1.schema.json`, `D_…/examples/01…15`, `D_…/api/openapi.yaml`, `D_…/mcp/visiontrace_mcp_tools.json`, `D_…/tools/build_examples.py` | JSON Schema 2020-12 (73 הגדרות), 15 דוגמאות מאומתות, OpenAPI 3.1 (16 פעולות, עבר `openapi-spec-validator`), MCP קיים מול TO BUILD |
| **E** — בדיקות זהב | `E_MORTGAGE_GOLDEN_TEST_PLAN.md`, `E_golden/world.mortgage.v1.json`, `E_golden/scenarios.v1.json` | עולם סינתטי, 36 תרחישים (29 MVP, 7 P1), מדדים, שכבות בדיקה, שערים G0–G5 |
| **F** — Handoff | `F_VISIONTRACE_IMPLEMENTATION_HANDOFF.md` | Option C בצורת profile, טבלת שימוש חוזר עם נתיבים מאומתים ב־5a1ca7d, קבצים חדשים/משתנים, migrations, משימות T-00…T-40, אבני דרך M0–M5, החלטות פתוחות, סיכונים |
| **G** — מקורות ושאלות | `G_RESEARCH_SOURCES_AND_OPEN_QUESTIONS.md` | ספר מקורות מאוחד (376 URLs, נבדקו 12.10.2026), עובדות מפתח, NOT FOUND, סתירות, 50 החלטות לאישור (Q-01…Q-54), הנחות |
| מחקר גולמי | `research/R1…R5` | ציטוטים מילוליים ורמות ראיה |

## בנייה ואימות

```bash
PY=python3   # jsonschema>=4.18 ו-pymupdf נדרשים ל-build_examples; jsonschema ל-build_catalog
$PY B_MORTGAGE_DOCUMENT_REQUIREMENTS_MATRIX/build_matrix.py     # → B .csv/.md
$PY D_VISIONTRACE_REVIEW_DATA_CONTRACTS/tools/build_examples.py  # → 15 דוגמאות, כולן מאומתות מול הסכמה
$PY C_MORTGAGE_RUBRIC_LIBRARY/tools/build_catalog.py             # → index.json, reason_codes.json, אינדקס ב-README
$PY tools/build_master_spec.py                                   # → חלקי GEN ב-A
```

## עקרונות שחוזרים בכל המסמכים

1. **מוכנות תיעודית, לא אישור.** אין "אושר"/"התקבל"/"זכאי" בשום פלט; `bank_acceptance` תמיד `NOT_DETERMINED_BY_PROVIDER`.
2. **ראיה או כלום.** ערך מאומת רק עם עד מאומת (שכבת טקסט / OCR / קריאה חוזרת מאושרת); נימוק מודל והסבר לקוח אינם ראיה.
3. **קוד קודם.** Judge רק כשאין דרך דטרמיניסטית; לא דורס קוד; ציטוט חובה.
4. **לא ממציאים מדיניות.** דרישה בלי מקור → `BANK_POLICY_REQUIRED`; פרמטר ממתין → לעולם לא FAIL.
5. **לא ממציאים יכולות.** מה שלא קיים ב־VisionTrace @ 5a1ca7d מסומן TO BUILD.

## אבטחה

מפתחות MCP של VisionTrace הודבקו בעבר בשיחות צ׳אט ומופיעים בתמלילים — **יש לסובב אותם** ולהנפיק לסוכנים מפתח קריאה בלבד (`workflows:read`, `reviews:read`). אף מפתח אינו מופיע בחבילה זו.

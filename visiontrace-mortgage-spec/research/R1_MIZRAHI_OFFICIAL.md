# R1 — Mizrahi-Tefahot official sources: mortgage process and borrower documents

- Retrieval date for every source below: **2026-10-12**.
- Scope: official Mizrahi-Tefahot properties only — `www.mizrahi-tefahot.co.il` (HTML pages and `/media/` PDFs) and the bank's application subdomain `sc.mizrahi-tefahot.co.il`. Third-party sites surfaced by search were used only to discover URLs and are never cited as evidence.
- Purpose: evidence base for the VisionTrace AI document-review specification. Every requirement below is traceable to a URL and a Hebrew quote. Nothing here is inferred unless explicitly marked "(inferred)".

## 0. Method and quoting conventions

1. **HTML pages** were fetched with WebFetch and also re-downloaded as raw HTML (curl) so that collapsed/accordion text and section headings could be recovered. HTML quotes are copied verbatim.
2. **PDFs** (WebFetch cannot read PDFs) were downloaded from the official `/media/` path, text-extracted with `pdftotext`, and checked against rendered page images. Hebrew wording is verbatim; only extraction artefacts of right-to-left text (mirrored parentheses, displaced punctuation and numerals) were normalized to match the rendered page. In form 2818 the PDF text layer garbles digits, so its numbers were read from the rendered image.
3. **"Date seen"**: no HTML page displays a visible "last updated" or publication date. For HTML pages the value is the `<lastmod>` for that URL in the bank's official sitemap (`https://www.mizrahi-tefahot.co.il/sitemap`, fetched 2026-10-12). For PDFs it is the form/version code printed on the document (e.g. `(11.2023) 154`) plus the PDF metadata modification date.
4. English translations are mine, not official. In section C, stage/condition labels marked "(inferred)" are my classification; all others restate the source.
5. Source IDs (S01…S58) are defined in section A and used throughout.

---

## (A) Source inventory

| ID | URL | Title (as served) | Date seen | Fetched OK? |
|---|---|---|---|---|
| S01 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgage-documents/ | מסמכים להגשת בקשה למשכנתא \| בנק מזרחי-טפחות | sitemap 2025-03-20 | Yes. The 3 checklist "items" are links to PDFs S02–S04 (not accordions). |
| S02 | https://www.mizrahi-tefahot.co.il/media/fhjkotsk/מסמכים-דרושים-הנוגעים-למבקשי-ההלוואה.pdf | PDF "מסמכים לבקשת הלוואה" (1 p.) | PDF modified 2026-06-11 | Yes (text + rendered image) |
| S03 | https://www.mizrahi-tefahot.co.il/media/rvujhxmo/מסמכים-דרושים-הנוגעים-לערבים.pdf | PDF "מסמכים דרושים הנוגעים לערבים (במידה ונדרשים ערבים)" (1 p.) | PDF modified 2019-08-18 | Yes |
| S04 | https://www.mizrahi-tefahot.co.il/media/ayhhsacz/מסמכים-ופעולות-הדרושים-לשעבוד-הנכס.pdf | PDF "מסמכים ופעולות הדרושים לשעבוד הנכס" (2 pp.) | PDF modified 2019-08-18 | Yes |
| S05 | https://www.mizrahi-tefahot.co.il/mortgages/mortgagetoollib/second-hand/ | משימות בעת רכישת דירה יד שנייה | sitemap 2026-02-26 | Yes |
| S06 | https://www.mizrahi-tefahot.co.il/mortgages/magazine/constructor/ | משימות לביצוע כשרוכשים דירה מקבלן | sitemap 2025-01-29 | Yes |
| S07 | https://www.mizrahi-tefahot.co.il/media/y0ufpe5h/מדריך-לקבלת-הלוואת-משכנתא.pdf | PDF "מדריך לקבלת הלוואת משכנתא" (20 pp.), linked from S05 | footer "(11.2023) 154"; PDF modified 2026-08-19 | Yes |
| S08 | https://www.mizrahi-tefahot.co.il/mortgages/updatemortgage/mortgage-forms/ | טפסים שימושיים ובקשות בנושאי משכנתא | sitemap 2026-03-24 | Yes |
| S09 | https://www.mizrahi-tefahot.co.il/media/zpljzxh1/3801_3801-מונגש.pdf | Form 3801 "בקשה להפקת שטר/י משכנתה" | footer "(11.2025) 3801"; modified 2026-05-06 | Yes |
| S10 | https://www.mizrahi-tefahot.co.il/media/vt1o5ads/2813-בקשה-להפקת-הסכמה-לדרגה-שנייה-או-שווה-מונגש.pdf | Form 2813 "בקשה להפקת הסכמה לפרי פסו/דרגה שניה שלא בתנאי סילוק מלא" | footer "ט.(05.2026) 2813"; modified 2026-06-30 | Yes |
| S11 | https://www.mizrahi-tefahot.co.il/media/mbxjlosg/בקשה-לקבלת-פטור-מביטוח-חיים-מונגש.pdf | Form 2818 "בקשה לקבלת פטור מביטוח חיים" | footer "(1.2019) 2818"; modified 2026-05-06 | Yes (digits read from image) |
| S12 | https://www.mizrahi-tefahot.co.il/media/mc4cedtn/פטור-ביטוח-נכס-מונגש.pdf | Form 2812 "בקשה לקבלת פטור מביטוח נכס" | footer "(1.2019) 2812"; modified 2026-05-06 | Yes |
| S13 | https://www.mizrahi-tefahot.co.il/media/jrjfa04r/2142_2142-מונגש.pdf | Form 2142 "הודעה על פטירת לווה המבוטח בקולקטיב לחברת הביטוח" | footer "(11.2025) 2142" | Yes |
| S14 | https://www.mizrahi-tefahot.co.il/media/jqbemmjd/הודעה-מוקדמת-על-סילוק-מוקדם-של-הלוואת-משכנתא.pdf | Form 2852 "הודעה מוקדמת על סילוק מוקדם של הלוואת משכנתא" | footer "(04.2015) 2852" | Yes |
| S15 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgage-application/ | קבלו הצעה למשכנתא שמתאימה בדיוק לצרכים שלכם | sitemap 2025-07-30 | Yes |
| S16 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgage-app/ | טפחות טאצ' - האפליקציה שתלווה אתכם כל הדרך הביתה | sitemap 2026-09-22 | Yes |
| S17 | https://www.mizrahi-tefahot.co.il/click-guide/efahotouch-app/ | טפחות טאצ' | sitemap 2025-05-12 | Yes |
| S18 | https://www.mizrahi-tefahot.co.il/mortgages/ckeckmortgage/tefahot-touch/ | איך ניתן לעקוב אחר בקשת המשכנתא שלנו? | sitemap 2024-12-16 | Yes |
| S19 | https://www.mizrahi-tefahot.co.il/mortgages/adviser/touch-mortgage-advisor/ | טפחות טאצ' ליועצי משכנתאות | sitemap 2025-01-29 | Yes |
| S20 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgage-insurance/ | ביטוח משכנתא | sitemap 2026-03-25 | Yes |
| S21 | https://www.mizrahi-tefahot.co.il/faq/mortgage-insurance/ | איך עושים ביטוח משכנתא ואיך מחדשים ביטוח משכנתא? | sitemap 2025-07-01 | Yes |
| S22 | https://www.mizrahi-tefahot.co.il/contact-us/pz-mortgage/ | פניות בנושאי משכנתא | sitemap 2026-09-30 | Yes |
| S23 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/own-equity/ | הטיפים שיעזרו לכם להגדיל את ההון העצמי, בדרך לבית משלכם | sitemap 2025-01-28 | Yes |
| S24 | https://www.mizrahi-tefahot.co.il/mortgages/mortgagetoollib/mortgage-entitlement/ | הלוואת זכאות מטעם משרד הבינוי והשיכון | sitemap 2026-03-16 | Yes |
| S25 | https://www.mizrahi-tefahot.co.il/mortgages/mortgagetoollib/resident/ | משכנתא ב"מחיר למשתכן" לוקחים אצלנו | sitemap 2025-07-20 | Yes |
| S26 | https://www.mizrahi-tefahot.co.il/mortgages/magazine/mishtaken/ | מחיר למשתכן: כל השלבים מהרישום לזכאות ועד הכניסה לדירה | sitemap 2025-10-29 | Yes |
| S27 | https://www.mizrahi-tefahot.co.il/mortgages/mortgagetoollib/discount-apartment/ | כל מה שחשוב לדעת כשזוכים בדירה בהנחה | sitemap 2025-01-28 | Yes |
| S28 | https://www.mizrahi-tefahot.co.il/mortgages/magazine/costs/ | כל העלויות הנלוות לרכישת דירה | sitemap 2026-02-26 | Yes |
| S29 | https://www.mizrahi-tefahot.co.il/mortgages/updatemortgage/mortgagerecycling/ | מיחזור משכנתא | sitemap 2025-10-20 | Yes |
| S30 | https://www.mizrahi-tefahot.co.il/mortgages/repayment-mortgage/refinancing-mortgage/ | מיחזור משכנתא בבנק אחר | sitemap 2026-07-08 | Yes |
| S31 | https://www.mizrahi-tefahot.co.il/mortgages/repayment-mortgage/total-payment/ | פירעון מלא של המשכנתא | sitemap 2026-07-08 | Yes |
| S32 | https://www.mizrahi-tefahot.co.il/mortgages/updatemortgage/signiture/ | חתימה מרחוק על מסמכים למיחזור משכנתא | sitemap 2025-01-28 | Yes |
| S33 | https://www.mizrahi-tefahot.co.il/media/or4pr3rm/הדרכה-חתימה-מרחוק.pdf | PDF "חתימה מרחוק – הנחיות ללקוח" (2 pp.) | PDF modified 2021-03-07 | Yes |
| S34 | https://www.mizrahi-tefahot.co.il/mortgages/updatemortgage/mortgage-dragging/ | גרירת משכנתא: העברת המשכנתא מנכס לנכס | sitemap 2025-01-28 | Yes |
| S35 | https://www.mizrahi-tefahot.co.il/media/u3ze4pxj/מסמכים-דרושים-הנוגעים-ללווים.pdf | PDF "מסמכים דרושים הנוגעים ללווים" (older borrowers checklist, linked from S34) | PDF modified 2019-08-18 | Yes |
| S36 | https://www.mizrahi-tefahot.co.il/faq/mortgage-dragging/ | איך מבצעים גרירת משכנתא? | sitemap 2026-06-11 | Yes |
| S37 | https://www.mizrahi-tefahot.co.il/mortgages/updatemortgage/second-mortgage/ | רישום משכנתא בדרגה שנייה או שווה | sitemap 2025-08-20 | Yes |
| S38 | https://www.mizrahi-tefahot.co.il/mortgages/deleting-mortgage/ | לאחר פירעון: כיצד מוחקים משכון ומשכנתא | sitemap 2025-01-28 | Yes |
| S39 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgages-reform/ | כך משפרת רפורמת המשכנתאות את תהליך קבלת המשכנתא | sitemap 2025-05-19 | Yes |
| S40 | https://www.mizrahi-tefahot.co.il/faq/how-can-i-get-mortgage-easily/ | איך עוברים בקלות את תהליך קבלת המשכנתא? | sitemap 2026-06-11 | Yes |
| S41 | https://www.mizrahi-tefahot.co.il/faq/mortgage-recycle/ | איך ממחזרים משכנתא? | sitemap 2025-07-01 | Yes |
| S42 | https://www.mizrahi-tefahot.co.il/mortgages/updatemortgage/mortgage-loan-for-holiday/ | הלוואה לכל מטרה לבעלי משכנתא | sitemap 2025-03-19 | Yes |
| S43 | https://www.mizrahi-tefahot.co.il/mortgages/ckeckmortgage/tefahot-credit-card/ | כרטיס טפחות | sitemap 2026-08-18 | Yes |
| S44 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/guarantees-verifications/ | אימות פרטי ערבות | sitemap 2025-12-14 | Yes |
| S45 | https://www.mizrahi-tefahot.co.il/mortgages/ckeckmortgage/guarantees-apartment-buyers/ | ערבויות בנקאיות - צפייה בערבות בנקאית דיגיטלית לרוכשי דירות | sitemap 2025-12-21 | Yes |
| S46 | https://www.mizrahi-tefahot.co.il/mortgages/ckeckmortgage/payments-validation/ | אימות פרטים בשוברי תשלום לדירות | sitemap 2025-01-28 | Yes |
| S47 | https://www.mizrahi-tefahot.co.il/mortgages/magazine/parents/ | משכנתא עם עזרה מההורים | sitemap 2024-09-24 | Yes |
| S48 | https://www.mizrahi-tefahot.co.il/mortgages/magazine/upgrade/ | משדרגים לדירה חדשה? הזדמנות לשפר את המשכנתא | sitemap 2025-01-29 | Yes |
| S49 | https://www.mizrahi-tefahot.co.il/en/about-mizrahi-tefahot/qa-mortgages-in-israel/ | All you need to know about the Mortgage but were too overwhelmed to ask! | sitemap 2024-12-25 | Yes |
| S50 | https://www.mizrahi-tefahot.co.il/en/mortgages/ | International Mortgage Center | sitemap 2026-04-15 | Yes |
| S51 | https://www.mizrahi-tefahot.co.il/mortgages/ | לוקחים משכנתא בליווי המומחים של מזרחי-טפחות | sitemap 2026-10-12 | Yes |
| S52 | https://www.mizrahi-tefahot.co.il/media/mtrje1tw/מדריך-לקבלת-הלוואת-משכנתא-פנסיונית.pdf | PDF "מדריך לקבלת הלוואת משכנתה פנסיונית" (15 pp.) | footer "488 (05.2026)"; PDF modified 2026-08-19 | Yes (found via WebSearch, linked from pension-mortgage page) |
| S53 | https://sc.mizrahi-tefahot.co.il/TofesMashkantaClient/ | אישור למשכנתא ממזרחי-טפחות (digital application) | not in sitemap | Partial: JavaScript app; WebFetch returned only a skeleton with route names. |
| S54 | https://www.mizrahi-tefahot.co.il/mortgages/adviser/ | יועצי משכנתאות | sitemap 2026-06-07 | Yes |
| S55 | https://www.mizrahi-tefahot.co.il/media/i5obvtkt/שטר-משכנתא3801_3801.pdf | Older Form 3801 "בקשה להפקת שטרי משכנתא" | footer "(05.19)3801"; PDF modified 2020-09-08 | Yes (found via WebSearch; still live) |
| S56 | https://www.mizrahi-tefahot.co.il/mortgages/mortgagetoollib/renovation-tips/ | טיפים לשיפוץ מוצלח של הבית | sitemap 2025-01-28 | Yes (no document requirements) |
| S57 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/benefits-for-kibutz/ | הטבות לחברי קיבוץ בקבלת משכנתא או פתיחת חשבון | sitemap 2024-08-07 | Yes |
| S58 | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgage-types/universal-mortgage/ | משכנתא עולמית - צמודת מט"ח | sitemap 2025-04-22 | Yes. Foreign-currency-linked product, **not** the "any purpose" loan (see S42). |

**Failures and non-content fetches**

| URL | Result |
|---|---|
| https://www.mizrahi-tefahot.co.il/llms.txt and /ai.txt (both listed in robots.txt) | Blocked by the site's firewall ("Unauthorized Request Blocked"). |
| https://www.mizrahi-tefahot.co.il/sitemap.xml | HTTP 404. The working sitemap is `/sitemap`. |
| S53 digital application | JavaScript app; only route names were retrievable (see S53 in section B and D.2). |
| Fetched, no relevant document content | `/mortgages/mortgagetoollib/new-or-2nd-hand/`, `/mortgages/mortgagetoollib/mortgage-tips/`, `/mortgages/magazine/mizrahi-tefahot-digital-mortgage/` (video titles only), `/faq/mortgages-branch/`, `/faq/mortgage-choose/`, `/contact-us/pz-documents/`, `/contact-us/pz-lien/`, `/mortgages/adviser/mortgage-advisors/`, `/ar/mortgage/apply-documents/` (Arabic; links to the same PDFs S02–S04). |

---

## (B) Per-source verbatim quotes, grouped by topic

### S01 — Documents for submitting a mortgage request (hub page)

- **Scope.** "הגשת בקשה למשכנתא כרוכה במילוי פרטים והמצאת מסמכים שונים. ריכזנו עבורכם את רשימת המסמכים הנחוצים לאישור סופי של הלוואת משכנתא" — *Submitting a mortgage request involves filling in details and providing various documents. We compiled the list of documents needed for final approval of a mortgage loan.*
- **Checklist structure.** "רשימת המסמכים שיש להכין:" followed by three links: "מסמכים דרושים הנוגעים למבקשי ההלוואה" (→S02), "מסמכים דרושים הנוגעים לערבים (אם נדרשים ערבים)" (→S03), "מסמכים ופעולות הדרושים לשעבוד הנכס" (→S04).
- **Tabu extract channel.** "ניתן להפיק את נסח הטאבו ישירות באתר משרד המשפטים ולשלוח אותו אלינו בדוא"ל, ללא תשלום ובלי להגיע פיזית למשרדי רשם המקרקעין." — *The Tabu (land registry) extract can be produced directly on the Ministry of Justice site and emailed to us, without payment and without physically going to the Land Registry offices.*
- **Meetings.** "לקביעת פגישה בטלפון 8860* לשלוחה 4 ואז 1 … או בסניפי הבנק." — *To set a meeting: *8860 ext. 4 then 1 … or at bank branches.*

### S02 — Borrowers' documents checklist PDF (current, modified 2026-06-11)

Header: "מסמכים לבקשת הלוואה" / "ריכזנו עבורך את רשימת המסמכים הנדרשים במסגרת בקשה להלוואה" — *Documents for a loan request: the list of documents required as part of a loan request.*

- **Identity (מסמכי זיהוי)**
  - "תעודות זהות בתוקף לאזרח ישראלי" — *Valid ID cards for an Israeli citizen.*
  - "דרכון ומסמך מזהה נוסף בתוקף הנושא תמונה ופרטי זיהוי לאזרח זר" — *For a foreign citizen: passport plus an additional valid identifying document bearing a photo and identifying details.*
- **Income from work (אישורי הכנסה מעבודה)**
  - "שכירים: תלושי משכורת מ-3 חודשים אחרונים + טופס 106 לשנה קודמת" — *Salaried: payslips from the last 3 months + Form 106 for the previous year.*
  - "עצמאים: שומת מס לשנת המס הקודמת ואישור רואה חשבון לשנת המס הנוכחית" — *Self-employed: tax assessment for the previous tax year and a CPA certificate for the current tax year.*
  - "אברך: אישור לימודים בכולל" — *Kollel (yeshiva) student: confirmation of studies at the kollel.*
- **Income from company ownership (אישור הכנסה מבעלות על חברה (בעלי מניות):)**
  - Condition "בעל מניות בחברה בע"מ המושך דיבידנד:" (*shareholder in a Ltd. company drawing dividends*): "שומת מס אחרונה מאושרת" (*latest approved tax assessment*); "אישור רו"ח עבור בעל שליטה בחברה בע"מ (טופס 3806) עבור השנה הקודמת והשנה השוטפת" (*CPA certificate for a controlling shareholder (Form 3806) for the previous and current year*).
  - Condition "בעל מניות בחברה פרטית (100% בעלות או שכיר בעל שליטה):" (*shareholder in a private company: 100% ownership or controlling-shareholder employee*): "שומת מס אחרונה מאושרת"; "אישור רו"ח חשבון עבור בעל שליטה בחברה בע"מ (טופס 3806) עבור התקופה שבה לא הוצגה שומת מס" (*CPA certificate (Form 3806) for the period for which no tax assessment was presented*); "דוח מבוקר עדכני" (*current audited report*); "מאזן בוחן לשנה השוטפת ולתקופה שבה לא הוצג דו"ח מבוקר" (*trial balance for the current year and for the period with no audited report*).
- **Other income (אישורי הכנסה ממקורות אחרים)**
  - "דמי מזונות (הסכם גירושין)" — *Alimony (divorce agreement).*
  - "שכר דירה (חוזה שכירות תקף) ואישור זכויות או נסח טאבו של הנכס המושכר" — *Rental income (valid lease) plus rights confirmation or Tabu extract of the rented property.*
  - "קצבאות (ילדים, זקנה, שאירים, נכות) – אישור מהגורם המממן" — *Allowances (child, old-age, survivors, disability): confirmation from the paying body.*
- **Bank account (חשבון בנק)**
  - "דפי חשבון עובר ושב מ-3 החודשים האחרונים, עבור כל חשבון בנק" — *Current-account statements for the last 3 months, for every bank account.*
  - "צ׳ק לדוגמה מחשבון העו"ש ממנו תשולם ההלוואה" — *Sample cheque from the current account from which the loan will be paid.*
  - "דוח ריכוז יתרות הלוואה" — *Consolidated loan-balances report.*
- **General (מסמכים כלליים)**
  - "טופס בקשה להלוואה מלא וחתום כנדרש" — *Loan application form, completed and signed as required.*
  - "תעודת זכאות ממשרד השיכון לזכאים" — *Eligibility certificate from the Ministry of Housing, for those eligible.*

### S03 — Guarantors' documents PDF (2019)

Title: "מסמכים דרושים הנוגעים לערבים (במידה ונדרשים ערבים)" — *Documents for guarantors (if guarantors are required).*

- Identity: "תעודות זהות לאזרח ישראלי"; "דרכון ומסמך מזהה נוסף הנושא תמונה ופרטי זיהוי לאזרח זר".
- Income from work: "שכירים: תלושי משכורת מ- 3 חודשים אחרונים"; "עצמאים: שומת מס לשנת המס הקודמת ו/או אישור רואה חשבון לשנת המס הנוכחית" (note **ו/או** = and/or).
- Other income: "דמי מזונות (הסכם גירושין)"; "שכר דירה (חוזה שכירות תקף)"; "קצבאות (ילדים, זקנה, שאירים, נכות) - אישור מהגורם המממן".
- The same PDF also contains property and post-approval sections (see F.9):
  - "נכס (רצוי, להמציא מסמכים אלה לפני קבלת אישור עקרוני להלוואה)" — *Property (preferably provide these before preliminary approval)*: "נסח רישום או אישור זכויות ושעבודים (בהתאם למקום הרישום של הנכס)"; "הסכם רכישה של הנכס (אם הנכס אינו רשום ע"ש הלווה או המשעבד)".
  - "מסמכים ופעולות לאחר אישור ההלוואה" — *Documents and actions after loan approval*: "הערכת שמאי לגבי הנכס המוצע לשעבוד"; "אם הנכס משועבד (לדוגמה, להבטחת הלוואה של המוכר) – אישור שחרור השעבוד, סילוק ההלוואה או אישור פרי פסו, לפי דרישת הבנק"; "הצגת ערבות בנקאית או בטוחה אחרת לפי חוק המכר, במקרה של רכישת דירה חדשה"; "הוראת קבע מבנק מסחרי להסדרת גביית התשלום החודשי על חשבון ההלוואה"; "אישורים מיוחדים בהתאם להנחיות משרד הבינוי והשיכון"; "בהלוואות למימון בנייה – היתר בנייה ואישור מהנדס על שלב הבנייה"; "בהלוואות לרכישת דירה – חוזה רכישת הדירה חתום כחוק וכן צילום תעודת הזהות ומספר חשבון הבנק של מוכר הדירה בצירוף מסמך לאימות פרטי החשבון (צ'ק, אישור מהבנק וכדומה)."

### S04 — Property-lien documents PDF (2019)

Title: "מסמכים ופעולות הדרושים לשעבוד הנכס (מסמכים אלו יידרשו בהמשך התהליך בהתאם למקום רישום הנכס ולמצב הזכויות)" — *Documents and actions required to pledge the property (required later in the process, depending on where the property is registered and the state of rights).*

| Registration situation (verbatim heading) | Required items (verbatim) |
|---|---|
| "נכס שרשום בלשכת רישום המקרקעין ("טאבו") על שם המשעבד" — *registered in Tabu in the pledgor's name* | "רישום משכנתא לטובת הבנק בטאבו"; "טופס שיעבוד דירתי חתום בידי הלווה/ משעבד אחר" |
| "נכס שהזכויות בו רשומות על שם המשעבד במינהל מקרקעי ישראל ("המינהל") ו/או ב"חברה משכנת"" — *rights registered in the pledgor's name at Israel Land Authority and/or a housing company* | "שטר משכון חתום בידי הלווה/ משעבד אחר"; "הודעת משכון חתומה בידי הלווה/ משעבד אחר ואישור על רישומה ברשם המשכונות"; "ייפוי כוח בלתי חוזר מאושר על ידי נוטריון"; "טופס שיעבוד דירתי חתום בידי הלווה/ משעבד אחר"; "התחייבות לרישום משכנתא של המינהל או של החברה המשכנת" |
| "נכס שרשום בטאבו על שם המוכר ("יד שניה")" — *second-hand, registered in Tabu in the seller's name* | "שטר משכון חתום בידי הלווה/ משעבד אחר"; "הודעת משכון … ואישור על רישומה ברשם המשכונות"; "ייפוי כוח בלתי חוזר מאושר על ידי נוטריון"; "טופס שיעבוד דירתי …"; "התחייבות לרישום משכנתא חתומה בידי המוכר"; "רישום הערות אזהרה לגבי הנכס: לטובת הלווים - בגין הסכם הרכישה; לטובת הבנק - בגין התחייבות לרישום משכנתא של המוכר" |
| "נכס שהזכויות בו רשומות במינהל או בחברה משכנת על שם המוכר ("יד שנייה")" — *second-hand, rights at ILA/housing company in the seller's name* | "שטר משכון …"; "הודעת משכון … ואישור על רישומה ברשם המשכונות"; "ייפוי כוח בלתי חוזר מאושר על ידי נוטריון"; "התחייבות לרישום משכנתא של החברה המשכנת ו/או של המוכר"; "הודעת משכון חתומה בידי בעל הזכויות בנכס ואישור על רישומה ברשם המשכונות"; "טופס שיעבוד דירתי חתום בידי בעל הזכויות בנכס" |
| "ברכישת נכס "יד ראשונה" מחברה משכנת" — *first-hand purchase from a housing company/developer* | "שטר משכון …"; "הודעת משכון … ואישור על רישומה ברשם המשכונות"; "ייפוי כוח בלתי חוזר מאושר על ידי נוטריון"; "טופס שיעבוד דירתי …"; "התחייבות לרישום משכנתא חתומה בידי הקבלן ובידי הבעלים הרשומים של המקרקעין"; "רישום הערת אזהרה לטובת הבנק בגין ההתחייבויות הנ"ל"; "ערבות של רוכשי דירות לפי "חוק המכר (דירות) (הבטחת השקעות של רוכשי דירות) התשל"ה - 1974", המוסבת לבנק או בטוחה אחרת לפי אותו חוק"; "פנקס שוברי התשלום שהונפק על ידי הבנק המלווה (בהלוואות לרכישת דירה מקבלן בפרויקט המלווה על ידי תאגיד בנקאי על פי הסכם ליווי שנחתם לאחר 1.6.2008)" |

- **Sale Law note.** "חוק המכר (דירות) … אוסר על מוכר דירה חדשה לקבל יותר מ- 7% ממחיר הדירה אלא אם ייתן לרוכש הדירה בטוחה המיועדת להבטיח השקעותיו…" and "הבנק עשוי לדרוש מלווה שקונה דירה חדשה להציג בפניו הוכחה שקיבל בטוחה כזאת או שקיבל התחייבות להמצאתה. הבנק אף רשאי לדרוש כי ערבות על פי החוק תוסב לבנק; אולם אין הבנק חייב לעשות זאת ועל הלווה לוודא שהוא מקבל את הבטוחה המגיעה לו." — *A new-apartment seller may not receive more than 7% of the price without giving the buyer a security. The bank may require a buyer of a new apartment to prove they received such security or an undertaking to provide it, and may require the statutory guarantee to be endorsed to the bank; the bank is not obliged to, and the borrower must make sure they receive the security due to them.*

### S05 — Tasks when buying a second-hand apartment

Structure (from raw HTML): "## 1. המסמכים והפעולות שצריך להשלים" (*documents and actions you must complete*) and "## 2. המסמכים שצריך להשלים מול המוכרים" (*documents to complete vis-à-vis the sellers*), with "באמצעות עורך הדין שלהם" (*through their lawyer*). "החלוקה היא למען הסדר הטוב בלבד; אנו ממליצים לעשות את כל הדברים במקביל." — *The split is only for order; we recommend doing everything in parallel.*

**Part 1 — borrower**
- **Signing.** "חתימות על מסמכי הלוואת המשכנתא, כולל חתימת הערבים (אם ישנם)" — "איפה ואיך מבצעים: בפגישה בסניף" — *Signing the mortgage loan documents, including guarantors (if any): at a branch meeting.*
- **Pledge notice.** "הבנק דורש כי תמשכנו את הזכויות שלכם בנכס כביטחון למשכנתא" — "את המשכון רושמים אונליין מול רשם המשכונות. ניתן לעשות זאת בפגישה בסניף" — "עלות רישום לרשם המשכונות: 175 ₪" — *Pledge registered online with the Pledges Registrar, can be done at the branch meeting; fee ₪175.*
- **Inspection reports.** "לאחר רישום המשכון, יש להפיק דו"ח עיון מרשם המשכונות לכל אחד ממבקשי המשכנתא" — "אפשר לעשות זאת באתר www.gov.il בעמוד "עיון בשעבודים ומשכונות". את דו"חות העיון שהופקו יש להעלות באפליקציית טפחות טאצ' או לשלוח לבנקאי במייל" — "עלות: 11 ₪ עבור כל דו"ח" — *After registration, produce a Pledges Registrar inspection report for each applicant; upload via Tefahot Touch or email to the banker; ₪11 per report.*
- **Sole/replacement apartment affidavit.** "הצהרה שהדירה שאתם רוכשים היא דירתכם היחידה או החליפית" — "את הטופס תקבלו מהבנקאי. על כל אחד מכם לחתום על טופס נפרד, לדאוג שעורך דין יאמת את החתימה, ולאחר מכן להחזיר לבנקאי. (רלוונטי במשכנתא בשיעור מימון העולה על 50%)" — *Each borrower signs a separate form, signature verified by a lawyer; relevant when LTV exceeds 50%.*
- **Notarized POA.** "באמצעות טופס זה אתם נותנים לבנק ייפוי כוח להשלים את רישום הנכס על שמכם אם עורך הדין לא יעשה זאת" — "את הטופס תקבלו מהבנקאי ועליכם לחתום עליו בפני נוטריון. יש להחזיר לבנקאי את הטופס המקורי, חתום ומאומת על-ידי נוטריון" — *Return the original, signed and authenticated by a notary.*
- **Appraisal.** "בכל בקשה למשכנתא יש לפנות לשמאי לצורך הערכת שווי הדירה. זאת, כיוון שסכום המשכנתא אותו ניתן לקבל תלוי, בין היתר, בהערכת שווי הדירה" — "תקבלו מהבנקאי טופס אשר כולל רשימה של 3 שמאים, מהם תבחרו את מי שתרצו לצורך הערכת שווי הדירה. בטופס מפורטים המסמכים אותם יש להעביר לשמאי והתעריף אותו תשלמו. לאחר ביצוע ההערכה, השמאי יעביר ישירות לבנק את הערכת השווי (השמאות). ניתן לבקש העתק של השמאות מהשמאי." — *Every mortgage request requires an appraisal; the banker gives a form listing 3 appraisers, the documents to give the appraiser and the fee; the appraiser sends the valuation directly to the bank.*
- **Insurance.** "עליכם לרכוש שני סוגי פוליסות ביטוח:"
  - Life: "פוליסת ביטוח חיים - פוליסה עבור כל אחד מהלווים בגובה סכום המשכנתא ולכל תקופתה. הבנק צריך להיות מוטב בלתי חוזר בפוליסה, והפוליסה צריכה להיות משועבדת לבנק מזרחי-טפחות. חשוב לשים לב, כי מספר הסניף וכתובת הסניף רשומים בפוליסה" — *A policy for each borrower for the mortgage amount and full term; bank as irrevocable beneficiary; policy pledged to the bank; branch number and address must appear.*
  - Property: "פוליסת ביטוח נכס - פוליסה בגובה ערך הכינון (הסכום המוערך הדרוש לבניית הנכס מחדש), נתון הזה רושם השמאי. הפוליסה צריכה לכלול את הסעיפים הבאים: א. סעיף שעבוד לטובת בנק מזרחי-טפחות (כולל מספר הסניף וכתובת סניף) ב. רישום הבנק כמוטב בלתי חוזר ג. התחייבות להודעה מוקדמת במקרה של ביטול הפוליסה (30 יום מראש)" — *Reinstatement value (recorded by the appraiser); lien clause in favour of the bank incl. branch number and address; bank as irrevocable beneficiary; 30 days' advance notice of cancellation.*
  - "ניתן לרכוש פוליסה בסכום מלא של ערך כינון או בסכום חלקי." — *Full reinstatement value or partial amount allowed.*
  - "באפשרותכם לרכוש את הפוליסות בכל חברת ביטוח ובאמצעות כל סוכנות ביטוח, וגם באמצעות סוכנות הביטוח של הבנק." / "את הפוליסות שרכשתם ניתן להעלות באפליקציית טפחות טאצ' או לשלוח לבנקאי במייל." — *Any insurer; upload via Tefahot Touch or email.*
- **Income and current-account documents.** "בכל בקשת משכנתא, יש להעביר לבנק את המסמכים הבאים לטובת אימות ההכנסות והמצב הפיננסי שלכם:"
  - "דפי תנועות בחשבון הבנק מ-3 החודשים האחרונים (עבור כל חשבונות הבנק שלכם)"
  - "דו"ח ריכוז יתרות של הלוואות (אם ישנן) מכל חשבונות הבנק"
  - "אם אתם שכירים - 3 תלושי שכר אחרונים"
  - "אם אתם עצמאים - אישור רו"ח או יועץ מס על ההכנסה שלכם בשנה האחרונה + שומת מס לשנה הקודמת"
  - "אם אתם שכירים ועצמאים - את כל המפורט בשני הסעיפים הקודמים"
  - "אם אתם שכירים בעלי שליטה בחברה בע"מ - 3 תלושי שכר אחרונים + דו"חות כספיים מבוקרים של השנה הקודמת + מאזן בוחן לשנה השוטפת"
  - "ייתכן שהבנקאי יבקש מסמכים נוספים." — *The banker may request additional documents.*
  - **Freshness rule:** "אם חלפו יותר מ-45 יום מאז שהעברתם את המסמכים בפעם הקודמת, או שעדיין לא העברתם את כל המסמכים, יש להעביר את המסמכים מחדש או לשלוח את המסמכים החסרים." — *If more than 45 days have passed since you last submitted the documents, or you have not yet submitted all of them, resubmit the documents or send the missing ones.*
- **Liens/arrears.** "בתהליך לקיחת המשכנתא, הבנק פונה למערכת נתוני אשראי של בנק ישראל, כדי לבדוק את ההיסטוריה הפיננסית שלכם. אם יופיע מידע לגבי עיקולים או פיגורים, תידרשו להציג אסמכתאות מהגורמים הרלוונטיים על ביטולם" — *The bank queries the Bank of Israel credit-data system; if attachments or arrears appear, you must show proof of their cancellation from the relevant bodies.*
- **Standing order.** "כדי שהבנק יוכל לגבות את תשלומי המשכנתא מחשבונכם, יש להעביר לבנקאי הרשאה חתומה על ידי הבנק שבו מתנהל חשבון העובר ושב שלכם" — "ניתן לעשות זאת גם באופן עצמאי, באפליקציה של הבנק שלכם."
- **Eligibility certificate.** "זכאות - המצאת תעודת זכאות תקפה" — "כדי להגיש בקשה למשרד השיכון להפקת תעודת זכאות מתאימה, עליכם להציג מסמכים נוספים, כגון: אישור על שירות צבאי, תעודת נישואין, תצהיר אחים ואחיות, תעודת עולה ותעודות זהות כולל ספח." — "את רשימת המסמכים הרלוונטית לכם, תקבלו מהבנקאי"
- **File-opening fee.** "זו עמלה קבועה בכל הבנקים, עבור טיפול בהלוואת המשכנתא, שעומדת כיום על 360 ₪" — "במזומן, בצ'ק או באשראי"

**Part 2 — vis-à-vis the sellers**
- **Seller undertaking.** "את הטופס ששמו "התחייבות", עליכם להעביר באמצעות עורך הדין שלכם למוכרים או לעורך דינם. לאחר מכן, יש להחזיר לבנקאי את הטופס המקורי כשהוא חתום על ידי כל המוכרים ומאומת על ידי עורך דין"
- **Warning note for the bank.** "על הטופס ששמו "בקשה לרישום הערת אזהרה בגין התחייבות לרישום משכנתא בהסכמת כל הצדדים" צריכים לחתום המוכרים, ועורך דינם צריך לאמת את חתימתם. לאחר החתימה, עורך הדין ירשום הערת אזהרה לטובת בנק מזרחי-טפחות. יש להחזיר לבנקאי בסניף את הטופס המקורי החתום על-ידי המוכרים ומאומת על-ידי עורך הדין" / "הרישום בטאבו נעשה אונליין." / "בנוסף לטופס המקורי, יש להעביר לבנקאי את שני המסמכים הבאים: נסח טאבו לאחר הרישום. חשוב - לוודא כי נרשמה הערת אזהרה גם לטובתכם; אישור על ביצוע הרישום" — *Plus: Tabu extract after registration (verify a warning note was also registered for the buyers) and confirmation of registration.*
- **Tax approvals.** "עלינו לקבל מכם את כל אישורי המיסים בעסקה. את המסמכים תקבלו מעורך הדין שלכם או מעורך הדין של המוכרים": "העתק דיווח העסקה לשלטונות המס (מש"ח) + אישור דיווח דיגיטלי"; "אישור תשלום מס רכישה"; "אישור תשלום מס שבח (או אישור על הפקדת הסכום לתשלום מס השבח בנאמנות עורך דין)"; "אישור עירייה עדכני על היעדר חובות של בעל הנכס מול העירייה"
- **Equity payment confirmation.** "על המוכרים לאשר את גובה תשלום ההון העצמי שהועבר אליהם. יש להחתים את המוכרים על טופס ששמו "אישור על תשלום הון עצמי" ולהחזיר לבנקאי את הטופס המקורי חתום ומאומת על ידי עורך הדין של המוכרים או לצרף אסמכתה (צילום צ'ק או אישור על ביצוע העברה בנקאית) על כך שהתשלום בוצע"
- **Disbursement instruction form.** "תשלום על חשבון ההלוואה" — "זהו טופס מפרט את החשבון או את חשבונות הבנק אליהם צריך להעביר את כספי המשכנתא למוכרים (או לעורך הדין, לטובת סילוק משכנתא של המוכרים וכו'). את הטופס ממלא עורך הדין והוא מחתים עליו את המוכרים" / "שימו לב - גם אתם צריכים לחתום על הטופס מול עורך דין או בנקאי. את הטופס המקורי, החתום על ידי המוכרים והקונים ומאומת על ידי עורך דין, יש להחזיר לבנקאי." Plus:
  - "יש לצרף אסמכתה לכל חשבון בנק אליו מבקשים להעביר את הכספים"
  - "בהתאם לחוזה הרכישה, הבנק יעביר את הסכום האחרון של כספי המשכנתא רק לאחר קבלת אישורי המיסים עבור הנכס (תשלום מס שבח לדוגמה) או לאחר שיופקד בנאמנות עורך דין לחשבון נאמנות ספציפי. יש לצרף את אישורי המס הרשומים בחוזה או לציין את פרטי חשבון הנאמנות, ולצרף אסמכתה גם לחשבון זה"
  - "אם המוכרים משלמים משכנתא, יש לצרף מכתב כוונות מהבנק בו מתנהלת המשכנתא שלהם"
- **Seller ID.** "יש לצרף צילום תעודת זהות, כולל הספח המעיד על המצב המשפחתי של המוכרים"
- **Seller's spouse consent.** "אם למוכר/ת יש בן או בת זוג שאינם מופיעים כמוכר בחוזה, נדרש לקבל את הסכמתם. את ההסכמה מקבלים בטופס בשם "החתמת בן זוג של המוכר". את הטופס תקבלו מהבנקאי בטפחות ועליכם להחתים עליו את בן או בת הזוג ואת עורך הדין של המוכרים ולהחזירו לבנקאי"
- **Foreign-resident seller.** "אם מוכר הדירה הוא תושב חוץ (מזוהה על ידי דרכון), העברת הכספים תמורת הדירה חייבת בניכוי מס במקור. לכן נדרש להציג לסניף, לפני העברת הכספים, טופס בשם "אישור לרישום בפנקסי המקרקעין", אותו יש לבקש מעורך הדין"
- **Existing liens on property** (heading on page: "איסור על הסרת שעבודים", see F.24): "אם הנכס משועבד לטובת גורם אחר (למשל בנק אחר), יש להעביר לבנקאי אישור על הסרת השעבודים או מכתב כוונות מהגורם המשעבד"
- **Rented apartment.** "אם הדירה מושכרת יש לצרף את הסכם השכירות שנחתם עם השוכרים"
- **Channels.** "המומחים של טפחות זמינים עבורכם במגוון ערוצים: ב-WhatsApp, בהודעות SMS, באפליקציית טפחות טאצ', בטלפון 8860* וכמובן בסניף."

### S06 — Tasks when buying from a contractor

- **Rationale.** "ברכישה עם הלוואת משכנתא אתם חייבים להעמיד לרשות הבנק בטוחה שתספק את הבנק (ערך נכס מספק על פי השמאות, דירה הניתנת לשימוש וכד')" — *You must provide security that satisfies the bank (sufficient value per appraisal, usable apartment, etc.).*
- **Purchase contract.** "יש להעביר חוזה רכישה חתום מהקבלן" — "מי מבצע? הלווה" — "יש לשים לב לווה אחד יכול להציגו לבנק" — *Signed purchase contract from the contractor; one borrower may present it.*
- **Registry extract.** "נסח רישום מקורי / אישור זכויות מקורי" — "המטרה היא לבדוק את המצב הרישומי של הנכס, לוודא שאין עליו עיקולים או הערות מיוחדות וכד'. סוג האישור הינו בהתאם למקום הרישום של הנכס" — "לווה אחד יכול להציגו לבנק" — *Original registry extract / original rights confirmation, type depends on where registered.*
- **Signing.** "עם פתיחת תיק ההלוואה – כל הלווים חייבים לחתום על המסמכים בבנק (לא חובה ביחד, כל אחד יכול להגיע במועד שנוח לו)" — *All borrowers must sign at the bank, not necessarily together.*
- **Residential lien form.** "טופס עליו חותמים הלווים בפני הבנקאי לאחר קבלת הסברים מהבנקאי." — "בטופס זה מאשרים את קבלת ההסבר ביחס לזכויות משעבדי דירת המגורים במקרה בו ייאלץ הבנק לממש את המשכנתא ולמכור את הדירה"
- **Pledge deed.** "מסמך שעבוד הדירה שנחתם על-ידי כל הלווים והמשעבדים מול הבנקאי בבנק"
- **Pledge notice.** "כיום יכולים רוב הלקוחות לבצע את רישום משכון מול בנקאי המשכנתאות בסניף." … "בסיום התהליך המקוון מתקבל במחשב הבנקאי מסמך אישור על רישום משכון. לאחר מכן, יש להפיק מאתר האינטרנט של הרשם דוחות עיון על שם הלווים והמשעבדים - זהו דו"ח המציג את נתוני כל המשכונים על-פי מספר ת.ז." Fallback: "במקרים בהם לא ניתן לבצע רישום משכון מקוון (על פי הנחיית הבנקאי), יש לגשת לרשם המשכונות עם טופס "הודעת משכון" חתום על-ידי כל הלווים והמשעבדים (הלווים והמשעבדים אינם חייבים להגיע יחד לרשם, מספיק אחד מהם או מיופה כוח) ולקבל אישור על רישום משכון."
- **Notarized POA.** "ייפוי כוח מנוטריון מייפה את כוחו של הבנק להשלים את הרישום ע"ש המשעבדים" — "מי מבצע? המשעבדים מול נוטריון"
- **Contractor undertaking.** "התחייבות לרישום משכנתא חתומה בידי הקבלן" — "החתמת המוכר על טופס ייעודי שתקבלו מהבנק" — "מי מבצע? הלווה מול הקבלן. ההתחייבות תחתם על-ידי הקבלן בפני עו"ד."
- **Guarantee documents.** "הסבת ערבות, התחייבות להמצאת ערבות ומכתב החרגה" — "מסמכים שיש להמציא מהקבלן" — *Endorsement of guarantee, undertaking to provide a guarantee, and exclusion letter — from the contractor.*
- **Vouchers.** "בפרויקט המלווה על ידי גוף פיננסי – התשלום לקבלן מתבצע באמצעות שוברי תשלום. את פנקס השוברים שתקבלו מהקבלן יש להציג לבנקאי" — "בכל ביצוע של תשלום יש להביא שובר"
- **Purchase tax.** "דיווח לרשויות המס על ביצוע העסקה, אישורים על תשלום מיסים" — "מי מבצע? הלווה מול עורך הדין המלווה"
- **Equity via vouchers.** "ההון העצמי ישולם בתחילה ואחר כך כספי המשכנתא - יש לקבל אישור מהקבלן על ההון העצמי ששילמתם לו, ההון העצמי וכן הלוואת המשכנתא ישולמו באמצעות שוברי נדל"ן." — "אישור הקבלן / אסמכתה לשוברים משולמים" — *Equity is paid first, then mortgage funds; get contractor confirmation of equity paid.*
- **Appraisal.** "במקרים מסוימים, הבנק יבקש שמאות לדירה כדי לוודא את ערך הנכס. … את ההפניה לשמאות מקבלים מהבנק (3 שמות עם פרטי התקשרות של שמאים מאושרים, מתוכם בוחרים אחד)" — "התשלום לשמאי מתבצע על-פי תעריף קבוע"
- **Standing order.** "זוהי הוראה לחיוב החשבון בבנק המסחרי לצורך הסדרת התשלום החודשי בגין הלוואת המשכנתא. יבוצע על-ידי הבנקאי המטפל בתיק" — "חתימה מול הבנקאי"
- **Insurance.** "בעת ביצוע הלוואת משכנתא תחויבו להמציא לבנק פוליסות ביטוח מבנה וביטוח חיים." — "לגבי נכס שבנייתו לא הושלמה, תדרשו להתחייב להמציא פוליסת ביטוח נכס בעתיד לכשתושלם הבנייה." — *For a property under construction, you must undertake to provide a property policy once construction is completed.*

### S07 — Official mortgage loan guide (form 154, version 11.2023)

- **Loan purposes (p.2).** "במזרחי-טפחות אפשר לקבל הלוואה מכספי הבנק למטרות שונות: א. רכישת דירת מגורים או נכס מקרקעין אחר (למשל: מגרש, משרד, חנות וכו'); ב. בניית בית מגורים; ג. שיפוץ דירה או הרחבתה; ד. מטרות אחרות - כגון: כל מטרה (כולל כרטיס אשראי טפחות), אירוע משפחתי, רכישת רכב, הלוואה פנסיוניות."
- **Eligibility certificate (p.1).** "כדי לקבל הלוואת זכאות תוכלו להגיש בקשה לתעודת זכאות באחד מסניפי הבנק, בצירוף המסמכים המפורטים בהמשך מדריך זה." / "הבנק יגיש עבורכם את הבקשה להנפקת תעודת הזכאות, אולם, מועד הנפקתה והנפקתה בכלל, אינם באחריות הבנק"
- **Credit criteria (§2, p.5).** "כדי לקבל הלוואה עליכם לעמוד בקריטריונים ובתנאים שהבנק קבע במספר מישורים: כושר ההחזר, טיב הנכס לשעבוד והערבים להלוואה." Main criteria: "עמידה במבחן של גיל, תעסוקה והכנסה כדי להבטיח, בסבירות גבוהה, את פירעון ההלוואה;" "ההלוואה תהיה מובטחת בשעבוד נכס מקרקעין;" "סכום ההלוואה לא יעלה על שיעור מסוים מערך הנכס (במקרים מסוימים ייתכן שיידרש ביטוח אשראי);" "ערבים - טיב הערבים ומספרם ייקבע לפי קריטריונים שונים, כגון סכום ההלוואה המבוקש, הביטחון הנכסי המוצע וכד'. במקרים מסויימים לא יידרשו ערבים כלל;" "כאשר קיימות הלוואות קודמות: אין, ולא היו בהן, פיגורים משמעותיים."
- **Process (§3, p.6)** — quoted in full in D.1.
- **Sale Law (§4, p.6).** "הבנק ידרוש מלווה שקנה דירה חדשה להציג בפניו הוכחה שקיבל בטוחה כזאת או שקיבל התחייבות להמצאתה. הבנק אף רשאי לדרוש כי ערבות על פי החוק תוסב לבנק; על הלווה לוודא שהוא מקבל את הבטוחה המגיעה לו."
- **Voucher book (§5, p.7).** "בפרויקטים שהסכם הליווי לגביהם נחתם לאחר 1.6.2008, מונפק על ידי הבנק המלווה פנקס שוברי תשלום, אשר רק באמצעותו ניתן לבצע את התשלומים לרכישת הדירה כולל התשלומים על חשבון ההלוואה."
- **Execution and payment dates (§6, p.7).** "מועד הפירעון של הלוואה הוא ב-1, ב-10 או ב-15 בכל חודש, לפי בחירתכם לפני ביצוע ההלוואה." / "ככלל, מועד הביצוע של ההלוואה נקבע על ידי הלווים (בכפוף להשלמת כל הפעולות הנדרשות לשם כך)." / Transfers: an instruction given on a business day Sun–Thu "לפני השעה 18:30, תבוצע בו ביום"; on a short business day "לפני השעה 13:00".
- **Costs and appraisal fees (§7, p.8).** "במקרים בהם נדרשת שמאות כתנאי לביצוע ההלוואה, עלות שמאות תשולם ישירות לשמאי על ידי הלקוח." / "העלויות הספציפיות לכל לקוח תפורטנה בהפניה להערכת שמאי."

| Appraisal type (verbatim) | Cost range |
|---|---|
| "הערכת שמאי להלוואות מוכוונות (לזכאי משרד השיכון בלבד) ועד שווי נכס של 2.1 מ' ₪." | ₪390–481 |
| "שומה מקוצרת/רגילה (לאחר רכישה) – משמשת לדירות גן וגג עד לשווי של 1.3 מ' ש"ח (כולל), וכן לכל יתר סוגי הדירות בבניה בבית קומות בסכום של עד 5 מ' ₪ (כולל)." | ₪850–4,420 |
| "סוג שמאות מורחבת (לאחר רכישה) – משמשת למגרשים, בניה עצמית, צמודי קרקע, דירות גן וגג בסכום שעולה על 1.3 מ' ₪. בנוסף משמשת לכל יתר סוגי הדירות בבית קומות בשווי העולה על 5 מ' ₪ ועד לסכום של 10 מ' ₪ (כולל) ובכפוף לכך ששיעור המימון אינו עולה על 50% וסכום אשראי אינו עולה על 3 מ' ₪." | ₪1,600–6,040 |
| "סוג שמאות תקן 19 (לאחר רכישה) – משמשת לנחלות. בנוסף משמשת לכל יתר הנכסים בשווי העולה על 5 מ' ₪ ועד 10 מ' ₪ (כולל) במקרה ששיעור המימון עולה על 50% ו/או במקרה שסכום האשראי עולה על 3 מ' ₪." | ₪4,400–9,750 |
| "סוג שמאות תקן 19 (לאחר רכישה) משמשת למקרים בהם שווי הנכס עולה על 10 מ' ₪." / "סוג שמאות תקן 19 – שמאות טרום רכישה." | "התעריף בתיאום הלקוח מול השמאי" |

- **Interest-rate lock (§8, pp.8–9).** "אם על פי אישור הבקשה להלוואה לא נדרש רישום שעבוד נוסף להבטחת ההלוואה - תוקף שמירת הריבית יהיה 12 יום מיום האישור." / "אם על פי אישור הבקשה להלוואה נדרש רישום שעבוד חדש/נוסף להבטחת ההלוואה: – כל עוד לא הוצגו פרטי הנכס המיועד לשעבוד לצורך הבטחת ההלוואה – תוקף שמירת הריבית יהיה 24 יום מיום האישור. – לאחר הצגת פרטי הנכס המיועד לשעבוד לצורך הבטחת ההלוואה – תוקף שמירת הריבית באישור הראשון יהיה 24 יום מיום האישור. בכל אישור מאוחר יותר – תוקף שמירת הריבית יהיה 12 יום מיום האישור." — *Rate lock: 12 days if no new lien is needed; 24 days while property details are not presented; 24 days on the first approval after presenting them; 12 days on any later approval.*
- **Insurance (§9, pp.10–12).**
  - "חובה לבטח כל נכס שישועבד להבטחת ההלוואה. כמו כן, הבנק דורש, בדרך כלל, שכל לווה הכשיר לכך יהיה מבוטח בביטוח חיים."
  - Contractor purchase: "(לגבי מי שרכש דירת מגורים מקבלן, החובה לבטח את הנכס תחול רק מהמועד בו התחייב הקבלן למסור את הדירה לקונה)"
  - Property clauses: "הבנק רשאי לעמוד על קיומם של תנאים הדרושים לשם הבטחת זכויותיו, לרבות קיומם של הסעיפים הבאים: סעיף שעבוד לטובתו וקביעת הבנק כמוטב בנוסח שייקבע על ידי הבנק מעת לעת, סעיף רעידת אדמה וסעיף הודעה מוקדמת של 30 יום במקרה של ביטול הפוליסה."
  - Sum insured: "מומלץ כי סכום הביטוח ישקף את עלויות הבנייה מחדש של הנכס (להלן: "ערך כינון"). ברוב המקרים, ערך הכינון נקבע על ידי השמאי שמעריך את שווי הנכס."
  - Partial insurance: "בסכום שלא יפחת מהיתרה המשוערכת של כל ההלוואות המובטחות בשעבוד אותו הנכס, בניכוי ערך הקרקע המתייחס לדירה, בהתאם להערכת שמאי שתציגו, בתוספת עד 20% מהיתרה שהתקבלה (להלן: "ביטוח לפי יתרה")" / "הבנק אינו ממליץ על "ביטוח חלקי""
  - Property-insurance exemptions: "יתרת כל ההלוואות בשעבוד הנכס אינה עולה על 30,000 ₪."; "שווי הקרקע של הנכס המשועבד, על פי שמאות המקובלת על הבנק, שווה ליתרה המשוערכת הבלתי מסולקת של כל ההלוואות המובטחות בשעבוד הנכס או גבוה ממנה."; "כל ההלוואות בשעבוד הנכס מורכבות מכספי מענק בלבד או הלוואות עומדות בלבד."; "כל ההלוואות בשעבוד הנכס מורכבות רק מסיוע מוגדל לעולי אתיופיה."
  - Life: "הבנק דורש, בדרך כלל, שכל לווה הכשיר לכך, יהיה מבוטח בביטוח חיים ממועד ביצוע ההלוואה ועד למועד פרעונה המלא של ההלוואה, אשר ישולם לבנק לזכות חשבון ההלוואה, במקרה של פטירת הלווה, בסכום יתרת ההלוואה בתוספת עמלת פרעון מוקדם." Clauses: "סעיף שעבוד לטובתו וקביעת הבנק כמוטב, בנוסח שייקבע על ידי הבנק מעת לעת וסעיף הודעה מוקדמת של 30 יום במקרה של ביטול הפוליסה." Approval risk: "זכותו של הבנק שלא לאשר, או אף לבטל, אישור להלוואה שכבר ניתן, אם הלווה או אחד הלווים יימצא כלא כשיר להיות מבוטח בביטוח חיים בהתאם לדרישות הבנק."
  - Life-insurance exemptions: "יתרת כל ההלוואות של הלווה בשעבוד נכס מסוים אינה עולה על 30,000 ₪."; "לא חלה חובת ביטוח על רכיבי מענק והלוואות עומדות."; "גיל הלווה בעת ביצוע ההלוואה עולה על 70 שנה."; "הלוואת כרטיס אשראי טפחות (בהלוואות אלו, הבנק רשאי אך אינו חייב לדרוש בעתיד המצאת פוליסת ביטוח חיים בגין סכומים שנוצלו בכרטיס)."
  - Agency policies: "טופס המפרט את פרטי הביטוח העיקריים יימסר ללווה בתום פעולת הרכישה בעמדה שבסניף. פוליסה מלאה תשלח לאחר ביצוע ההלוואה."
  - Credit insurance: "במקרים מסויימים יתנה הבנק את ביצוע ההלוואה בביטוח האשראי (על ידי חברת EMI)." / "סכום הפרמיה נקבע בהתחשב במרכיבים הבאים: סכום ההלוואה, תקופת ההלוואה והיחס בין סכום ההלוואה לשווי הנכס המשועבד (שיעור המימון)."
- **Early repayment notice (§10, p.13).** "עמלת אי הודעה מוקדמת - 0.1% מהסכום הנפרע, נגבית רק אם הלווה לא מסר לבנק הודעה מוקדמת על הכוונה לפרוע את ההלוואה 10 ימים לפחות לפני יום הפירעון אך לא יותר מ-45 יום לפני יום הפירעון."
- **Porting (§11, p.15).** "במקרים מסויימים תוכלו למכור את הנכס שבגינו ניתנה ההלוואה ולגרור את ההלוואה לנכס אחר. הקריטריונים לגרירה ותנאיה כפופים לנוהלי הבנק ולנוהלי משרד הבינוי והשיכון"
- **Waiver of protected/alternative housing (§14, p.15).** "הבנק דורש שכל מסמכי השעבוד לצורך ביצוע ההלוואה יכללו ויתור על זכות לקבלת דיור חלופי ו/או במקרים מסויימים, לזכויות דיור מוגן"
- **Required documents (§15, pp.15–17)** — every item is in section C. Intro: "להלן רשימת המסמכים הנדרשים במקרים שונים, לצורך ביצוע ההלוואה. במקרים מסויימים, יתכן שתדרשו להביא מסמכים נוספים, בהתאם לזהות הלווים והערבים, נתוני הבקשה, סוג הנכס, ולהנחיות משרד הבינוי והשיכון, ככל שרלבנטיות." Sub-headings: "ב. מסמכים נדרשים לאישור הלוואה וביצועה"; "מסמכים המתייחסים ללווים:"; "מסמכים המתייחסים לערבים בהלוואה:"; "מסמכים המתייחסים לנכס אשר ישועבד לבנק (רצוי, אך אין חובה, להמציא מסמכים אלה לפני אישור עקרוני להלוואה):"; "מסמכים ופעולות לצורך ביצוע ההלוואה (אם אושרה):"; "מסמכים ופעולות הדרושים לשעבוד הנכס לפי הפירוט דלהלן:" (same five registration situations as S04, with "רשות מקרקעי ישראל ("רמ"י")" instead of "המינהל").
- **Disclaimer (p.18).** "זהו מסמך כללי ועל כן אין להתייחס אליו כמסמך הממצה את דרישות הבנק לגבי הלוואה מסויימת. כדי לקבל את ההלוואה עליכם לפעול על פי ההנחיות שיינתנו לכם ע"י פקידי הבנק וכמפורט במסמכי ההתקשרות."
- **Acknowledgment (p.20).** "לאישור בעת קבלת מסמכים באמצעי בנקאות בתקשורת בלבד - הרינו מאשרים קבלת המסמך:" (name, ID, borrower signature, date).

### S08 — Useful mortgage forms page, with forms S09–S14

- **Mortgage deed (שטר משכנתא).** "שטר משכנתא נועד לביצוע שיעבוד הנכס לבנק לפי הסכם ההלוואה. השטר מופק לצורך רישום משכנתא על הנכס בטאבו." / "להפקת שטר משכנתא יש לשלוח את הטופס בצירוף המסמכים המצוינים בו למרכז המשכנתאות למייל bithonot@umtb.co.il."
  - S09 (form 3801, 11.2025): "על מנת שיונפקו שטר/י משכנתה עלינו להעביר לבנק בקשתינו על גבי טופס זה בצירוף לפחות אחד מהמסמכים הבאים (נא סמנו אילו מסמכים צורפו לטופס): העתק נסח רישום מקרקעין (טאבו) מעודכן; העתק שטר מכר; העתק שטר שכירות; העתק "דרישה לרישום זכויות בלשכת רישום המקרקעין" (מסמך מטעם רשות מקרקעי ישראל)". "במקרה בו השתנו פרטי הנכס הידועים לבנק בעקבות הליך פרצלציה שנרשם במקרקעין יש לצרף, בנוסף לאחד המסמכים שלעיל, אישור בדבר רישום הפרצלציה." "במקרה בו רשומה לטובת הבנק הערת אזהרה בלשכת רישום המקרקעין, יש לצרף גם נסח רישום מקרקעין בו רשומה הערת האזהרה הנ"ל." Copies: "רישום מקוון בלשכת רישום המקרקעין – עותק אחד"; "רישום ידני בלשכת רישום המקרקעין – 5 עותקים" ("נכון להיום מרבית הרישומים בלשכת רישום המקרקעין מבוצעים באופן מקוון").
- **Standing order.** "ניתן להקים או לשנות באופן עצמאי הרשאה לחיוב חשבון לקוד מוסד 704 (בנק מזרחי-טפחות)" / "אם החיוב מפוצל במספר חשבונות או שהבקשה מתייחסת לחשבון בנק שאינו של הלווים, יש לפנות למרכז המשכנתאות (8860*) לקבלת הנחיות."
- **Payment date change.** "מועדי החיוב האפשריים הם: 1, 10 או 15 בחודש." / "בתנאי שהבקשה הוגשה עד ה-23 בחודש הנוכחי."
- **Lien release (expedited).** "שחרור שעבוד יבוצע 30 יום לאחר קבלת אסמכתה להעברת הכספים." Attach relevant items from: "נסח טאבו או אישור זכויות"; "דו"ח רישום משכון ודו"ח תוצאות עיון".
- **Borrower death (S13, form 2142).** "שולחים את הטופס בצירוף תעודת פטירה וצו ירושה (אם יש) וכן כל מסמך אחר התומך בתביעה" / "יש להמשיך בתשלומי הלוואת המשכנתא עד לקבלת תשובה מחברת הביטוח." The form's attachment checklist: "תעודה רפואית לסיבת המוות"; "העתק מתעודת פטירה רשמית ממשרד הפנים"; "פוליסת ביטוח חיים"; "טופס ויתור על סודיות רפואית חתום ע"י יורשי המנוח (במידת הצורך)"; "צו ירושה/ צו קיום צוואה בצירוף צוואה (במידת הצורך)"; "מסמכים ודוחות רפואיים הקשורים לתביעה".
- **Insurance exemptions.** "לקבלת הפטור יש לציין את פרטי הנכס ולבחור את הסיבה לבקשת הפטור מתוך הסיבות המצוינות בטופס." (forms 2812, 2818)
  - S12 (property, 2812) reasons: "יתרת כל ההלוואות בשעבוד הנכס אינו עולה על 30,000 ש"ח ועפ"י הוראות המפקח על הבנקים, בהוראה 451…"; "ערך הקרקע של הנכס המשועבד שווה או עולה מיתרת ההלוואה המשוערכת הבלתי מסולקת…"; "כל ההלוואות בשעבוד הנכס מורכבות מכספי מענק זכאות בלבד…"; "כל הלוואות בשעבוד הנכס מורכבות מסיוע מוגבר לעולים מאתיופיה בלבד…"; "הארכת הלוואת/ משנה הבלון ב-___ חודשים…". Guarantors also sign: "אנו הערבים הח"מ, מאשרים כי קראנו את המסמך דלעיל ומסכימים לכל האמור בו".
  - S11 (life, 2818) reasons (digits from image): "עפ"י הוראות משרד הבינוי והשיכון לא חלה עלינו חובה להיות מבוטחים בביטוח חיים על כספי מענק הזכאות."; "עפ"י הוראות המפקח על הבנקים, בהוראה 451 נקבע כי תאגיד בנקאי לא יסרב לבקשתו של לווה שלא לחייב אותו לבצע ביטוחים, וזאת לגבי הלוואות בסכומים עד 30,000 ₪ או שיתרתן אינה עולה על הסכום הנ"ל."; "הארכת הלוואת/ משנה הבלון ב-___ חודשים…".
- **Letter of intent.** "את הבקשה צריכים להגיש לקוחות שמסלקים או ממחזרים משכנתא והתבקשו להנפיק מכתב כוונות" / "מומלץ לצרף לבקשה נסח טאבו עדכני או אישור זכויות עדכני. מכתב כוונות מונפק עד 3 ימי עסקים מקבלת הבקשה בבנק. תוקפו של מכתב הכוונות הוא 30 יום מיום הנפקתו." — *Letter of intent issued within 3 business days; valid 30 days from issue.*
- **Second-degree lien (S10, form 2813).** "לקבל את אישור הבנק לרשום משכנתא בדרגה שנייה או בדרגה שווה לטובת גוף מממן נוסף … בלי לפרוע את המשכנתא הקיימת במלואה. אישור הבקשה - בכפוף לשיקול דעת הבנק." Form attachments: "נסח טאבו/אישור זכויות עדכני."; "טופס "בקשה להסכמה לפרי פסו/דרגה שניה" מהנושה הנוסף." Plus "ידוע לנו כי אם פרטי הנכס כפי שצוינו בטבלה לעיל אינם תואמים את המופיע ברישומי הבנק, ולא צורף נסח טאבו/אישור זכויות עדכני בו מופיעים הפרטים שצוינו, לא ניתן יהיה להנפיק את כתב ההסכמה."; "עבור הפקת מכתב הסכמה נחויב בעמלה בסך 150 ₪"; "ידוע לנו כי ייתכן שנדרש להמציא אישורי הכנסות לצורך בחינת הבקשה."
- **Payoff by bank transfer.** "היום הקובע של סכום הסילוק הוא יום ההעברה הבנקאית בפועל" / "נכנסים לאתר הפעולות ומגישים בקשה, בצירוף אסמכתה על ביצוע ההעברה הבנקאית"
- **Early repayment notice.** "כדי ליהנות מהפטור יש לסלק את ההלוואה החל מ-10 ימים ממועד משלוח ההודעה לבנק - ולמשך 45 ימים." S14 (form 2852): "הפטור מעמלת "אי הודעה מוקדמת" ייכנס לתוקפו לאחר 10 ימים מיום קבלת ההודעה בבנק, ויהיה תקף למשך 35 ימים נוספים." / "אם לא אבצע את סילוק ההלוואה במהלך 35 הימים כמתואר לעיל, לא יינתן לי פטור נוסף … למשך 6 חודשים."
- **Certificates.** "הפקת אישור מטרת הלוואה וסוג אשראי — האישור מיועד לבעלי משכנתא המעוניינים לבצע מחזור משכנתא וקישור נכס להלוואה." / "הפקת אישור יתרות קרן — … המעוניינים לקבל החזרי מס או נדרשים להגיש הצהרת הון."
- **Acknowledgment SLA (repeated on most forms).** "לאחר כ-24 שעות מקבלים SMS המאשר שהמסמך התקבל והועבר לטיפול"

### S15–S19, S40 — Application channels and Tefahot Touch

- S15: "פונים למומחים של טפחות בדרך שהכי נוחה לכם – בדיגיטל, בצ'אט, ב-WhatsApp או בטלפון - ומקבלים אישור עקרוני מהיר"; "קבלת אישור עקרוני מהיר ללא צורך בהגעה לסניף"; "התכתבות דרך אפליקציית טפחות טאצ' ישירות עם מומחה המשכנתאות לאחר הגשת בקשה. זהו שירות ייחודי של מזרחי-טפחות, המאפשר להתעדכן בזמן אמת בבקשת המשכנתא שהגשתם"
- S16: "טפחות טאצ' מאפשרת לכם: לדעת מה קורה בכל שלב בתהליך, ומה נותר להשלים; עושה לכם סדר בכל המשימות עם עדכונים ישירות לנייד שלכם; מומחה משכנתאות שמלווה אתכם - לא בוט, בן אדם; שליחה וקבלה של מסמכים בקלות - אין צורך להגיע לסניף" and "המאפשרת לכם לנהל את תהליך לקיחת המשכנתא מהנייד שלכם, מכל מקום ובכל זמן, משלב הגשת הבקשה למשכנתא ועד קבלתה."
- S17: "מגישים בקשה למשכנתא ומקבלים עדכון אם קיבלתם אישור עקרוני; מעלים מסמכים ומורידים אישורים בלי להגיע לסניף; מתאמים ומעדכנים מועדי פגישות; נהנים מליווי צמוד של מומחה משכנתאות; מתעדכנים בכל שלב בתהליך עד לקבלה של כל כספי המשכנתא"; "באמצעות טפחות טאצ' אפשר לקחת משכנתא חדשה או למחזר משכנתא קיימת"; "האפליקציה זמינה ללקוחות כל הבנקים"; "כלים לניהול המשכנתא, כמו מחשבון, ומידע מאתר מדלן…"
- S18: "להתעדכן בזמן אמת באיזה שלב נמצאת בקשת ההלוואה שהגשתם, מה משמעות שלב זה ומהם השלבים הבאים; לשלוח את כל המסמכים הדרושים ולקבל את האישורים מהבנק מבלי להגיע לסניף; להתכתב עם מומחה משכנתאות; להתעדכן בפרטי הפגישה שנקבעה עם הבנקאי שלכם…" and "חלק מהפעולות הנדרשות ללקיחת משכנתא, שעד עתה היה צורך להגיע לסניף כדי לבצע אותן, ניתן מעכשיו לעשות בקלות דרך טפחות טאצ'."
- S40: same list, with "לתאם פגישה עם הבנקאי שלכם ולהתעדכן בפרטי הפגישה" and "לשלוח ולקבל את כל המסמכים הדרושים בלי להגיע לסניף"; "מלווה אתכם … מהרגע שהגשתם בקשה למשכנתא ועד קבלת ההלוואה."
- S19 (advisers' interface): "לפתוח בקשה חדשה באמצעות טופס דיגיטלי; להתעדכן בפגישות הקרובות; לצפות באופן מרוכז בכל הלקוחות בטיפולכם; לבצע סינון לפי סטטוס הבקשה; לצפות בתמהילי ריביות, כולל תמהילי ריביות מוצעות של בנק ישראל"; login: "מזינים מספר תעודת זהות ואת מספר הטלפון המעודכן בבנק … מזינים את קוד האימות שהתקבל במסרון".

### S20–S22 — Mortgage insurance

- S20: "קבלת משכנתא מהבנק מחייבת את הרוכשים לבטח את המשכנתא." / "ביטוח משכנתא כולל שני ביטוחים שונים - ביטוח חיים וביטוח נכס" / "אם החלטתם לקחת משכנתא במזרחי-טפחות אך לרכוש ביטוח למשכנתא שלא באמצעות טפחות סוכנות לביטוח, יש להמציא לבנק עותק של הפוליסה העונה על דרישות הבנק, בתנאים המפורטים בהסכם ההלוואה." / Disclaimer: "הביטוחים נדרשים עבור כל הלוואה שיתרתה מעל 30,000 ₪." (Agency product detail, not a bank requirement: "דיור חלופי ל-12 חודשים או בגובה 15% מסכום הביטוח (הנמוך מביניהם)".)
- S21 (policy purchase and renewal):
  - "על פי דרישת הבנק, בעת לקיחת הלוואת משכנתא יש להמציא לבנק פוליסת ביטוח משכנתא."
  - "פרטי הביטוחים … מרוכזים באתר הפעולות תחת משכנתאות שלי >> ביטוחים. ניתן לאתר את החברה המבטחת, תוקף הביטוח, סכום הביטוח, כתובת הנכס המבוטח ושמות המבוטחים בביטוח חיים."
  - "פוליסה חדשה למשכנתא קיימת ניתן לשלוח אלינו למייל polisa@umtb.co.il או לפקס 03-5656666." Attach: "את מסמך הפוליסה בלבד - חיים ונכס"; "ביטולי פוליסה".
  - Checks before sending: "לשלוח כל פוליסה במייל נפרד, כקובץ pdf ללא תמונות."; "לציין את שם הלווה (בעל המשכנתא) ואת מספר הלוואת המשכנתא לה מיועדת הפוליסה."; "לרשום את בנק מזרחי-טפחות כמוטב בלתי חוזר ולוודא קיום סעיף הודעה 30 יום לפני ביטול הפוליסה."; "לוודא שהסכומים המצוינים בפוליסה תואמים לדרישות הבנק ושתקופת הפוליסה תואמת את תקופת ההלוואה."; "לוודא שכתובתכם למשלוח דואר מעודכנת ברישומי הבנק לנושא משכנתאות."
  - Bank review outcome: "הפוליסה תיבדק על ידינו. לאחר אישור, נשלח מסמך אישור לכתובת שלך המעודכנת בבנק. אם הפוליסה אינה תקינה, נשלח מכתב הכולל הסבר לתיקון הדרוש."
- S22 repeats the renewal rules (email polisa@umtb.co.il; "את מסמך הפוליסה בלבד - חיים ונכס"; "ביטולי פוליסה").

### S23–S27 — Equity, eligibility, price-for-resident, discounted apartments

- S23: "כדי שתוכלו לקבל משכנתא, אתם צריכים הון עצמי בשיעור של 25% מעלות הדירה שאתם רוצים לרכוש." / "25% - זהו שיעור ההון העצמי שאיתו תצטרכו להגיע לבנק כאשר תבקשו משכנתא עבור הדירה הראשונה שלכם."
- S24 (eligibility):
  - Documents: "מסמכים להנפקת תעודת זכאות": "תעודת זהות של הלווים כולל ספח"; "תעודת זהות של אחד מהורי כל אחד מהמבקשים (כולל ספח), או תצהיר הכולל את פרטי האחים והאחיות של המבקשים"; "אישור לגבי שירות בטחוני. שירות בצה"ל: אישור על מהלך שירות צבאי. ניתן להנפיק באתר צה"ל. שירות לאומי: אישור מהרשות לשירות לאומי אזרחי או מהגוף המוכר בו בוצע השירות הלאומי. שירות אזרחי: אישור מהרשות לשירות אזרחי."; "שירות מילואים: אישור מסוג "אישור שירות מילואים שש שנתי". ניתן להנפיק באתר המילואים של צה"ל"; "מסמכים המעידים על מצב אישי (תעודת נישואין, תעודת גירושין וכדומה)"; "אישור מהרבנות על הרשמה לנישואין (לזוגות העומדים להינשא)"; "מבקשת משכנתא הנמצאת בהריון (משבוע 24 ואילך) – אישור מרופא על ההיריון"; "תעודת עולה (אם אחד מהמבקשים הוא עולה חדש, גם אם אינה בתוקף)"; "במקרים מסוימים ייתכן שיידרשו מסמכים נוספים, בהתאם למעמד האישי של הזכאים ולהנחיות משרד הבינוי והשיכון."
  - Validity: "תוקף תעודת הזכאות הוא לרוב שנה מיום ההרשמה לקבלת תעודת זכאות" / "אם חל שינוי בנתונים האישיים שלך (שינוי במצב המשפחתי, לידת ילד וכו'), אזי לפני קבלת ההלוואה עליך לעדכן את התעודה או להאריך את תוקף התעודה (אם פג תוקפה), באחד מסניפי הבנק"
  - Issue time: "זמן הנפקת התעודה נע בין מספר ימים למספר שבועות, והוא תלוי במשרד הבינוי והשיכון" / "ניתן להנפיק את תעודת הזכאות עוד לפני רכישת דירה ולפני הגשת הבקשה להלוואה"
  - Two requests: "למימוש הלוואת הזכאות יש להגיש שתי בקשות: בקשה להנפקת תעודת זכאות בצירוף המסמכים הדרושים, באמצעות נציגי הבנק … ; בקשת משכנתא"
- S25 (price-for-resident): "הגובה המרבי של המשכנתא במסגרת מחיר למשתכן נקבע לפי שווי השוק של הדירה ולא לפי מחיר רכישתה. הקלה זו מאפשרת שיעור מימון גבוה יותר מ-75% מהתשלום עבור הדירה הנרכשת." / "ההקלה מותנית בכך שתשלמו לפני קבלת המשכנתא 100,000 ₪ לפחות מהון העצמי שלכם ובתנאי ששווי הדירה לא יעלה על 1.8 מיליון ₪." / "הנפקת תעודת זכאות חינם"
- S26: "אנו ממליצים לפנות לבנק ולקבל אישור עקרוני להלוואת משכנתא לאחר זכייתכם בתוכנית, ולפני כנס ההסברה" / "אישור עקרוני אינו מהווה התחייבות של הבנק להעמיד לכם את ההלוואה, אלא מגדיר את סכום המסגרת להלוואה אותה אתם יכולים לקבל. האישור העקרוני מוגבל בזמן, אך ככל שלא חל שינוי לרעה במצבכם הפיננסי, ניתן יהיה, בכפוף להצגת אישורים מתאימים, להאריך את תוקף האישור." — *Preliminary approval is time-limited (no number given) and extendable with appropriate documents if your finances did not worsen.*
- S27: "הזוכים בהגרלות לדירה בהנחה יכלו להסתפק בהון עצמי של 100,000 ₪ בלבד ברכישת דירה ששוויה עד 1,800,000 ₪ … בכפוף לקבלת אישור פרטני להלוואה." / "במידה ותהיו מעוניינים ברכישת דירה שמחירה גבוה מ-1,800,000 ₪, תתבקשו להעמיד הון עצמי של 25% ממחיר הדירה." / Bridge loan for equity: "בגובה של עד 50% משווי הדירה שברשותם, בניכוי שארית המשכנתא הקיימת עליה."

### S28 — Costs of buying an apartment

- "כאשר אתם לוקחים את המשכנתא ידרוש מכם הבנק לרשום בטאבו גם הערת אזהרה המונעת מכם למכור את הדירה ללא אישור הבנק כל עוד לא פרעתם לגמרי את המשכנתא." / "תידרשו לשלם אגרה על רישום המשכון של הדירה ברשם המשכונות"
- "עמלת פתיחת תיק משכנתא בשיעור של 0.25% מסכום ההלוואה אותה אתם נוטלים ועד 360 ₪. בנוסף, כתנאי להעמדת המשכנתא ידרוש מכם הבנק לרכוש ביטוח משכנתא, הכולל ביטוח חיים וביטוח מבנה"
- "עו"ד שיאשר את ייפוי הכוח שתעניקו לבנק לבצע פעולות בשמכם בקשר לדירה."
- "הלוואת המשכנתא מחושבת עבור מחיר הדירה בלבד ואינה מתייחסת לכל העלויות הנוספות."

### S29–S33 — Refinancing, payoff, remote signing

- S29 (refinance at Mizrahi). Steps: "הגשת בקשה בדיגיטל, בסניף הקרוב אליך או בטלפון 8860* לשלוחה 4 ואז 2"; "בדיקת כדאיות מיחזור המשכנתא"; "בחירת מסלולי הלוואות משכנתא חדשות"; "בחינת תנאי הלוואת המשכנתא החדשה"; "קבלת הצעה למיחזור מהמומחים שלנו"; "לאחר קבלת ההצעה נדרשת חתימה על טפסים. לנוחותכם אנו מציעים חתימה מרחוק, וזאת לאחר שיחה עם בנקאי בה נבדקת עמידתכם בתנאים הנדרשים למיחזור באופן זה." Offer: "שירות לטיפול במסמכי משכנתא". Disclaimer: "סך כל ההלוואות המובטחת בנכס נדל"ן מסוים לא יעלה על 50% משווי הנכס".
- S30/S31 (paying off; refinancing elsewhere). S30: "אם החלטתם לבצע מיחזור בבנק אחר, הבנק שאתם עוברים אליו יבקש: מכתב כוונות; הסכמה לדרגה שנייה". Both: cheque payment requires "צ'ק" and "אסמכתה למקור הכסף (למשל: מסמך מכירה, אישור העברה, ירושה וכו’)"; after a transfer: "שמרו את אישור העברת הכספים (אסמכתה); מלאו טופס עדכון סילוק; העלו את אישור ההעברה ששמרתם"; "נשלח אליכם אישור על החזר ההלוואה ב-SMS תוך 2 ימי עסקים ממועד העברת הכספים."; "הבנק ישחרר את השעבוד על הבית תוך 30 יום ממועד הפירעון של המשכנתא." Expedited release documents: "נסח טאבו או אישור זכויות עדכני"; "דו"ח תוצאות עיון על שם כל אחד מהלווים"; "(עלות: 12 ₪ לדו"ח)"; "אנו נטפל בבקשה תוך 14 יום, אם החזרתם את כל ההלוואות שלקחתם עבור קניית הבית." S31 adds: "מכתב כוונות הוא אישור מהבנק, שאם תפרעו את כל הלוואות המשכנתא שלקחתם, השעבוד יוסר מהבית שלכם." / "תוך 3 ימי עסקים תקבלו את מכתב הכוונות למייל שלכם".
- S32 (remote signing for refinancing): "החתימה על הטפסים מתבצעת לאחר שיחה עם בנקאי. בשיחה זו מסוכמים תנאי ההלוואה, ונבדקת עמידתכם בתנאים הנדרשים למיחזור באופן זה." / "קבלת SMS מהבנקאי הכולל מועד לחתימה וקישור לטופס בודד או למספר טפסים. פתיחת הקישור מתאפשרת לאחר הזנת מספר זהות תקין" / "בטפסים בהם נדרש לצרף קובץ, כמו למשל צילום תעודת זהות: לוחצים על כפתור "צירוף קובץ"; בוחרים את הקובץ מתוך תיקיית הקבצים שבטלפון הנייד או מצלמים באמצעות המצלמה את הטופס". Forms to sign: "1. בקשה להלוואה 2. מדריך לקבלת הלוואה 3. הצהרה על נהנה 4. הודעה על אישור 5. הסכם ביטחונות 6. גילוי נאות לריבית משתנה 7. הסכם הלוואה 8. הוראת קבע 9. הוראה לביצוע מיחזור הלוואת משכנתא 10. טופס יתרות לסילוק מוקדם להלוואות הממוחזרות". "תהליך דומה מתקיים גם כשמדובר בחשבון עם מספר לווים החותמים על המסמכים."
- S33: "ה-SMS מגיע לאחר שיחה עם בנקאי בה סוכמו תנאי המיחזור." / "בחלק מהטפסים צריך לצרף קובץ" / "מקבלים מאתנו אישור שהטופס החתום התקבל בהצלחה."

### S34–S36, S48 — Porting (גרירה)

- S34 steps: "א. הגשת בקשה לקבלת הלוואה, כולל מסמכים הנוגעים ללווים ולעסקה: חוזה רכישה, חוזה מכירה, נסח רישום או אישור זכויות עדכני של הנכס הנוכחי והנרכש." (links to S35, S03, S04) "ב. בדיקת הבקשה והמסמכים על ידי הבנק; ג. אישור הבקשה - במקרים של גרירת כספי הלוואת זכאות, תנאי ההלוואה עשויים להשתנות במעבר מיישוב ליישוב…; ד. ביצוע פעולות נוספות וצירוף מסמכים נוספים על פי הצורך (כגון ביצוע שמאות על הדירה הנרכשת).; ה. חתימה על הסכם הלוואה חדש (במקרים בהם מבוצעת הלוואה נוספת לצורך הרכישה); ו. ביצוע הגרירה בפועל - שעבוד נכס חדש ושחרור הנכס הנוכחי משעבוד."
- S35 (2019 borrowers checklist): identity as S03; "שכירים: תלושי משכורת מ- 3 חודשים אחרונים + טופס 106 לשנה קודמת"; "עצמאים: שומת מס לשנת המס הקודמת ואישור רואה חשבון לשנת המס הנוכחית"; other income as S03; "דפי חשבון של 3 חודשים אחרונים מחשבון בנק מסחרי עבור כל חשבון בנק"; "דוגמה של שיק מחשבון הבנק ממנו תיפרע ההלוואה באמצעות הרשאה לחיוב חשבון שייתן הלווה לבנק"; "טופס בקשה להלוואה מלא וחתום כנדרש"; "תעודת זכאות ללווים בעלי זכאות".
- S36: "במקרים בהם ניתנת משכנתא מכספי הבנק, הדירה החדשה תשועבד במקום הדירה הישנה, בהתאם לשיקולי האשראי ולקריטריונים המקובלים בבנק."
- S48: "גרירת משכנתא משולה באופן הביצוע ללקיחת משכנתא "רגילה" וכוללת הגשת בקשה ראשונית להלוואה, המצאת המסמכים הנדרשים, בחינת הבקשה על ידי הבנק וחתימה על הסכם משכנתא חדש מול הבנק."

### S37–S38 — Second-degree lien and lien deletion

- S37: "יש לקבל את אישור הבנק לרישום משכנתא בדרגה שנייה או בדרגה שווה לטוב גוף מממן נוסף, כאשר המשכנתא הקיימת עדיין לא נפרעה במלואה. האישור יינתן בכפוף לשיקול דעת הבנק." / "יש לשלוח את הטופס בצירוף המסמכים הנדרשים המצוינים בו למרכז המשכנתאות במייל hn@umtb.co.il."
- S38: "ואם הנכסים ששועבדו נמצאים בחזקתו, יעמידם לרשות הלקוח או הממשכן תוך שבועיים מיום הפרעון. היה השעבוד משכנתה או משכון רשום, הבנק יגיש, תוך 30 ימים מיום הפרעון, הודעה על מחיקת השעבודים למרמים [sic] הרלבנטיים." / "היה ומדובר בגרירת השעבוד לנכס אחר, הבנק יאפשר מחיקה של השעבוד הקיים."

### S39, S41 — Reform and refinance FAQ

- S39: "הרפורמה במשכנתאות מחייבת את כל הבנקים לאפשר לכם לעשות את התהליך באופן מקוון: לבקש משכנתא בדיגיטל, באמצעות המחשב או הטלפון הנייד, לצרף את המסמכים הדרושים ולהמתין לתשובה מהבנקאי." / "מזרחי-טפחות הוא הבנק היחיד בישראל שיש לו אפליקציה ייעודית למשכנתאות - טפחות טאצ' - שמאפשרת לכם להגיש בקשה, לסרוק מסמכים ולהעלות אותם…" / "מאז כניסת הרפורמה לתוקף, הבנק נותן אישור עקרוני למשכנתא תוך 5 ימי עסקים (למעט מקרים חריגים)." / Pre-approval contents: "ריבית כוללת חזויה"; "סך התשלומים בכל תקופה"; "התשלום הכי גבוה". / "כל הבנקים מחויבים להציע לכם 3 תמהילים (סלי משכנתא) אחידים". / "הביטחונות כמקובל בנוהלי הבנק."
- S41: "כל בקשה למיחזור הלוואה קיימת נבחנת לפי הקריטריונים של הבנק ובכפוף להוראת בנק ישראל."

### S42–S43, S58 — Any-purpose loan and Tefahot card

- S42: "אם יש לכם כבר משכנתא אצלנו, באפשרותכם לקבל הלוואה לכל מטרה … כנגד שעבוד הדירה." / "אנו מציעים הלוואה החל מ-40,000 ₪ לתקופה של 4 עד 30 שנים." / "על פי הנחיית בנק ישראל, סך כל ההלוואות הוא עד 70% משווי הנכס המשועבד." / "כל בקשת אשראי שתוגש לבנק תיבחן באופן פרטני…" / Green track: "בגובה של 10,000 עד 60,000 ₪ לתקופה של עד 30 שנה … את ההלוואה ניתן לקבל בחתימה מרחוק במסרון או במייל" / Disclaimer: "סך כל ההלוואות המובטחות בנדל"ן מסוים לא יעלה על 70% משווי הנכס."
- S43: "עד 120,000 ₪ מסגרת אשראי"; "עד 360 תשלומים"; "חתימה מרחוק במסרון או במייל על מסגרת האשראי"; disclaimer: "על פי הנחיית בנק ישראל, בתקופת משבר הקורונה ניתנה הקלה לפיה סך ההלוואות הוא עד 70% משווי הנכס המשועבד, ולא 50% כמו בימי שגרה."
- S58 is a foreign-currency-linked mortgage ("משכנתא צמודה לשער היציג של הדולר או האירו"), relevant only as a product type ("לרכישת נכס, מקרקעין או כל מטרה").

### S44–S46 — Bank-provided verification tools (relevant to automated checks)

- S44: "יש לך כתב ערבות? בתהליך קצר ומהיר נסייע לך לאתר את הערבות ולוודא שפרטיה נכונים" / "אפשר לאתר ערבויות מסוג חוק מכר בלבד" / "יש למלא את סכום הערבות המדויק כולל אגורות" / input fields "מספר ערבות", "סכום ערבות" / "אם ברצונך לאשר את תקינות ותוקף החתימה הדיגיטלית המופיעה בערבות, אפשר לעשות זאת באתר COMSIGN".
- S45: "ערבות דיגיטלית היא ערבות החתומה באמצעות חתימה דיגיטלית מאושרת. מדובר בחתימה מאובטחת שנתמכת על ידי קומסיין ומוסמכת לאשר את זהות החותם בבנק ולהנפיק אישור שהחתימה תקינה ושלא בוצעו שינויים במסמך." / "מסמך הערבות הדיגיטלית נשלח לקבלן ולאחר מכן בהתאמה לרוכשים." / "בערבות שאייקון המסמך לא קיים, המשמעות היא שהערבות הונפקה באופן ידני ונשלחה לסניף למסירה".
- S46: "כאן ניתן לאשר ולאמת את פרטי הפרויקט - מספר חשבון ושם הפרויקט - המופיעים בשוברי התשלום." / "לאחר הזנת פרטי החשבון לתשלום, המערכת תציג לכם את שם פרויקט הבנייה."

### S47 — Parents' help

- "משכנתא לדירה ראשונה ניתנת בשיעור מימון של עד 75%" / "במקרים שבהם הילדים זקוקים להגדלת מסגרת המשכנתא (ולא להשתתפות בהלוואה). במצב כזה, לרוב תספיק ערבות ההורים (כערבים תומכים)." / "ההורים יכולים לשעבד את הדירה שלהם ולקבל הלוואה כנגד הדירה…"

### S49–S50 — English pages

- S49: "You are entitled to up to 75% LTV (loan to value) instead of 50% as a foreign citizen." / "Homebuyers with no other properties in Israel can get up to 75% finance rate for their first purchase. However, in a case of housing improvements the maximum finance possible is 70% and if you already have an apartment in Israel, the maximum finance rate will be 50%." / "All homebuyers must provide a proof of a monthly income (generated in Israel or abroad, including investment income etc.) as a threshold requirement for a mortgage." / "the bank of Israel limits the debt to income ratio to 40%" / Process: "The first occurs before signing the purchase contract and includes applying for an approval in principle for your application by presenting all relevant income documentation." "After signing the contract, you will proceed to step two, signing all mortgage and collateral documents to place a deed." "Once the mortgage file has been checked and fully completed the funds will be wired." / "We strongly recommend signing the purchase contract only after receiving final approval" / "The bank is legally obligated to check the origins of your funds and monthly income. Make sure you have all relevant documentation." / "If you plan on wiring funds from abroad for the purchase, make sure to do that before signing the sale contract." / "Life insurance is a preliminary requirement for approval of your mortgage."
- S50: "Up to 50% of the property value" / "The amount of the mortgage together with the extra credit limit may not exceed 50% of the value of the property."

### S51, S54 — Mortgage hub and advisers

- S51: "אצלנו מגישים בקשה בדרך שהכי נוחה לכם - ומקבלים אישור עקרוני מהיר לסכום הדרוש"; "ריכזנו עבורכם את רשימת המסמכים הנחוצים להגשת הבקשה לקבלת משכנתא"; "קבלת משכנתא כרוכה גם בהנפקת פוליסת ביטוח משכנתא, הכוללת ביטוח חיים וביטוח מבנה"; "מעקב אחר בקשת המשכנתא שהגשתם באפליקציית טפחות טאצ'".
- S54: "מגישים עבור הלקוחות בקשה בטופס דיגיטלי ומקבלים אישור עקרוני מהיר בלי להגיע לסניף".

### S52 — Pension-mortgage guide (form 488, 05.2026) — product-specific

- p.4, step 4: "הבנק יבחן את הבקשה, את המידע ואת המסמכים ויחליט אם הוא מוכן לאשר את ההלוואה, באיזה סכום ובאלו תנאים. לתשומת ליבכם, תוקף האישור העקרוני הינו למשך 45 ימים. ככל שבמהלך תקופה זו לא תבוצע ההלוואה, יידרש אישור ההלוואה מחדש." — *Preliminary approval valid for 45 days; if the loan is not executed in that period, re-approval is required.* Applies to the pension (reverse) mortgage guide only.
- p.4, step 3: "ייתכן שתידרשו להעביר מסמכים נוספים גם לאחר האישור העקרוני של ההלוואה."

### S53 — Digital application (`TofesMashkantaClient`)

- The fetched skeleton exposes these route names: "user-details", "loan-details", "property-details", "borrowers-details", "liabilities", "financing-sources", "summarize". A WebSearch snippet of the same official URL shows: "מגישים בקשה למשכנתא ומקבלים אישור עקרוני מטפחות" and "פרטים אישיים — מצב תעסוקתי, הכנסות, הלוואות והתחייבויות אחרות, הון עצמי ועוד". No document-upload step is visible in what could be retrieved.

### S55 — Older Form 3801 (05.19), still live

- "בצירוף אחד מהמסמכים הבאים" (vs current "לפחות אחד"), "בפקס 03-5656621 או בדוא"ל לכתובת stf@umtb.co.il" (vs current bithonot@umtb.co.il / 03-5686982); no parcellation, warning-note-extract or copy-count clauses.

### S56–S57 — Renovation and kibbutz

- S56: "הלוואת "שפץ נא" של מזרחי-טפחות מאפשרת לכם לממן את השיפוץ…" — no document list.
- S57: "משכנתא לדיור באמצעות ערבות קמ"ע"; "מתן הלוואה לדיור באמצעות ערבות קמ"ע בסכום של עד 1,000,000 ₪."; "תוקף ההטבות למבצעי ההלוואות עד 31.12.2022." (stale page).

---

## (C) Consolidated document checklist

Stage labels: **APP** = with the application, for underwriting and preliminary approval; **PRE-APPR (preferred)** = the source says preferably before preliminary approval; **POST-APPR** = the source says after approval / for loan execution; **SIGN** = signing meeting; **LIEN** = collateral registration; **PRE-DISB** = before funds are transferred; **SERV** = after disbursement. "(inferred)" means the stage is my classification.

### C.1 Identity and representation

| # | Document (HE / EN) | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 1 | תעודת זהות בתוקף / valid Israeli ID | Every Israeli borrower; guarantors | APP (inferred) | "תעודות זהות בתוקף לאזרח ישראלי" | S02; S07 p.16 "תעודות זהות."; S03 "תעודות זהות לאזרח ישראלי" |
| 2 | דרכון + מסמך מזהה נוסף / passport + second photo ID | Foreign citizen (borrower or guarantor) | APP (inferred) | "דרכון ומסמך מזהה נוסף בתוקף הנושא תמונה ופרטי זיהוי לאזרח זר" | S02; S07 p.16 "בעלי אזרחות זרה – דרכון ומסמך מזהה נוסף הנושא תמונה ופרטי זיהוי;"; S03 |
| 3 | כתב מינוי נציג בארץ / appointment of an Israeli representative | Borrowers permanently living abroad | "לאישור הלוואה וביצועה" | "לווים המתגוררים בחו"ל דרך קבע – יחתמו על כתב מינוי נציג בארץ;" | S07 p.16 |
| 4 | ייפוי כוח מקובל על הבנק / power of attorney acceptable to the bank | Loan executed through an attorney-in-fact | POST-APPR | "מי שמבצע את ההלוואה באמצעות מיופה כח – יחתום על יפוי כח המקובל על הבנק ובהתאם לחוק;" | S07 p.17 |
| 5 | צילום תעודת זהות (קובץ מצורף) / ID photo upload | Remote-signing forms that require a file | SIGN (refinance) | "בטפסים בהם נדרש לצרף קובץ, כמו למשל צילום תעודת זהות" | S32 |

### C.2 Income from work

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 6 | תלושי משכורת 3 חודשים / last 3 payslips | Salaried (borrower and guarantor) | APP | "שכירים: תלושי משכורת מ-3 חודשים אחרונים + טופס 106 לשנה קודמת" | S02; S05 "אם אתם שכירים - 3 תלושי שכר אחרונים"; S07 p.16 "לשכירים –תלושי משכורת מ– 3 חודשים האחרונים."; S03 (without Form 106) |
| 7 | טופס 106 לשנה קודמת / Form 106, previous year | Salaried borrower | APP | (same quote as #6) | S02, S35 only (absent from S03, S05, S07) |
| 8 | שומת מס לשנה קודמת / tax assessment, previous year | Self-employed | APP | "עצמאים: שומת מס לשנת המס הקודמת ואישור רואה חשבון לשנת המס הנוכחית" | S02; S05 "+ שומת מס לשנה הקודמת"; S07 "שומת מס אחרונה ו/או אישור רו"ח"; S03 "ו/או" |
| 9 | אישור רו"ח (או יועץ מס) / CPA (or tax advisor) income certificate | Self-employed | APP | "אם אתם עצמאים - אישור רו"ח או יועץ מס על ההכנסה שלכם בשנה האחרונה + שומת מס לשנה הקודמת" | S05; S02 "אישור רואה חשבון לשנת המס הנוכחית" |
| 10 | Both salaried + self-employed sets | Salaried **and** self-employed | APP | "אם אתם שכירים ועצמאים - את כל המפורט בשני הסעיפים הקודמים" | S05 |
| 11 | תלושים + דו"חות כספיים מבוקרים + מאזן בוחן / payslips + audited statements + trial balance | Salaried controlling shareholder in a Ltd. | APP | "אם אתם שכירים בעלי שליטה בחברה בע"מ - 3 תלושי שכר אחרונים + דו"חות כספיים מבוקרים של השנה הקודמת + מאזן בוחן לשנה השוטפת" | S05 |
| 12 | שומת מס אחרונה מאושרת + אישור רו"ח (טופס 3806) / latest tax assessment + CPA Form 3806 for previous and current year | Shareholder in a Ltd. drawing dividends | APP | "בעל מניות בחברה בע"מ המושך דיבידנד: שומת מס אחרונה מאושרת; אישור רו"ח עבור בעל שליטה בחברה בע"מ (טופס 3806) עבור השנה הקודמת והשנה השוטפת" | S02 |
| 13 | שומה + 3806 + דוח מבוקר עדכני + מאזן בוחן / assessment + Form 3806 + current audited report + trial balance | Shareholder in private company (100% owner or controlling-shareholder employee) | APP | "שומת מס אחרונה מאושרת; אישור רו"ח חשבון עבור בעל שליטה בחברה בע"מ (טופס 3806) עבור התקופה שבה לא הוצגה שומת מס; דוח מבוקר עדכני; מאזן בוחן לשנה השוטפת ולתקופה שבה לא הוצג דו"ח מבוקר" | S02 |
| 14 | אישור לימודים בכולל / kollel study confirmation | Kollel student (אברך) | APP | "אברך: אישור לימודים בכולל" | S02 |
| 15 | Proof of monthly income | All homebuyers (English page) | APP | "All homebuyers must provide a proof of a monthly income (generated in Israel or abroad, including investment income etc.)" | S49 |

### C.3 Other income

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 16 | הסכם גירושין / divorce agreement | Alimony income | APP | "דמי מזונות (הסכם גירושין)" | S02, S03; S07 "דמי מזונות – הסכם גרושין" |
| 17 | חוזה שכירות תקף + אישור זכויות/נסח של הנכס המושכר / valid lease + rights confirmation or extract of the rented property | Rental income | APP | "שכר דירה (חוזה שכירות תקף) ואישור זכויות או נסח טאבו של הנכס המושכר" | S02 (S03, S35: lease only) |
| 18 | אישור מהגורם המממן / payer confirmation | Child/old-age/survivors/disability allowance | APP | "קצבאות (ילדים, זקנה, שאירים, נכות) – אישור מהגורם המממן" | S02, S03; S07 "קיצבת נכות – אישור רשמי מהגוף המממן" |

### C.4 Bank, credit and payment set-up

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 19 | דפי חשבון עו"ש 3 חודשים / 3 months of statements, every account | All borrowers | APP | "דפי חשבון עובר ושב מ-3 החודשים האחרונים, עבור כל חשבון בנק" | S02; S05 "דפי תנועות בחשבון הבנק מ-3 החודשים האחרונים (עבור כל חשבונות הבנק שלכם)"; S07 "דפי חשבון של 3 חודשים האחרונים מחשבון הבנק המסחרי, עבור כל חשבון בנק;" |
| 20 | דוח ריכוז יתרות הלוואה / consolidated loan-balances report | Borrowers with loans | APP | "דו"ח ריכוז יתרות של הלוואות (אם ישנן) מכל חשבונות הבנק" | S05; S02 "דוח ריכוז יתרות הלוואה" |
| 21 | צ'ק לדוגמה / sample cheque | Account from which the loan will be paid | APP | "צ׳ק לדוגמה מחשבון העו"ש ממנו תשולם ההלוואה" | S02; S07 "דוגמה של שיק מחשבון הבנק ממנו תיפרע ההלוואה…" |
| 22 | אסמכתאות על ביטול עיקולים/פיגורים / proof that attachments or arrears were cancelled | Only if BoI credit data shows them | UW (inferred) | "אם יופיע מידע לגבי עיקולים או פיגורים, תידרשו להציג אסמכתאות מהגורמים הרלוונטיים על ביטולם" | S05 |
| 23 | הרשאה לחיוב חשבון חתומה ע"י הבנק המסחרי / standing-order authorization signed by the commercial bank | All loans | SIGN | "יש להעביר לבנקאי הרשאה חתומה על ידי הבנק שבו מתנהל חשבון העובר ושב שלכם" | S05; S07 §3ה–ו; S03 "הוראת קבע מבנק מסחרי…"; S06 "חתימה מול הבנקאי" |
| 24 | Source-of-funds documentation (unspecified) | All (English page) | APP (inferred) | "The bank is legally obligated to check the origins of your funds and monthly income. Make sure you have all relevant documentation." | S49 |

### C.5 Application, declarations, fees

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 25 | טופס בקשה להלוואה / loan application form | All | APP | "טופס בקשה להלוואה מלא וחתום כנדרש" | S02; S07 "טופס בקשה להלוואה ממולא וחתום כנדרש;" |
| 26 | תעודת זכאות תקפה / valid eligibility certificate | Eligible borrowers (directed loan) | APP | "זכאות - המצאת תעודת זכאות תקפה" | S05; S02 "תעודת זכאות ממשרד השיכון לזכאים"; S07 "לווים בעלי זכאות להלוואה מוכוונת – תעודת זכאות." |
| 27 | תצהיר דירה יחידה/חליפית / sole or replacement apartment affidavit (each borrower, lawyer-verified) | LTV > 50% | SIGN (inferred) | "על כל אחד מכם לחתום על טופס נפרד, לדאוג שעורך דין יאמת את החתימה, ולאחר מכן להחזיר לבנקאי. (רלוונטי במשכנתא בשיעור מימון העולה על 50%)" | S05 |
| 28 | עמלת פתיחת תיק / file-opening fee payment | All | SIGN (inferred) | "זו עמלה קבועה בכל הבנקים … שעומדת כיום על 360 ₪" | S05; S28 "0.25% … ועד 360 ₪" |
| 29 | מדריך לקבלת הלוואה (חתום) / signed acknowledgment of the loan guide | Received via remote banking; listed among refinance forms | SIGN | "לאישור בעת קבלת מסמכים באמצעי בנקאות בתקשורת בלבד - הרינו מאשרים קבלת המסמך:" | S07 p.20; S32 item 2 |

### C.6 Eligibility-certificate application (Ministry of Housing)

| # | Document | Condition | Exact quote | Source |
|---|---|---|---|---|
| 30 | ת.ז. כולל ספח / ID with appendix | Applicants | "תעודת זהות של הלווים כולל ספח" | S24; S07 "תעודת זהות של המבקשים;" |
| 31 | ת.ז. של הורה או תצהיר אחים / parent's ID or siblings affidavit | Applicants | "תעודת זהות של אחד מהורי כל אחד מהמבקשים (כולל ספח), או תצהיר הכולל את פרטי האחים והאחיות של המבקשים" | S24; S07 "תעודת זהות של הורי המבקשים בה רשומים האחים והאחיות שלהם (שכתובתם הקבועה בארץ), או תצהיר הכולל את פרטיהם (ניתן לקבל את נוסח התצהיר בבנק);" |
| 32 | אישור שירות / service confirmation | Military / national / civil service | "שירות בצה"ל: אישור על מהלך שירות צבאי. ניתן להנפיק באתר צה"ל." | S24; S07 "אישור מקצין העיר על שירות צבאי (הכולל את משך השירות), או אישור על שירות לאומי (מהגוף במסגרתו בוצע השירות);" |
| 33 | אישור שירות מילואים שש שנתי / 6-year reserve-duty confirmation | Reserve service | "שירות מילואים: אישור מסוג "אישור שירות מילואים שש שנתי"." | S24 |
| 34 | מסמכי מצב אישי / personal-status documents | Married / divorced etc. | "מסמכים המעידים על מצב אישי (תעודת נישואין, תעודת גירושין וכדומה)" | S24; S07 "תעודת נישואין (לזוגות נשואים);" and "זוג הנשוי בנישואין אזרחיים – אישור ממשרד הפנים על הכרה בנישואין ותאריך הנישואין;" |
| 35 | אישור רבנות על הרשמה לנישואין / rabbinate registration | Couples about to marry | "אישור מהרבנות על הרשמה לנישואין (לזוגות העומדים להינשא)" | S24, S07 |
| 36 | אישור רופא על היריון / pregnancy confirmation | Pregnant applicant (threshold conflicts, F.3) | "מבקשת משכנתא הנמצאת בהריון (משבוע 24 ואילך) – אישור מרופא על ההיריון" | S24; S07 "(מחודש חמישי ואילך) – אישור עדכני של רופא ממוסד רפואי מוכר." |
| 37 | תעודת עולה / immigrant certificate | New immigrant | "תעודת עולה (אם אחד מהמבקשים הוא עולה חדש, גם אם אינה בתוקף)" | S24; S07 |

### C.7 Property documents

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 38 | נסח רישום / אישור זכויות ושעבודים / registry extract or rights-and-liens confirmation | All; type depends on registration | PRE-APPR (preferred) | "נסח רישום או אישור זכויות ושעבודים (בהתאם למקום הרישום של הנכס);" under "רצוי, אך אין חובה, להמציא מסמכים אלה לפני אישור עקרוני להלוואה" | S07 p.16; S03; S06 "נסח רישום מקורי / אישור זכויות מקורי … לווה אחד יכול להציגו לבנק"; S01 (Tabu extract by email) |
| 39 | הסכם רכישה / purchase agreement | Property not registered in borrower's/pledgor's name | PRE-APPR (preferred) | "הסכם רכישה של הנכס (אם הנכס אינו רשום ע"ש הלווה או המשעבד)." | S07; S03; S06 "יש להעביר חוזה רכישה חתום מהקבלן" |
| 40 | חוזה רכישה חתום כחוק + ת.ז. וחשבון בנק של המוכר + אימות חשבון / legally signed contract + seller ID + seller bank account + account proof | Loans for purchasing an apartment | POST-APPR | "בהלוואות לרכישת דירה – חוזה רכישת הדירה חתום כחוק וכן צילום תעודת הזהות ומספר חשבון הבנק של מוכר הדירה בצירוף מסמך לאימות פרטי החשבון (שיק, אישור מהבנק וכד');" | S07 p.16; S03 |
| 41 | חוזה רכישה, חוזה מכירה, נסחים של שני הנכסים / purchase + sale contracts, extracts of current and new property | Porting | APP | "חוזה רכישה, חוזה מכירה, נסח רישום או אישור זכויות עדכני של הנכס הנוכחי והנרכש" | S34 |
| 42 | הסכם שכירות / lease agreement | Apartment being bought is rented | PRE-DISB (inferred) | "אם הדירה מושכרת יש לצרף את הסכם השכירות שנחתם עם השוכרים" | S05 |
| 43 | היתר בנייה + אישור מהנדס / building permit + engineer's stage confirmation | Construction-financing loans | POST-APPR | "בהלוואות למימון בנייה – היתר בנייה ואישור מהנדס על שלב הבנייה (אם הבנק דורש זאת);" | S07 p.16; S03 (no "אם הבנק דורש זאת") |
| 44 | אישורים מיוחדים / special approvals per Ministry of Housing | Directed loans under certain programmes | POST-APPR | "בהלוואות מוכוונות לפי תוכניות ממשלתיות מסוימות – אישורים מיוחדים בהתאם להנחיות משרד הבינוי והשיכון;" | S07; S03 |

### C.8 Appraisal

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 45 | הערכת שמאי (שמאי מתוך רשימת 3 של הבנק) / appraisal by one of 3 bank-listed appraisers, sent directly to the bank | Second-hand: "בכל בקשה"; contractor: "במקרים מסוימים"; guide: "אם הבנק דורש זאת" | POST-APPR | "תקבלו מהבנקאי טופס אשר כולל רשימה של 3 שמאים … לאחר ביצוע ההערכה, השמאי יעביר ישירות לבנק את הערכת השווי (השמאות)." | S05; S06; S07 p.16 "הערכת שמאי … ערוכה ע"י שמאי מוסמך אליו תופנו על ידי הבנק (אם הבנק דורש זאת);"; S03 "מסמכים ופעולות לאחר אישור ההלוואה" |
| 46 | שמאות מבנק אחר (≤90 יום) / another bank's appraisal, at most 90 days old | "בתנאים מסויימים" | POST-APPR | "ובתנאי שלא חלפו יותר מ– 90 יום ממועד ההערכה ושהשמאות תופנה לבנק לצורך ביצוע ההלוואה;" | S07 p.16 |

### C.9 Insurance

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 47 | פוליסת ביטוח חיים / life policy per borrower | Every borrower fit to be insured; not required if balance ≤ ₪30,000, grant/standing loans, age > 70, or Tefahot card loan | POST-APPR / before execution | "פוליסה עבור כל אחד מהלווים בגובה סכום המשכנתא ולכל תקופתה. הבנק צריך להיות מוטב בלתי חוזר בפוליסה, והפוליסה צריכה להיות משועבדת לבנק מזרחי-טפחות. חשוב לשים לב, כי מספר הסניף וכתובת הסניף רשומים בפוליסה" | S05; S07 pp.11–12; S20 |
| 48 | הצהרת בריאות / health declaration (with life policy) | Life insurance | POST-APPR | "פוליסת ביטוח נכס ופוליסת ביטוח חיים כולל הצהרת בריאות;" | S07 p.16 |
| 49 | פוליסת ביטוח נכס / property policy | Every pledged property; exemptions in S07 p.11 | POST-APPR / before execution | "פוליסה בגובה ערך הכינון … א. סעיף שעבוד לטובת בנק מזרחי-טפחות (כולל מספר הסניף וכתובת סניף) ב. רישום הבנק כמוטב בלתי חוזר ג. התחייבות להודעה מוקדמת במקרה של ביטול הפוליסה (30 יום מראש)" | S05; S07 p.10 adds "סעיף רעידת אדמה" |
| 50 | התחייבות להמציא פוליסת נכס / undertaking to provide a property policy later | Property whose construction is not complete | POST-APPR | "לגבי נכס שבנייתו לא הושלמה, תדרשו להתחייב להמציא פוליסת ביטוח נכס בעתיד לכשתושלם הבנייה." | S06; S07 p.10 (obligation only from contractor's delivery date) |
| 51 | ביטוח אשראי (EMI) / credit insurance | "במקרים מסויימים" | before execution | "במקרים מסויימים יתנה הבנק את ביצוע ההלוואה בביטוח האשראי (על ידי חברת EMI)." | S07 p.12 |
| 52 | עותק פוליסה חיצונית / copy of an external policy | Policy not bought via the bank's agency | before execution | "יש להמציא לבנק עותק של הפוליסה העונה על דרישות הבנק, בתנאים המפורטים בהסכם ההלוואה." | S20 |
| 53 | פוליסה + ביטולי פוליסה (חידוש) / policy document + cancellations (renewal) | Replacing a policy on an existing mortgage | SERV | "את מסמך הפוליסה בלבד - חיים ונכס"; "ביטולי פוליסה"; "לשלוח כל פוליסה במייל נפרד, כקובץ pdf ללא תמונות." | S21, S22 |
| 54 | טופס פטור 2812 / 2818 / insurance exemption request | Meets a listed exemption reason; guarantors countersign | SERV / before execution (inferred) | "לקבלת הפטור יש לציין את פרטי הנכס ולבחור את הסיבה לבקשת הפטור מתוך הסיבות המצוינות בטופס." | S08, S11, S12 |

### C.10 Collateral and lien registration

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 55 | רישום משכנתא בטאבו / mortgage registration in Tabu | Property registered in Tabu in pledgor's name | LIEN | "רישום משכנתא לטובת הבנק בטאבו" | S04; S07 p.17 |
| 56 | טופס שיעבוד דירתי / residential-lien acknowledgment form | All registration types | SIGN/LIEN | "טופס שיעבוד דירתי חתום בידי הלווה/ משעבד אחר" | S04; S06 "טופס עליו חותמים הלווים בפני הבנקאי" |
| 57 | שטר משכון / pledge deed | ILA/housing company; second-hand; first-hand from housing company | SIGN/LIEN | "שטר משכון חתום בידי הלווה/ משעבד אחר" | S04; S06 "נחתם על-ידי כל הלווים והמשעבדים מול הבנקאי" |
| 58 | הודעת משכון + אישור רישום / pledge notice + registration confirmation | Same types as #57 | LIEN | "הודעת משכון חתומה בידי הלווה/ משעבד אחר ואישור על רישומה ברשם המשכונות" | S04; S05 (online at branch, ₪175); S06 |
| 59 | דו"ח עיון לכל לווה / inspection report per borrower/pledgor | After pledge registration | LIEN | "לאחר רישום המשכון, יש להפיק דו"ח עיון מרשם המשכונות לכל אחד ממבקשי המשכנתא" | S05 (upload via Touch or email, ₪11); S06 "על שם הלווים והמשעבדים" |
| 60 | ייפוי כוח בלתי חוזר נוטריוני / irrevocable notarized POA (original) | All except Tabu-registered-in-pledgor's-name | SIGN/LIEN | "יש להחזיר לבנקאי את הטופס המקורי, חתום ומאומת על-ידי נוטריון" | S05; S04 "ייפוי כוח בלתי חוזר מאושר על ידי נוטריון"; S06 |
| 61 | התחייבות לרישום משכנתא / undertaking to register a mortgage | ILA/housing company; seller; contractor + registered landowners | LIEN | "התחייבות לרישום משכנתא חתומה בידי המוכר" / "…חתומה בידי הקבלן ובידי הבעלים הרשומים של המקרקעין" / "…של המינהל או של החברה המשכנת" | S04; S07 p.17; S05 "התחייבות" (all sellers, lawyer-verified original); S06 (contractor before a lawyer) |
| 62 | הערות אזהרה / warning notes for buyers (purchase agreement) and bank (seller's undertaking) | Second-hand, registered in Tabu in seller's name | LIEN | "רישום הערות אזהרה לגבי הנכס: לטובת הלווים - בגין הסכם הרכישה; לטובת הבנק - בגין התחייבות לרישום משכנתא של המוכר" | S04; S07 p.17 |
| 63 | טופס בקשה לרישום הערת אזהרה + נסח אחרי רישום + אישור רישום / warning-note form + post-registration extract + registration confirmation | Second-hand (S05 process) | LIEN | "נסח טאבו לאחר הרישום. חשוב - לוודא כי נרשמה הערת אזהרה גם לטובתכם" and "אישור על ביצוע הרישום" | S05 |
| 64 | הערת אזהרה לטובת הבנק בגין התחייבויות הקבלן / bank warning note re contractor undertakings | First-hand from housing company | LIEN | "רישום הערת אזהרה לטובת הבנק בגין ההתחייבויות הנ"ל" | S04; S07 |
| 65 | ערבות חוק מכר מוסבת לבנק / Sale Law guarantee endorsed to the bank (or other statutory security) | New apartment | LIEN / POST-APPR | "ערבות של רוכשי דירות לפי "חוק המכר (דירות) … התשל"ה - 1974", המוסבת לבנק או בטוחה אחרת לפי אותו חוק" | S04; S07 p.16 "(במקרה של רכישת דירה חדשה – אם הבנק דורש זאת)"; S06 "הסבת ערבות, התחייבות להמצאת ערבות ומכתב החרגה" |
| 66 | פנקס שוברי תשלום / payment-voucher book | Contractor project accompanied by a bank under an agreement signed after 1.6.2008 | DISB | "פנקס שוברי התשלום שהונפק על ידי הבנק המלווה (בהלוואות לרכישת דירה מקבלן בפרויקט המלווה על ידי תאגיד בנקאי על פי הסכם ליווי שנחתם לאחר 1.6.2008)" | S04; S07 p.17; S06 "בכל ביצוע של תשלום יש להביא שובר" |
| 67 | Form 3801 + attachments for mortgage deed | Producing a mortgage deed for Tabu registration | LIEN / SERV | "בצירוף לפחות אחד מהמסמכים הבאים … העתק נסח רישום מקרקעין (טאבו) מעודכן; העתק שטר מכר; העתק שטר שכירות; העתק "דרישה לרישום זכויות בלשכת רישום המקרקעין"" + parcellation approval if details changed + extract showing the bank's warning note if one exists | S09 |

### C.11 Seller-side documents (second-hand purchase)

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 68 | אישורי מיסים / tax approvals | All second-hand deals | PRE-DISB (last tranche) | "העתק דיווח העסקה לשלטונות המס (מש"ח) + אישור דיווח דיגיטלי"; "אישור תשלום מס רכישה"; "אישור תשלום מס שבח (או אישור על הפקדת הסכום לתשלום מס השבח בנאמנות עורך דין)"; "אישור עירייה עדכני על היעדר חובות של בעל הנכס מול העירייה" | S05; S06 (contractor: purchase tax via the lawyer) |
| 69 | אישור על תשלום הון עצמי / sellers' equity-received confirmation or proof of payment | All second-hand deals | PRE-DISB (inferred) | "יש להחתים את המוכרים על טופס ששמו "אישור על תשלום הון עצמי" … או לצרף אסמכתה (צילום צ'ק או אישור על ביצוע העברה בנקאית)" | S05; S06 (contractor confirmation via vouchers) |
| 70 | טופס "תשלום על חשבון ההלוואה" + אסמכתה לכל חשבון / disbursement-instruction form + proof for each account | All second-hand deals | PRE-DISB | "את הטופס המקורי, החתום על ידי המוכרים והקונים ומאומת על ידי עורך דין, יש להחזיר לבנקאי." / "יש לצרף אסמכתה לכל חשבון בנק אליו מבקשים להעביר את הכספים" | S05 |
| 71 | אישורי מס לפי החוזה או פרטי חשבון נאמנות + אסמכתה / contract tax approvals or trust-account details + proof | Before last mortgage tranche | PRE-DISB | "הבנק יעביר את הסכום האחרון של כספי המשכנתא רק לאחר קבלת אישורי המיסים עבור הנכס … או לאחר שיופקד בנאמנות עורך דין לחשבון נאמנות ספציפי." | S05 |
| 72 | מכתב כוונות מבנק המוכר / letter of intent from seller's mortgage bank | Seller is paying a mortgage | PRE-DISB | "אם המוכרים משלמים משכנתא, יש לצרף מכתב כוונות מהבנק בו מתנהלת המשכנתא שלהם" | S05 |
| 73 | אישור הסרת שעבודים / מכתב כוונות / אישור פרי פסו / lien-removal approval, letter of intent, or pari-passu approval | Property pledged to another party | POST-APPR / PRE-DISB | "אם הנכס משועבד לטובת גורם אחר (למשל בנק אחר), יש להעביר לבנקאי אישור על הסרת השעבודים או מכתב כוונות מהגורם המשעבד" | S05; S07 p.16 "אישור שחרור השעבוד, אישור סילוק ההלוואה או אישור פרי פסו, הכל כפי שהבנק ידרוש;"; S03 |
| 74 | צילום ת.ז. המוכרים כולל ספח / sellers' ID incl. appendix | All second-hand deals | PRE-DISB (inferred) | "יש לצרף צילום תעודת זהות, כולל הספח המעיד על המצב המשפחתי של המוכרים" | S05 |
| 75 | "החתמת בן זוג של המוכר" / seller's spouse consent | Seller's spouse not listed as a seller | PRE-DISB (inferred) | "אם למוכר/ת יש בן או בת זוג שאינם מופיעים כמוכר בחוזה, נדרש לקבל את הסכמתם." | S05 |
| 76 | "אישור לרישום בפנקסי המקרקעין" / approval for registration in land books | Seller is a foreign resident (identified by passport) | PRE-DISB (stated: "לפני העברת הכספים") | "נדרש להציג לסניף, לפני העברת הכספים, טופס בשם "אישור לרישום בפנקסי המקרקעין", אותו יש לבקש מעורך הדין" | S05 |

### C.12 Contractor-specific (new construction)

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 77 | חוזה רכישה חתום מהקבלן / signed contract from contractor | Contractor purchase | APP (inferred) | "יש להעביר חוזה רכישה חתום מהקבלן" — "לווה אחד יכול להציגו לבנק" | S06 |
| 78 | הסבת ערבות, התחייבות להמצאת ערבות ומכתב החרגה / guarantee endorsement, undertaking, exclusion letter | Contractor purchase | LIEN (inferred) | "מסמכים שיש להמציא מהקבלן" | S06 |
| 79 | אסמכתה לתשלום הון עצמי בשוברים / proof of equity paid by vouchers | Contractor purchase | PRE-DISB (equity first) | "יש לקבל אישור מהקבלן על ההון העצמי ששילמתם לו" — "אישור הקבלן / אסמכתה לשוברים משולמים" | S06 |

### C.13 Refinancing, payoff and servicing

| # | Document | Condition | Stage | Exact quote | Source |
|---|---|---|---|---|---|
| 80 | מכתב כוונות + הסכמה לדרגה שנייה / letter of intent + second-degree consent | Refinancing at another bank | SERV | "הבנק שאתם עוברים אליו יבקש: מכתב כוונות; הסכמה לדרגה שנייה" | S30 |
| 81 | צ'ק + אסמכתה למקור הכסף / cheque + source-of-money proof | Payoff by cheque | SERV | "אסמכתה למקור הכסף (למשל: מסמך מכירה, אישור העברה, ירושה וכו’)" | S30, S31 |
| 82 | אישור העברה + טופס עדכון סילוק / transfer confirmation + payoff-update form | Payoff by bank transfer | SERV | "שמרו את אישור העברת הכספים (אסמכתה); מלאו טופס עדכון סילוק; העלו את אישור ההעברה ששמרתם" | S30, S31; S08 |
| 83 | נסח/אישור זכויות עדכני + דו"ח תוצאות עיון לכל לווה / updated extract + inspection-results report per borrower | Expedited lien release | SERV | "נסח טאבו או אישור זכויות עדכני; דו"ח תוצאות עיון על שם כל אחד מהלווים" | S30, S31; S08 "דו"ח רישום משכון ודו"ח תוצאות עיון" |
| 84 | נסח/אישור זכויות עדכני (מומלץ) / updated extract (recommended) | Letter-of-intent request | SERV | "מומלץ לצרף לבקשה נסח טאבו עדכני או אישור זכויות עדכני." | S08 |
| 85 | Form 2813 + נסח עדכני + טופס הנושה הנוסף (+ אישורי הכנסות) / form 2813 + updated extract + other creditor's form (+ possibly income docs) | Second-degree / pari-passu lien | SERV | "נסח טאבו/אישור זכויות עדכני."; "טופס "בקשה להסכמה לפרי פסו/דרגה שניה" מהנושה הנוסף."; "ייתכן שנדרש להמציא אישורי הכנסות לצורך בחינת הבקשה." | S10, S37 |
| 86 | 10 refinance forms (remote signature) | Refinancing at Mizrahi | SIGN | "בקשה להלוואה; מדריך לקבלת הלוואה; הצהרה על נהנה; הודעה על אישור; הסכם ביטחונות; גילוי נאות לריבית משתנה; הסכם הלוואה; הוראת קבע; הוראה לביצוע מיחזור הלוואת משכנתא; טופס יתרות לסילוק מוקדם להלוואות הממוחזרות" | S32 |
| 87 | Form 2142 + death certificate + inheritance order + supporting documents | Borrower death (group life policy via bank) | SERV | "שולחים את הטופס בצירוף תעודת פטירה וצו ירושה (אם יש) וכן כל מסמך אחר התומך בתביעה" | S08, S13 |

### C.14 Explicit numeric parameters (consolidated)

| Parameter | Value | Scope | Source |
|---|---|---|---|
| Payslips | last 3 months | Salaried borrowers and guarantors | S02, S03, S05, S07 |
| Bank statements | last 3 months, every account | Borrowers | S02, S05, S07 |
| Form 106 | previous year | Salaried (S02 only) | S02 |
| Document resubmission | > 45 days since last submission → resubmit | Income/current-account documents (second-hand page) | S05 |
| Other-bank appraisal max age | 90 days from valuation | "בתנאים מסויימים" | S07 p.16 |
| Appraiser choice | list of 3 | Bank referral | S05, S06 |
| Interest-rate lock | 12 days / 24 days (rules in §8) | All loans | S07 pp.8–9 |
| Preliminary approval turnaround | within 5 business days (except exceptional cases) | Post-reform | S39 |
| Preliminary approval validity | 45 days | **Pension mortgage only** | S52 p.4 |
| Eligibility certificate validity | "לרוב שנה" from registration | Directed loans | S24 |
| Letter of intent | issued within 3 business days; valid 30 days | Payoff/refinance | S08, S31 |
| Insurance cancellation notice | 30 days | Life and property policies | S05, S07, S21 |
| Insurance threshold | required for each loan with balance > ₪30,000 (S20); exemptions at ≤ ₪30,000 (S07, S11, S12) | Life and property | S07, S11, S12, S20 |
| Life insurance age exemption | borrower age > 70 at execution | Life | S07 p.12 |
| Partial property insurance | ≥ balance − land value + up to 20% | Property | S07 p.10, S12 |
| Sole-apartment affidavit | LTV > 50% | Second-hand page | S05 |
| Pledge registration fee | ₪175 | Pledges Registrar | S05 |
| Inspection report fee | ₪11 (S05) / ₪12 (S30, S31) | Per report | conflict, F.2 |
| File-opening fee | ₪360 fixed (S05) / 0.25% up to ₪360 (S28) | | conflict, F.1 |
| Mortgage deed copies | online 1 / manual 5 | Form 3801 | S09 |
| Second-degree consent fee | ₪150 | Form 2813 | S10 |
| Lien release | within 30 days of repayment; expedited within 14 days (S30/S31) or "30 יום לאחר קבלת אסמכתה" (S08) | | conflict, F.15 |
| Payoff confirmation SMS | within 2 business days | | S30, S31 |
| Form acknowledgment SMS | ~24 hours | | S08 |
| Equity (first apartment) | 25% | | S23; S47 "עד 75%" LTV |
| Price-for-resident / discounted | ₪100,000 equity if market value ≤ ₪1.8M; else 25% | | S25, S27 |
| Any-purpose loan | from ₪40,000; 4–30 years; total ≤ 70% of value | | S42 |
| Sale Law threshold | > 7% of price requires security | New apartment | S04, S07 |
| Voucher-book regime | accompaniment agreements signed after 1.6.2008 | Contractor | S04, S07 |
| Payment days | 1, 10 or 15 of month | | S07, S08 |
| Early-repayment notice | ≥ 10 and ≤ 45 days before (S07); from day 10 for 45 days (S08); from day 10 for 35 more days (S14) | | conflict, F.14 |
| Appraisal fee ranges | ₪390–481 / ₪850–4,420 / ₪1,600–6,040 / ₪4,400–9,750 | By appraisal type | S07 p.8 |

---

## (D) Process and lifecycle map

### D.1 The bank's canonical 7-step process (S07 §3, p.6)

1. **Information and financing plan** — actor: customer. "קבלת מידע וגיבוש תוכנית מימון. תוכלו לקבל מידע על אפשרויות המימון שהבנק מציע ועל סוגי ההלוואות ותנאיהן בכל סניפי הבנק ובאתר האינטרנט של הבנק."
2. **Application** — actor: customer (guarantor details included). "הבקשה להלוואה כוללת מידע על הלווים, מטרת ההלוואה ופרטי הנכס אשר ישועבד לטובת הבנק. במסגרת הבקשה יימסרו גם פרטי הערבים להלוואה. את הבקשה ניתן להגיש בסניף הבנק, באתר האינטרנט של הבנק או בשיחה עם נציג הבנק במרכז המשכנתאות."
3. **Document submission** — actor: customer; possible branch-manager meeting. "כדי שהבנק יוכל לבחון את בקשת ההלוואה, עליכם להעביר לבנק מסמכים שונים כמפורט בהמשך מדריך זה. ייתכן שתידרשו להמציא מסמכים נוספים גם לאחר האישור העקרוני של ההלוואה. לעתים, מנהל הסניף יבקש להיפגש עמכם ואולי לקבל מכם מידע נוסף על עיסוקכם, מצבכם הכספי וכו'."
4. **Review and approval** — actor: bank. "הבנק יבחן את הבקשה, את המידע ואת המסמכים ויחליט אם הוא מוכן לתת את ההלוואה, באיזה סכום ובאלו תנאים."
5. **Signing** — actors: borrowers, guarantors, commercial bank. "אם ניתן אישור להלוואה, תחתמו אתם והערבים (אם ישנם) על הסכם ההלוואה ונספחיו, תמציאו את מסמכי הביטחונות הנדרשים ותחתמו על מסמכי הבנק, ככל שתידרשו. כמו כן תחתמו על טופס הרשאה לחיוב חשבונכם בבנק מסחרי, ותחזירו לבנק את טופס ההרשאה כשהוא חתום על ידי הבנק המסחרי"
6. **Standing order** — "בין היתר, תדרשו להמציא הרשאה לחיוב חשבונכם בבנק מסחרי כשהיא חתומה על ידכם ומאושרת ע"י הבנק המסחרי"
7. **Disbursement** — actor: bank. "לאחר שעמדתם בכל הדרישות, תבוצע ההלוואה כמוסכם. בעת ביצוע הלוואה לרכישה מקבלן, נדרש לצורך ביצוע ההלוואה, פנקס שוברי התשלום שהונפק על ידי הבנק המלווה ונמסר על ידי הקבלן. ההלוואה תבוצע רק באמצעות שובר התשלום. במקרים אחרים, בדרך כלל תבוצע העברה בנקאית לחשבון המוכר או לחשבון הקבלן או לחשבון גורם אחר, בהתאם למוסכם מראש. … במקרים אלו … יבצע את ההלוואה באמצעות המחאות לחשבונות המתאימים ומסירתן ללווים."

English summary of the same flow (S49): approval in principle **before** signing the purchase contract, with income documentation → after the contract, sign mortgage and collateral documents → "Once the mortgage file has been checked and fully completed the funds will be wired."

### D.2 Application channels and preliminary approval

- Channels: "בדיגיטל, בצ'אט, ב-WhatsApp או בטלפון" (S15); branch, website, phone (S07); digital form (S53, linked from S51/S40); Tefahot Touch (S17 "מגישים בקשה למשכנתא ומקבלים עדכון אם קיבלתם אישור עקרוני"); advisers' interface (S19, S54).
- Digital form sections (S53 route names): user-details, loan-details, property-details, borrowers-details, liabilities, financing-sources, summarize.
- Timing: "הבנק נותן אישור עקרוני למשכנתא תוך 5 ימי עסקים (למעט מקרים חריגים)." (S39)
- Nature and validity: "אישור עקרוני אינו מהווה התחייבות של הבנק להעמיד לכם את ההלוואה, אלא מגדיר את סכום המסגרת להלוואה … האישור העקרוני מוגבל בזמן" (S26). Numeric validity only in S52 (pension): 45 days. Rate-lock windows in S07 §8.
- Recommended order: get preliminary approval before committing ("שלא תגיעו לשלב בחירת הדירה לפני שיש בידכם את האישור העקרוני מהבנק" — S26; "make sure that you do not sign anything before receiving an approval in principle" — S49).

### D.3 Document collection and freshness

- Property documents preferably before preliminary approval (S07, S03).
- Additional documents may be requested after preliminary approval (S07 §3ג, S52, S05 "ייתכן שהבנקאי יבקש מסמכים נוספים.").
- Refresh rule: "אם חלפו יותר מ-45 יום מאז שהעברתם את המסמכים בפעם הקודמת … יש להעביר את המסמכים מחדש" (S05).
- Upload channels: Tefahot Touch ("מעלים מסמכים ומורידים אישורים" — S17; "לסרוק מסמכים ולהעלות אותם" — S39) or email to the banker (S05, for inspection reports and policies); Tabu extract by email (S01).
- Originals required, not copies (stated): seller undertaking, warning-note form, notarized POA, equity-payment confirmation, disbursement-instruction form ("הטופס המקורי" — S05).

### D.4 Credit check

- "הבנק פונה למערכת נתוני אשראי של בנק ישראל, כדי לבדוק את ההיסטוריה הפיננסית שלכם." (S05). Criterion: previous loans "אין, ולא היו בהן, פיגורים משמעותיים" (S07).

### D.5 Appraisal

- Actors: banker provides a form with 3 appraisers, the documents to give the appraiser, and the fee; customer chooses and pays; appraiser sends the valuation directly to the bank; customer may ask the appraiser for a copy (S05, S06, S07 §7).
- The appraiser records the reinstatement value used for property insurance (S05, S07 p.10).
- Classified by S03 under "מסמכים ופעולות לאחר אישור ההלוואה" and by S07 under "מסמכים ופעולות לצורך ביצוע ההלוואה (אם אושרה)".

### D.6 Insurance

- Customer buys life and property policies from any insurer or from Tefahot agency; recommended at the branch meeting; upload via Touch or email (S05).
- Agency policies: a summary form is given at the branch kiosk; the full policy is sent after loan execution (S07).
- Bank checks external policies against requirements (S20, S21); life uninsurability can block or cancel an approval (S07).

### D.7 Signing

- At a branch meeting, including guarantors (S05). All borrowers must sign at the bank, not necessarily together (S06). Residential-lien form, pledge deed and standing order are signed in front of the banker (S06).
- Remote signing (SMS link, finger signature, file attachments) exists for refinancing (S32, S33) and for the any-purpose loan and Tefahot card (S42, S43).

### D.8 Collateral registration (who does what)

- Pledge notice: registered online at the branch with the mortgage banker; otherwise at the Pledges Registrar (S05, S06).
- Inspection reports: customer produces them on gov.il per borrower/pledgor, then uploads or emails them (S05, S06).
- Notarized POA: borrowers/pledgors in front of a notary (S05, S06).
- Warning note in favour of the bank: sellers sign, seller's lawyer verifies and registers online, buyer returns the original plus a post-registration Tabu extract and registration confirmation (S05).
- Contractor: undertaking signed by the contractor before a lawyer; guarantee documents from the contractor (S06).
- Mortgage deed for Tabu: form 3801 sent to the mortgage centre (S08, S09).

### D.9 Seller/lawyer actions (second-hand)

- Buyer's lawyer passes the "התחייבות" form to the sellers or their lawyer (S05).
- Seller's lawyer verifies signatures, registers the warning note, fills the "תשלום על חשבון ההלוואה" form (S05).
- Tax documents come from the buyer's or seller's lawyer (S05). Foreign-resident seller form is requested from the lawyer (S05).

### D.10 Disbursement conditions (stated)

- "לאחר שעמדתם בכל הדרישות, תבוצע ההלוואה כמוסכם." (S07)
- Contractor: only by payment voucher (S07, S06); equity first, then mortgage money (S06).
- Second-hand: transfer to accounts listed in the disbursement-instruction form, with proof for each account; last tranche only after tax approvals or a trust deposit (S05).
- Foreign-resident seller: "לפני העברת הכספים" present the land-books approval form (S05).
- Execution date chosen by borrowers "בכפוף להשלמת כל הפעולות הנדרשות לשם כך" (S07); payment day 1/10/15 (S07).
- English: life insurance is "a preliminary requirement for approval" (S49).

### D.11 Post-disbursement and servicing

- Policy renewal and replacement by email; bank review; approval letter or correction letter (S21, S22).
- Forms: deed production, standing-order change, payment-date change, lien release, death notice, insurance exemptions, letter of intent, second-degree lien, payoff notice (S08).
- Payoff: early-repayment notice → letter of intent → payment → payoff-update form → SMS within 2 business days → lien release within 30 days (expedited 14) (S31).
- Lien deletion obligations: release assets within two weeks; file deletion notice within 30 days (S38).

### D.12 Actor and responsibility matrix (from the sources)

| Actor | Responsibilities stated in sources | Source |
|---|---|---|
| Borrower / customer | Apply; provide documents; choose appraiser and pay; buy insurance; sign at branch; register pledge; produce inspection reports; get notarized POA; set up standing order; collect tax approvals; coordinate seller forms via lawyer | S05, S06, S07 |
| Guarantor | Identity and income documents; signs loan documents; countersigns exemption forms | S03, S05, S07, S11, S12 |
| Mortgage banker | Provides forms (affidavit, POA, appraiser list, standing order, spouse consent); online pledge registration at branch; standing-order execution; receives originals | S05, S06 |
| Branch manager | May ask to meet and request more information | S07 |
| Appraiser | Values property, records reinstatement value, sends valuation directly to bank | S05, S06, S07 |
| Buyer's lawyer | Passes seller undertaking form; supplies tax documents; verifies affidavit signatures | S05 |
| Seller's lawyer | Verifies seller signatures; registers warning note; fills disbursement form; provides foreign-resident form | S05 |
| Notary | Authenticates irrevocable POA | S04, S05, S06 |
| Seller | Signs undertaking, warning-note form, equity confirmation, disbursement form; provides ID; spouse consent; lien release / letter of intent | S05 |
| Contractor | Signs mortgage-registration undertaking before a lawyer; provides guarantee endorsement/undertaking/exclusion letter; issues voucher book; confirms equity paid | S04, S06, S07 |
| Insurer / Tefahot agency | Sells life and structure policies; summary form at kiosk; full policy after execution | S05, S07, S20 |
| Commercial bank | Signs standing-order authorization | S05, S07 |
| Pledges Registrar / Land Registry | Pledge registration and inspection reports; mortgage and warning-note registration | S05, S06, S09 |
| Ministry of Housing | Issues eligibility certificate | S07, S24 |

### D.13 Variant lifecycles

- **Refinance at Mizrahi (S29):** digital/branch/phone request → feasibility check → choose tracks → review terms → offer → sign forms (remote signing after a banker call).
- **Refinance elsewhere / full payoff (S30, S31):** request letter of intent and second-degree consent → payoff by cheque (+ source-of-money proof) or transfer (+ update form and proof) → SMS within 2 business days → lien release within 30 days (expedited within 14 days).
- **Porting (S34):** application with contracts and extracts of both properties → bank review → approval → extra actions such as appraisal → new loan agreement if an additional loan is taken → new lien registered and old one released.
- **Second-degree lien (S10, S37):** form 2813 with an updated extract and the other creditor's form → bank discretion → ₪150 fee.
- **Price-for-resident (S26):** eligibility certificate → lottery → win → preliminary approval (recommended before the briefing) → apartment selection → sale contract → mortgage as usual.

### D.14 Tefahot Touch — what the customer can do (consolidated)

| Capability | Verbatim | Source |
|---|---|---|
| Submit a mortgage request | "מגישים בקשה למשכנתא ומקבלים עדכון אם קיבלתם אישור עקרוני" | S17 |
| Upload documents / download approvals | "מעלים מסמכים ומורידים אישורים בלי להגיע לסניף" | S17 |
| Send and receive documents | "שליחה וקבלה של מסמכים בקלות - אין צורך להגיע לסניף" | S16 |
| Scan and upload | "להגיש בקשה, לסרוק מסמכים ולהעלות אותם" | S39 |
| Upload inspection reports and policies | "את דו"חות העיון שהופקו יש להעלות באפליקציית טפחות טאצ'" / "את הפוליסות שרכשתם ניתן להעלות באפליקציית טפחות טאצ'" | S05 |
| Real-time status and next steps | "להתעדכן בזמן אמת באיזה שלב נמצאת בקשת ההלוואה שהגשתם, מה משמעות שלב זה ומהם השלבים הבאים" | S18 |
| Remaining tasks | "לדעת מה קורה בכל שלב בתהליך, ומה נותר להשלים" / "עושה לכם סדר בכל המשימות עם עדכונים ישירות לנייד שלכם" | S16 |
| Messaging with a human expert | "להתכתב עם מומחה משכנתאות" / "לא בוט, בן אדם" | S18, S16 |
| Meetings | "מתאמים ומעדכנים מועדי פגישות" / "להתעדכן בפרטי הפגישה שנקבעה עם הבנקאי שלכם" | S17, S18 |
| Track until full disbursement | "מתעדכנים בכל שלב בתהליך עד לקבלה של כל כספי המשכנתא" | S17 |
| Refinance | "באמצעות טפחות טאצ' אפשר לקחת משכנתא חדשה או למחזר משכנתא קיימת" | S17 |
| Tools | "כלים לניהול המשכנתא, כמו מחשבון, ומידע מאתר מדלן על מחירים, תשואות ומצב מערכת החינוך" | S17 |
| Availability | "האפליקציה זמינה ללקוחות כל הבנקים" | S17 |
| Advisers' interface | "לפתוח בקשה חדשה באמצעות טופס דיגיטלי … לבצע סינון לפי סטטוס הבקשה" | S19 |

---

## (E) Searched for but NOT FOUND on official pages

1. **General validity period of a Mizrahi preliminary approval (regular mortgage).** NOT FOUND. Official pages only say it is "מוגבל בזמן" (S26). Closest numbers: interest-rate lock 12/24 days (S07 §8) and 45 days in the **pension-mortgage** guide only (S52). Third-party sites claim "24 days"; not on any Mizrahi page, so excluded.
2. **Maximum age, in days, of individual documents** (Tabu extract, payslips, statements, CPA letter, municipality approval). NOT FOUND. Sources use "3 החודשים האחרונים", "עדכני/מעודכן" or "בתוקף" without day counts. The only day-based rules are the 45-day resubmission rule (S05), the 90-day limit for another bank's appraisal (S07), and the 30-day letter-of-intent validity (S08).
3. **The 45-day rule on the dedicated documents page (S01), the checklist PDFs (S02–S04) or the guide (S07).** NOT FOUND; it appears only on S05.
4. **Validity of an appraisal ordered through Mizrahi itself.** NOT FOUND.
5. **Dedicated self-build (בנייה עצמית) page or document list.** NOT FOUND. Only "בהלוואות למימון בנייה – היתר בנייה ואישור מהנדס על שלב הבנייה (אם הבנק דורש זאת)" (S07) and the appraisal type covering "בניה עצמית" (S07 p.8).
6. **Renovation-mortgage document list.** NOT FOUND (S07 lists "שיפוץ דירה או הרחבתה" as a purpose; S56 mentions the "שפץ נא" loan only).
7. **Any-purpose mortgage document list.** NOT FOUND (S42 gives terms only).
8. **"FastTrack" / "mortgage FastTrack".** NOT FOUND on any official page. The digital application (S53) and reform page (S39) are the closest.
9. **Self-employed specifics:** number of years of assessments beyond "previous year", the bank's CPA-letter template, or a Mizrahi "עוסק מורשה/פטור" income form. NOT FOUND officially. A form "2708 אישור הכנסה עבור עוסק מורשה/פטור" appears only on a third-party site (effectivemortgage.co.il); not cited.
10. **Foreign-resident / non-resident borrower document list** (foreign income proof, translations, apostille, foreign credit reports). NOT FOUND. Only passport + second ID (S02, S07), representative appointment (S07) and English LTV statements (S49, S50).
11. **Guarantor criteria** (age, income, residency, number, when required). NOT FOUND beyond "טיב הערבים ומספרם ייקבע לפי קריטריונים שונים…" (S07).
12. **Equity source documents for purchase** (gift letter, savings proof, sale proceeds). NOT FOUND in Hebrew. Only the sellers' equity confirmation (S05), contractor confirmation (S06), the generic English source-of-funds statement (S49), and source-of-money proof for payoff by cheque (S30, S31).
13. **Upload technical requirements in Tefahot Touch** (file types, size, resolution, naming). NOT FOUND. The only format rule is for policy-renewal emails: "כקובץ pdf ללא תמונות" (S21).
14. **Tefahot Touch status names / stage taxonomy.** NOT FOUND.
15. **Credit-data consent form.** NOT FOUND (S05 only says the bank queries the system).
16. **Debt-to-income limit in Hebrew official pages.** NOT FOUND. Only English S49 ("40%").
17. **Deadline from approval to signing or disbursement**, other than rate-lock windows. NOT FOUND.
18. **Health-declaration content or underwriting thresholds.** NOT FOUND ("כולל הצהרת בריאות" only, S07).
19. **Certified-copy requirements** ("נאמן למקור"), wet-ink vs digital signature rules for customer documents. NOT FOUND (except "originals" for specific forms in S05).
20. **List of documents to give the appraiser.** NOT FOUND (S05 says the banker's form lists them; the form is not published).
21. **Published versions of forms referenced by S05/S06:** "התחייבות", "בקשה לרישום הערת אזהרה בגין התחייבות לרישום משכנתא בהסכמת כל הצדדים", "אישור על תשלום הון עצמי", "תשלום על חשבון ההלוואה", "החתמת בן זוג של המוכר", sole/replacement apartment affidavit, appraiser-referral form, standing-order form. NOT FOUND as downloadable files.
22. **Documents for refinancing a mortgage from another bank into Mizrahi.** NOT FOUND as a list (S29 mentions "שירות לטיפול במסמכי משכנתא"; S08 mentions a loan-purpose certificate for refinancing).
23. **A single "conditions for disbursement" (תנאים לביצוע / העמדת הלוואה) checklist.** NOT FOUND as one page; reconstructed in D.10 from S05, S06 and S07.
24. **Hebrew LTV caps by borrower type** (first home / upgrader / additional property / foreign resident). NOT FOUND in Hebrew except 75% first apartment (S47), the >75% price-for-resident relief (S25), and 70%/50% totals for any-purpose loans (S42, S43, S29). The full breakdown is English-only (S49).

---

## (F) Contradictions and ambiguities between sources

1. **File-opening fee:** "עמלה קבועה … 360 ₪" (S05) vs "0.25% מסכום ההלוואה … ועד 360 ₪" (S28).
2. **Inspection report fee:** "11 ₪ עבור כל דו"ח" (S05) vs "12 ₪ לדו"ח" (S30, S31).
3. **Pregnancy threshold (eligibility):** "מחודש חמישי ואילך … אישור עדכני של רופא ממוסד רפואי מוכר" (S07, 11.2023) vs "משבוע 24 ואילך – אישור מרופא" (S24, sitemap 2026-03-16).
4. **Self-employed documents (AND vs AND/OR, CPA vs tax advisor):** S02 "שומת מס לשנת המס הקודמת **ו**אישור רואה חשבון לשנת המס הנוכחית"; S03 "**ו/או**"; S07 "שומת מס אחרונה **ו/או** אישור רו"ח"; S05 "אישור רו"ח **או יועץ מס** … + שומת מס לשנה הקודמת".
5. **Form 106:** required for salaried in S02/S35 but absent from S05, S07 and S03.
6. **Controlling shareholder:** S05 requires "3 תלושי שכר … + דו"חות כספיים מבוקרים של השנה הקודמת + מאזן בוחן לשנה השוטפת"; S02 requires latest approved tax assessment + Form 3806 + current audited report + trial balance, with no payslips and two distinct sub-cases (dividend-drawing vs 100%/controlling employee).
7. **Loan-balances report and kollel/shareholder items:** present in S02 (2026) and S05, absent from S07 and from the 2019 checklist S35.
8. **Two live versions of the borrowers checklist:** S02 (modified 2026-06-11, linked from S01) vs S35 (2019, linked from the porting page S34) with different content (S35 lacks "בתוקף" on IDs, shareholder sections, kollel, loan-balances report, and rented-property extract).
9. **Guarantors PDF scope:** S03 is titled for guarantors but includes property and post-approval items (appraisal, liens, Sale Law guarantee, standing order, seller ID/account). Unclear whether these apply to guarantors or the PDF reuses the borrower template.
10. **Appraisal requirement:** "בכל בקשה למשכנתא יש לפנות לשמאי" (S05, second-hand) vs "במקרים מסוימים, הבנק יבקש שמאות" (S06, contractor) vs "(אם הבנק דורש זאת)" (S07).
11. **Power of attorney:** notary-authenticated ("בפני נוטריון", S05; "מאושר על ידי נוטריון", S04) vs "עו"ד שיאשר את ייפוי הכוח שתעניקו לבנק" (S28).
12. **Sale Law guarantee strength:** "הבנק **ידרוש** מלווה שקנה דירה חדשה להציג בפניו הוכחה" (S07 p.6) vs "הבנק **עשוי לדרוש**" (S04) vs "(במקרה של רכישת דירה חדשה – **אם הבנק דורש זאת**)" (S07 p.16).
13. **LTV / total-lien cap:** any-purpose loan "סך כל ההלוואות הוא עד 70% משווי הנכס המשועבד" (S42) vs Tefahot card "בתקופת משבר הקורונה ניתנה הקלה … 70% … ולא 50% כמו בימי שגרה" (S43) vs refinancing disclaimer "לא יעלה על 50%" (S29) vs English "may not exceed 50%" (S50).
14. **Early-repayment notice window:** S07 "10 ימים לפחות לפני יום הפירעון אך לא יותר מ-45 יום"; S08 "החל מ-10 ימים ממועד **משלוח** ההודעה … ולמשך 45 ימים"; S14 "לאחר 10 ימים מיום **קבלת** ההודעה בבנק, ויהיה תקף למשך 35 ימים נוספים". Sending vs receipt, and 45 total vs 45 after day 10.
15. **Expedited lien-release timing:** S08 "שחרור שעבוד יבוצע 30 יום לאחר קבלת אסמכתה" for the **expedited** procedure vs S30/S31 standard "תוך 30 יום ממועד הפירעון" and expedited "תוך 14 יום".
16. **Lien-release attachments:** S08 "דו"ח רישום משכון ודו"ח תוצאות עיון" vs S30/S31 "דו"ח תוצאות עיון על שם כל אחד מהלווים" (no pledge-registration report).
17. **Two live versions of form 3801:** S09 (11.2025): "לפחות אחד", bithonot@umtb.co.il, fax 03-5686982, parcellation and warning-note clauses, 1 vs 5 copies; S55 (05.19): "אחד", stf@umtb.co.il, fax 03-5656621, none of those clauses.
18. **Insurance threshold basis:** S20 "עבור כל הלוואה שיתרתה מעל 30,000 ₪" (per loan) vs S07 exemptions "יתרת כל ההלוואות בשעבוד הנכס" (property, aggregate per property) and "יתרת כל ההלוואות של הלווה בשעבוד נכס מסוים" (life, per borrower per property).
19. **Life-insurance sum:** "בגובה סכום המשכנתא ולכל תקופתה" (S05) vs "בסכום יתרת ההלוואה בתוספת עמלת פרעון מוקדם" (S07).
20. **Property-insurance sum:** "פוליסה בגובה ערך הכינון" (S05) but partial insurance allowed (S05 "או בסכום חלקי"; S07 "ביטוח לפי יתרה" with a floor). A reviewer must accept either.
21. **Property-insurance clauses differ by source:** S05 lists lien clause with branch number/address, irrevocable beneficiary, 30-day notice; S07 adds an earthquake clause; S21 adds policy period matching the loan term, amounts matching bank requirements, borrower name and loan number. Union of requirements is not stated anywhere in one place.
22. **Contractor insurance timing:** S07 "החובה לבטח את הנכס תחול רק מהמועד בו התחייב הקבלן למסור את הדירה" vs S06 "תדרשו להתחייב להמציא פוליסת ביטוח נכס בעתיד לכשתושלם הבנייה" (undertaking now, policy later).
23. **Sole/replacement apartment affidavit (LTV > 50%)** appears only in S05; not in S02–S04 or S07.
24. **Heading typo:** S05 seller section titled "איסור על הסרת שעבודים" (*prohibition on removing liens*), while the body describes "אישור על הסרת השעבודים" (*approval of lien removal*).
25. **Duplicate standing-order step:** S07 §3 lists the commercial-bank authorization in both step ה and step ו.
26. **Purpose of the checklist:** S01 says the list is for "אישור סופי של הלוואת משכנתא" (final approval), while S51 links the same page as documents "להגשת הבקשה" (for submitting the request).
27. **Equity requirements by context:** 25% for a first apartment (S23) vs ₪100,000 if market value ≤ ₪1.8M (S25, S27) vs English 75% / 70% / 50% LTV by buyer type (S49). Not contradictory per se, but scope-dependent.
28. **English DTI "40%"** (S49) is attributed to the Bank of Israel but appears in no Hebrew official page; treat as unverified.
29. **Interest-rate lock vs preliminary-approval validity:** S07 defines rate-lock windows tied to "מיום האישור" without saying whether "אישור" means the preliminary approval; S52 (pension) gives 45 days for the preliminary approval itself.
30. **Stale content still live:** S57 benefits "עד 31.12.2022"; S28 purchase-tax figure "נכון לשנת 2023"; S03/S04/S35 PDFs dated 2019; S14 dated 04.2015; S11/S12 form versions 1.2019.
31. **Naming of the land authority:** S04 uses "מינהל מקרקעי ישראל ("המינהל")" while S07 uses "רשות מקרקעי ישראל ("רמ"י")" for the same registration category.
32. **Ownership of eligibility documents:** S05 says "את רשימת המסמכים הרלוונטית לכם, תקבלו מהבנקאי"; S24 publishes a list; S07 §15א publishes a slightly different list (e.g. "אישור מקצין העיר" vs "אישור על מהלך שירות צבאי. ניתן להנפיק באתר צה"ל"; reserve-duty item only in S24).

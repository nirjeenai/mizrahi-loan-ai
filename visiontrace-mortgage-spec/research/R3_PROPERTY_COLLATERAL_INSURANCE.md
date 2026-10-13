# R3 — Property, Collateral & Insurance Documents in an Israeli Mortgage

- Research date (and retrieval date of every source below): **2026-10-12**.
- Scope: the documents about the **property** and the **collateral** in a residential mortgage, as an AI document-review system would meet them: Land Registry extract, Israel Land Authority (ILA / רמ"י) and housing-company rights confirmations, Sale Law securities for new builds (guarantee, voucher booklet, exclusion letter), warning notes, mortgage and pledge registration, undertakings to register a mortgage, the purchase agreement, tax and municipal clearances, the appraisal, life and structure insurance, and seller-side documents (seller's bank letter of intent, spouse consent, foreign-resident seller, inheritance orders).
- Rule followed: nothing below is invented. Every statement points to a source ID from section A with a verbatim Hebrew quote (or an official English text) and an English translation. Anything that could not be verified is listed in section D. Translations are mine unless marked "official translation".
- Access caveats (important for anyone re-checking):
  - **www.gov.il HTML pages were blocked** during this session (Cloudflare "Sorry, you have been blocked" to curl; WebFetch timed out). For those pages the quote is the text the search engine captured from the page, tagged **[SN]**. Re-verify against the live page before relying on exact wording.
  - **gov.il PDF files under `/BlobFolder/` downloaded normally** and were read in full (tag **[P]**). This is how the ILA procedures and the appraisal standards were obtained.
  - **Bank of Israel HTML pages sit behind a bot wall** (Radware); its PDF files downloaded normally.
  - Statutes and regulations were read on **Wikisource** (an unofficial mirror of the official text), tagged **[M]**.

## Evidence legend

| Tag | Meaning |
| --- | --- |
| [F] | Page fetched directly (HTML) in this session; quote is verbatim. |
| [P] | PDF text extracted in this session. Verbatim, except RTL extraction artefacts (flipped parentheses, `10/MM/YY` printed as `YY/MM10/`, line breaks), which were normalized. No words changed. |
| [SN] | Text captured by the search engine from a page that could not be fetched. Verbatim as captured; `…` marks gaps. Treat as partial. |
| [M] | Official legal text or official form read on a non-official host (Wikisource, or a law-firm site hosting an official form/procedure). |
| SECONDARY | Non-authoritative source (law firm, commercial site). Used only to flag something to verify, never as a rule. |

Field-status tags in section C:

- **SOURCE-BACKED** — the field is named, or directly required, by the cited law, regulation, procedure, official form or official bank page.
- **PROPOSED** — useful for extraction or cross-checking but not mandated by any source found; a design suggestion only.

---

## (A) Source inventory

| ID | Source (issuer) | URL | Date shown on source | Ev. |
| --- | --- | --- | --- | --- |
| S01 | Land Registration & Settlement of Rights Authority — "הפקת נסח טאבו מפנקסי המקרקעין" (service page, Hebrew) | https://www.gov.il/he/service/land_registration_extract | not visible (fetch blocked) | [SN] |
| S02 | Same authority — "Generation of a Land Registry Extract (Tabu Extract) from the Land Registers" (official English page) | https://www.gov.il/en/service/land_registration_extract | not visible | [SN] |
| S03 | Same authority — "מדריך לרישום והפקת נסח טאבו - מנויים" (subscriber guide page; only metadata captured) | https://www.gov.il/he/pages/guide-new-registration-extract-pay | published 17.12.2023, updated 05.08.2024 | [SN] |
| S04 | תקנות המקרקעין (ניהול ורישום), התשע"ב-2011 (regs 1, 7, 8, 17, 18, 21, 92) | https://he.wikisource.org/wiki/תקנות_המקרקעין_(ניהול_ורישום) | page last edited 13 May 2025 | [M] |
| S05 | חוק המקרקעין, התשכ"ט-1969 (ss. 8, 126, 127, 128) | https://he.wikisource.org/wiki/חוק_המקרקעין | page last edited 28 Oct 2025 | [M] |
| S06 | Land Registry — "בקשה לרישום או ביטול הערת אזהרה" (service page) | https://www.gov.il/he/service/caveat_filling | not visible | [SN] |
| S07 | Land Registry — topic page "רישום מקרקעין (טאבו)" (lists the mortgage-registration service; news item 29/06/25) | https://www.gov.il/he/departments/topics/registry-land | news item dated 29/06/25 | [SN] |
| S08 | Official Ministry of Justice form "בקשה לרישום הערת אזהרה" (copy hosted by a real-estate site) | https://storage.nadlancenter.co.il/media/Storage/47541.pdf | n/a | [SN][M] |
| S09 | "קובץ נהלי הרשות לרישום והסדר זכויות מקרקעין" — Land Registry procedures compendium, "עדכון אחרון ביום 30/10/2022" (copy hosted by a law firm) | https://www.barlawyers.com/_files/ugd/6d4db5_21f13de50c1b437bb4df2f1e158f4287.pdf | 30/10/2022 | [P][M] |
| S10 | Ministry of Construction & Housing — "בדיקת מצב רישום הדירה" | https://al-harishum.moch.gov.il/ | n/a | [F] |
| S11 | ILA Procedure **90.08B** "אישור זכויות או הודעה על רישום זכויות בנכס" | https://www.gov.il/BlobFolder/policy/9008b-procedure/he/Procedures_90.08b.pdf | published 21.02.2023 (original 31.03.2015) | [P] |
| S12 | ILA Procedure **90.02B** "התחייבות לרישום משכנתה וסילוקה" | https://www.gov.il/BlobFolder/policy/9002b-procedure/he/Procedures_90.02b.pdf | published 08.07.2025 (original 26.02.2015) | [P] |
| S13 | datahelp.co.il — reproduction of ILA ordering text (printout vs. binding confirmation) — SECONDARY | https://datahelp.co.il/RightsConfirmation.asp?NEGISHOT=yes | n/a | [SN] |
| S14 | Bank of Israel — Proper Conduct of Banking Business Directive **451** "נהלים למתן הלוואות לדיור", consolidated **version 22 (7/23)** | https://www.boi.org.il/media/utld2tgp/451.pdf | version 22, last update 19/07/23 | [P] |
| S15 | Bank of Israel — Directive 451 version 22, **official English translation** | https://www.boi.org.il/media/5mooz2uw/451_en.pdf | (07/23) [22] | [P] |
| S16 | Bank of Israel — circular ח-06-2755 (update 22 to Directive 451) | https://www.boi.org.il/media/2ochqat1/h2755.pdf | 19 July 2023 | [P] |
| S17 | Bank of Israel — circular postponing s.15ב1 of update 22 to 1 April 2025 | https://boi.org.il/media/n2mk2juj/111542.pdf | n/a (refers to 2023–2025 circulars) | [SN] |
| S18 | Bank of Israel — draft circular amending Directive 451 (appraisal reuse), "חוזר מס' ח-06-XXXX" (a draft) | https://www.boi.org.il/media/h32l11ch/%D7%94%D7%95%D7%A8%D7%90%D7%94-451.pdf | 23 Oct 2018 (draft) | [P] |
| S19 | Bank of Israel (English) — "The reform to increase information transparency and competition in mortgages" | https://boi.org.il/en/information-and-service-to-the-public/banking-customer-service-information/financial-education/the-reform-to-increase-information-transparency-and-competition-in-mortgages/ | n/a | [SN] |
| S20 | חוק הבנקאות (שירות ללקוח), התשמ"א-1981 (ss. 7, 9א) | https://he.wikisource.org/wiki/חוק_הבנקאות_(שירות_ללקוח) | page last edited 1 Sep 2026 | [M] |
| S21 | Mizrahi-Tefahot — "מדריך לקבלת הלוואת משכנתא" (form 154) | https://www.mizrahi-tefahot.co.il/media/y0ufpe5h/%D7%9E%D7%93%D7%A8%D7%99%D7%9A-%D7%9C%D7%A7%D7%91%D7%9C%D7%AA-%D7%94%D7%9C%D7%95%D7%95%D7%90%D7%AA-%D7%9E%D7%A9%D7%9B%D7%A0%D7%AA%D7%90.pdf | "(11.2023) 154" printed on pages; PDF modified 19 Aug 2026 | [P] |
| S22 | Mizrahi-Tefahot — "משימות בעת רכישת דירה יד שנייה" | https://www.mizrahi-tefahot.co.il/mortgages/mortgagetoollib/second-hand/ | no date on page | [F] |
| S23 | Mizrahi-Tefahot — "משימות בעת רכישת דירה מקבלן" | https://www.mizrahi-tefahot.co.il/mortgages/magazine/constructor/ | no date on page | [F] |
| S24 | Mizrahi-Tefahot — "טפסים שימושיים ובקשות בנושאי משכנתא" | https://www.mizrahi-tefahot.co.il/mortgages/updatemortgage/mortgage-forms/ | no date on page | [F] |
| S25 | Mizrahi-Tefahot — "ביטוח משכנתא" | https://www.mizrahi-tefahot.co.il/mortgages/takemortgagelib/mortgage-insurance/ | no date on page | [F] |
| S26 | Mizrahi-Tefahot — FAQ "איך עושים ביטוח משכנתא ואיך מחדשים ביטוח משכנתא?" | https://www.mizrahi-tefahot.co.il/faq/mortgage-insurance/ | no date on page | [F] |
| S27 | Mizrahi-Tefahot — "פניות בנושאי משכנתא" (policy review by the bank) | https://www.mizrahi-tefahot.co.il/contact-us/pz-mortgage/ | no date on page | [SN] |
| S28 | Mizrahi-Tefahot — "אימות פרטים בשוברי תשלום לדירות" (voucher/project validation tool) | https://www.mizrahi-tefahot.co.il/mortgages/ckeckmortgage/payments-validation/ | no date on page | [SN] |
| S29 | חוק המכר (דירות) (הבטחת השקעות של רוכשי דירות), התשל"ה-1974 (ss. 2, 2א1, 2ב, 2ג, 3ב) | https://he.wikisource.org/wiki/חוק_המכר_(דירות)_(הבטחת_השקעות_של_רוכשי_דירות) | page last edited 30 Sep 2026 | [M] |
| S30 | תקנות המכר (דירות) (הבטחת השקעות של רוכשי דירות) (ערבות בנקאית), התשע"א-2010 — prescribed guarantee form | https://he.wikisource.org/wiki/תקנות_המכר_(דירות)_(הבטחת_השקעות_של_רוכשי_דירות)_(ערבות_בנקאית) | page last edited 2 Oct 2026 | [M] |
| S31 | חוק המכר (דירות), התשל"ג-1973 (ss. 2, 3 — specification) | https://he.wikisource.org/wiki/חוק_המכר_(דירות) | page last edited 25 Dec 2025 | [M] |
| S32 | Ministry of Construction & Housing — "זכויותיו של רוכש הדירה" | http://www.gov.il/he/pages/zexuyot_shel_rochesh_hadira | not visible | [SN] |
| S33 | תקנות המשכון (סדרי רישום ועיון), התשנ"ד-1994 (regs 5, 13, 13א; fee schedule) | https://he.wikisource.org/wiki/תקנות_המשכון_(סדרי_רישום_ועיון) | page last edited 14 Dec 2025 | [M] |
| S34 | Official form 1 "הודעת מישכון" (Registrar of Pledges) — two copies hosted by law firms | https://www.harel-law.com/wp-content/uploads/2020/08/%D7%98%D7%95%D7%A4%D7%A1_%D7%91%D7%A7%D7%A9%D7%94_%D7%9C%D7%A8%D7%99%D7%A9%D7%95%D7%9D_%D7%9E%D7%A9%D7%9B%D7%95%D7%9F.pdf ; https://www.cotton.co.il/sites/default/files/2025-03/%D7%98%D7%95%D7%A4%D7%A1%20%20%D7%94%D7%95%D7%93%D7%A2%D7%AA%20%D7%9E%D7%A9%D7%9B%D7%95%D7%9F%20.pdf | n/a | [SN][M] |
| S35 | Real Estate Appraisers Council (Ministry of Justice) — **Standard 19.0** "פרוט מזערי נדרש בשומות מקרקעין המיועדות להצעת זכויות במקרקעין כבטוחה לאשראי" | https://www.gov.il/BlobFolder/dynamiccollectorresultitem/assessor-standardization-db_19/he/land_assessor_shameim_19.pdf | June 2010; in force for appraisals signed from 1/11/2010 | [P] |
| S36 | Same council — **Standard 1.1** "פירוט מזערי נדרש בשומות מקרקעין לסוגיהן" | https://www.gov.il/BlobFolder/dynamiccollectorresultitem/assessor-standardization_1_1/he/appendix-4-1.1.pdf | February 2025; in force for appraisals signed from 1/4/2025 | [P] |
| S37 | תקנות שמאי מקרקעין (אתיקה מקצועית), התשכ"ו-1966 — Schedule (minimum contents of an appraisal report) | https://he.wikisource.org/wiki/תקנות_שמאי_מקרקעין_(אתיקה_מקצועית) | page last edited 25 Sep 2026 | [M] |
| S38 | Israel Tax Authority — "טופס הצהרה על מכירת ורכישת נכס מקרקעין (טופס 7000)" | https://www.gov.il/he/service/real-estate-tax-7000 | not visible | [SN] |
| S39 | Israel Tax Authority form 7161 "בקשה לקבלת אישור לרישום בפנקסי המקרקעין" (copy hosted by a third party) | https://hmercaz.com/wp-content/uploads/2025/11/misui7161.pdf | n/a | [SN][M] |
| S40 | חוק מיסוי מקרקעין (שבח ורכישה), התשכ"ג-1963 (ss. 15, 16, 49א) | https://he.wikisource.org/wiki/חוק_מיסוי_מקרקעין_(שבח_ורכישה) | page last edited 30 Sep 2026 | [M] |
| S41 | פקודת העיריות (s. 324) | https://he.wikisource.org/wiki/פקודת_העיריות | page last edited 30 Sep 2026 | [M] |
| S42 | Tel Aviv-Yafo Municipality — "תעודה לרשם המקרקעין (טאבו) להעברת זכויות בנכס" | http://tel-aviv.gov.il/Residents/Assets/Pages/TransferringRights.aspx | fee "נכון ל-1 בינואר 2026" | [SN] |
| S43 | חוק התכנון והבנייה, התשכ"ה-1965 — Third Schedule s.10 (betterment levy) | https://he.wikisource.org/wiki/חוק_התכנון_והבנייה | page last edited 30 Sep 2026 | [M] |
| S44 | Registrar of Inheritance Affairs — "הרשם לענייני ירושה אונליין" | https://inheritance.justice.gov.il/RashamYerusha/ | "עדכון אחרון: 09/10/2026" | [SN] |
| S45 | Administrator General & Registrar of Inheritance — "מדריך ליורשיו של מנוח שלא הותיר צוואה" | https://www.gov.il/blobFolder/guide/guide_with_no_will/he/guide_with_no_will_file.pdf | תשפ"ד-2023 | [P] |
| S46 | News report (ice.co.il) on Tax Authority certificates in the personal area — SECONDARY | https://www.ice.co.il/digital-140/news/article/954847 | 2/4/2023 | [SN] |
| S47 | vaad.org.il — explanation of extract types incl. "נסח היסטורי סרוק" and "נסח חלקי" — SECONDARY | https://vaad.org.il/info/873825763 | n/a | [SN] |

---

## (B) Findings per document

Quote format: **Q-id** · source · tag → HE (verbatim) → EN (translation) → what it proves / what it does not prove.

### B1. Land Registry extract — נסח רישום מקרקעין ("נסח טאבו")

**Purpose & issuer.** An official extract from the land registers, issued by the Land Registration and Settlement of Rights Authority (Ministry of Justice). Anyone may order it, for a fee, online; an Apostille-stamped version is also available.

**Q1.1** · S01 [SN]
HE: «השירות מאפשר לכל אדם להזמין בתשלום נסח רישום מפנקסי המקרקעין, וגם נסח חתום בחותמת אפוסטיל.»
EN: "The service allows any person to order, for a fee, a registration extract from the land registers, and also an extract signed with an Apostille stamp."
Proves: anyone can order; paid; Apostille variant exists. Does not prove: any validity period or who must rely on it.

**Q1.2** · S01 [SN] — contents listed by the official page
HE: «מסמך רשמי המכיל מידע משפטי על נכס כפי שרשום בפנקסי המקרקעין: - בעלים רשומים. - שעבודים, משכנתאות, עיקולים, צווים שיפוטיים ועוד. - הגבלות אם יש.»
EN: "An official document containing legal information about a property as registered in the land registers: registered owners; charges, mortgages, attachments, judicial orders and more; restrictions, if any."
Proves: the minimum content categories (owners, charges/mortgages, attachments, court orders, restrictions). Does not prove: the exact section headings or columns of the PDF.

**Q1.3** · S01 [SN] — recency
HE: «המידע בנסח נכון ליום הפקתו.»
EN: "The information in the extract is correct as of the day it was produced."
Proves: an extract is a snapshot at its issue date. Does not prove: any official expiry period (none found — see D).

**Q1.4** · S01 [SN] — official extract types
HE: «נסח רגיל מלא: - כולל את כל המידע העדכני על הנכס כפי שרשום בפנקסי המקרקעין. - מתאים לרוב המקרים כמו קנייה ומכירה. נסח היסטורי: - כולל גם רישומים שנמחקו. - נדרש כאשר צריך לבדוק את ההיסטוריה של הנכס. נסח מרוכז: - מכיל מידע כללי על כל בעלי הדירות בבית משותף. - לא כולל את כל פרטי הרישום.»
EN (official, S02): "Full Regular Extract: Includes all current information regarding the property as registered in the Land Registers. Suitable for most cases, such as buying and selling. Historical Extract: Includes deleted (canceled) registrations as well. Required when there is a need to review the history of the property. Concentrated Extract (Condominium Summary): Contains general information regarding all apartment owners in a joint house (condominium). Does not include full registration details."
Proves: three online types and when each is used. Does not prove: other types. SECONDARY S47 additionally lists "נסח היסטורי סרוק" (cancelled registrations before 1991) and "נסח חלקי" (parcels with over 50 rights holders, only at the registry office, not online) — not confirmed on an official page.

**Q1.5** · S01 [SN] + S02 [SN] — identifiers
HE: «כדי להפיק את הנסח יש להקליד את מספר גוש חלקה של הנכס» … «מספר תת החלקה בטאבו אינו בהכרח זהה למספר הדירה בבניין.»
EN (official, S02): "In order to generate the extract, you must enter the Block (Gush) and Parcel (Chelka) numbers of the property." "If the apartment is located in a joint house (condominium), you will also be required to enter the Sub-Parcel (Tat-Chelka) number." "The Sub-Parcel number in the Land Registry (Tabu) is not necessarily identical to the apartment number in the building."
Proves: the keys are Gush / Chelka / Tat-Chelka, and the sub-parcel number must not be matched against the apartment number. Does not prove: anything about address-based lookup.

**Q1.6** · S01 [SN] + S02 [SN] — authenticity
HE: «מקבלים את הנסח למייל תוך דקות: - הנסח כולל חתימה אלקטרונית מאושרת. - הנסח רשמי ומוכר כמסמך מקורי רק בצורה דיגיטלית ולא כשהוא מודפס.»
EN (official, S02): "Receive the extract via email within minutes: The extract includes a certified electronic signature. The extract is official and recognized as an original document only in its digital format, and not when printed."
Proves: the authenticity mechanism is the approved electronic signature on the digital file; printouts are not originals. Does not prove: any verification code or lookup service (none found — see D).

**Q1.7** · S04 [M] — regulation 92 (the legal basis of Q1.6)
HE: «(ב) קבלת הנסח יכול שתהיה במסירת תצלום, פלט או מסר אלקטרוני מאושרים בידי רשם או חתומים בחתימה אלקטרונית מאובטחת, כפי שיורה הממונה. (ג) התקבל נסח מקוון החתום בחתימה אלקטרונית מאושרת, לא יראו פלט נייר שלו כהעתק נאמן של הנסח; פלט נייר כאמור של נסח לא יהיה קביל בכל הליך שיפוטי להוכחת זכויות במקרקעין.»
EN: "(b) An extract may be delivered as a photocopy, printout or electronic message approved by a registrar or signed with a secure electronic signature, as the Chief Registrar directs. (c) Where an online extract signed with an approved electronic signature was received, its paper printout shall not be deemed a true copy of the extract; such a paper printout shall not be admissible in any judicial proceeding to prove rights in land."
Proves: a printed/scanned copy of an online extract is legally not a true copy. Does not prove: how a bank must treat scans in its own process (bank policy question — see E).

**Q1.8** · S04 [M] — what an extract is, and who sets its layout
HE: «”נסח“ – העתק מרישום בפנקסי המקרקעין המאושר על ידי לשכת רישום;» (reg. 1) … «(א) אלה הם הפנקסים: (1) פנקס זכויות; (2) פנקס בתים משותפים; (3) פנקס שטרות, לגבי מקרקעין בלתי מוסדרים.» (reg. 7) … «הממונה יורה על אופן ניהול הפנקסים וצורת הרישום בהם.» (reg. 8)
EN: "'Extract' — a copy of a registration in the land registers approved by a registry office" … "These are the registers: (1) register of rights; (2) register of condominiums; (3) register of deeds, for unsettled land." … "The Chief Registrar shall direct how the registers are kept and the form of registration in them."
Proves: the extract's field layout is set administratively, not by regulation. Does not prove: the actual section headings — the extraction schema for extract sections must be built from real sample extracts (section C marks those fields PROPOSED).

**Q1.9** · S01 [SN] — errors
HE: «בדקו את הנסח מיד כשאתם מקבלים אותו. - אם מצאתם טעות הגישו בקשה לתיקון בלשכה.»
EN: "Check the extract as soon as you receive it. If you found an error, submit a correction request at the registry office."

**Q1.10** · S10 [F] — look-alike documents that are not extracts
HE: «הבהרה: המידע המוצג אינו נסח רישום מאושר או העתק רישום, כמשמעותם בחוק המקרקעין, התשכ"ט–1969, בתקנות ובנהלים שעל פיו. לקבלת נסח רישום רשמי יש לפנות ללשכת רישום מקרקעין (טאבו).»
EN: "Clarification: the information displayed is not an approved registration extract or registration copy within the meaning of the Land Law 1969 and the regulations and procedures under it. To obtain an official extract, apply to the Land Registry office."
Proves: Ministry of Construction & Housing registration-status printouts must not be accepted as extracts.

**Bank usage (Mizrahi-Tefahot).**

**Q1.11** · S21 [P]
HE: «מסמכים המתייחסים לנכס אשר ישועבד לבנק (רצוי, אך אין חובה, להמציא מסמכים אלה לפני אישור עקרוני להלוואה): נסח רישום או אישור זכויות ושעבודים (בהתאם למקום הרישום של הנכס);»
EN: "Documents relating to the property to be pledged to the bank (preferably, but not mandatorily, provided before the approval in principle): a registration extract or a confirmation of rights and charges (according to where the property is registered)."

**Q1.12** · S23 [F]
HE: «נסח רישום מקורי / אישור זכויות מקורי — המטרה היא לבדוק את המצב הרישומי של הנכס, לוודא שאין עליו עיקולים או הערות מיוחדות וכד'. סוג האישור הינו בהתאם למקום הרישום של הנכס — מי מבצע? הלווה — יש לשים לב: לווה אחד יכול להציגו לבנק»
EN: "Original registration extract / original rights confirmation — the purpose is to check the registration status of the property and verify there are no attachments, special notes, etc. The type of confirmation depends on where the property is registered. Who does it? The borrower. Note: one borrower may present it to the bank."
Proves: Mizrahi wants an original (for an online extract, by Q1.6/Q1.7 that means the signed digital file) and uses it to screen for attachments and notes. Does not prove: a maximum age.

**Q1.13** · S22 [F] — extract after the warning note
HE: «בנוסף לטופס המקורי, יש להעביר לבנקאי את שני המסמכים הבאים: - נסח טאבו לאחר הרישום. חשוב - לוודא כי נרשמה הערת אזהרה גם לטובתכם - אישור על ביצוע הרישום»
EN: "In addition to the original form, give the banker these two documents: a Tabu extract after the registration — important: make sure a warning note was registered in your favor as well; and confirmation that the registration was carried out."
Proves: a second, post-registration extract is required, and it must show both the bank's and the buyers' warning notes.

**Recency inside appraisals (credit-security appraisals only).**

**Q1.14** · S35 [P] — Standard 19, s.4.10(א) and s.4.18(א)
HE: «יפורטו פרטי הזכויות הרשומות בפנקסי המקרקעין על פי נסח רישום שמועד הוצאתו, על ידי השמאי או מי מטעמו, עד חודשיים לפני מועד הקובע לשומה, ובכלל זה כל ההערות הרלוונטיות לנכס הנשום (משכנתאות, שיעבודים ועיקולים, זיקות הנאה וזכות קדימה, הערות לפי סעיף 126, הערות על הפקעות, הכרזות, הערות על זיהום קרקע וכד'). השמאי לא יוכל להסתמך על נסח שהומצא לו ע"י מקור אחר.» … «א. נסח רישום עדכני, שמועד הוצאותו עד חודשיים לפני מועד עריכת השומה.»
EN: "The registered rights shall be detailed according to a registration extract issued by the appraiser or on his behalf no more than two months before the valuation date, including all relevant notes (mortgages, charges and attachments, easements and pre-emption rights, notes under section 126, expropriation notes, declarations, soil-contamination notes, etc.). The appraiser may not rely on an extract supplied by another source." … "(a) A current registration extract issued no more than two months before the appraisal was prepared."
Proves: a 2-month recency rule and a note-category list — **but only for Standard-19 appraisals**, which by its own s.2 exclude residential-mortgage appraisals (see Q11.7). Does not prove: a general bank rule.

### B2. ILA rights confirmation — אישור זכויות רמ"י (and "הודעה על רישום זכויות בנכס")

**Purpose & issuer.** Issued by the Israel Land Authority for property not registered at the Land Registry; for property managed by a housing company / developer, the ILA instead issues a "notice on registration of rights".

**Q2.1** · S11 [P] — ILA Procedure 90.08B, s.A.1–A.2
HE: «אישור זכויות או הודעה על רישום זכויות בנכס הינו אישור המעיד על טיב הזכויות בהתבסס על נתוני תיק הנכס המתנהל ברשות מקרקעי ישראל (להלן: רמ"י). רמ"י מפיקה "אישור זכויות" עבור נכסים שאינם רשומים בלשכת רישום מקרקעין (טאבו) ו"הודעה על רישום זכויות בנכס" עבור נכסים המנוהלים ע"י חברה משכנת/גורם מאכלס/ גורם משכן/חברה קבלנית.»
EN: "A rights confirmation or a notice on registration of rights in a property certifies the nature of the rights based on the property file kept at the ILA. The ILA issues a 'rights confirmation' for properties not registered at the Land Registry (Tabu) and a 'notice on registration of rights in the property' for properties managed by a housing company / occupying body / housing body / contractor company."
Proves: when each ILA document applies. Does not prove: that a "notice" binds the housing company.

**Q2.2** · S11 [P] — s.A.3–A.6 (fee, who may ask)
HE: «הפקת "אישור זכויות" כרוכה בתשלום אגרה בהתאם לתקנות מינהל מקרקעי ישראל (אגרות) התשס"ד – 2004. הפקת "הודעה על רישום זכויות בנכס" אינה כרוכה בתשלום. ניתן להפיק אישור זכויות / הודעה על רישום זכויות לכל בעל עניין, המגיש בקשה דרך האזור האישי (רמ"י שלי) ללא הצגת ייפוי כוח מטעם בעל הזכויות בנכס. בקשות מייצגים המוגשות באמצעות ערוצי פניה אחרים מחייבות הצגת יפוי כח מטעם בעל זכויות בנכס. ניתן להפיק אישור זכויות / הודעה על רישום זכויות בנכס ללא אישור בעל הזכויות בנכס כאשר הבקשה הוגשה על ידי הבנק אשר לטובתו ניתנה התחייבות לרישום משכנתא, וזאת לאחר הצגת יפוי כח מהבנק לידי הגורם המבקש מטעמו.»
EN: "Issuing a 'rights confirmation' involves a fee under the ILA (Fees) Regulations 2004. Issuing a 'notice on registration of rights' is free. A confirmation/notice may be issued to any interested party applying through the personal area ('רמ"י שלי') without a power of attorney from the rights holder; representatives applying through other channels must present a power of attorney. A confirmation/notice may be issued without the rights holder's consent when requested by the bank in whose favor an undertaking to register a mortgage was given, upon presenting the bank's power of attorney to its agent."

**Q2.3** · S11 [P] — s.C.2: checks and mandatory remarks (this is the field list)
HE: «א. האם הנכס אינו רשום בלשכת רישום המקרקעין ואינו ניתן לרישום בלשכת רישום המקרקעין … אם הנכס ניתן לרישום בלשכת רישום המקרקעין, באישור הזכויות/הודעה תצויין ההערה שלהלן: "היות והנכס ניתן לרישום בלשכת רישום המקרקעין, הרשות לא תבצע בנכס כל פעילות, לרבות מתן התחייבות לרישום משכנתא, העברת זכויות וכו' ועל בעלי הזכויות לפעול לרישום הנכס כדין לאלתר". ב. אם פג תוקפו של ההסכם תתווסף לאישור זכויות / הודעה על רישום זכויות בנכס ההערה שלהלן: "היות ופג תוקפם של המועדים הקבועים בהסכם, רמ"י לא תבצע בנכס כל פעילות, לרבות מתן התחייבות לרישום משכנתא, העברת זכויות וכו' …". ג. האם קיימות הערות משפטיות (טיפול משפטי, כינוס נכסים, עיקולים, צווי מניעה, משכון, צווים משפטיים, שעבוד) … ד. האם רשומה התחייבויות לרישום משכנתא. … ה. האם על פי מסמכי החוזה או דוחות פיקוח קיימת אינדיקציה ל: שימוש חורג, חריגות בנייה, פלישה. … ו. האם קיימים חובות. ז. האם קיימת בקשה להעברת זכויות. … אם אחד מהסעיפים מתקיים, יש לציין זאת באישור הזכויות.»
EN: "(a) Whether the property is not registered and not registrable at the Land Registry … if it is registrable, the confirmation/notice shall state: 'Since the property can be registered at the Land Registry, the Authority will not perform any activity in it, including giving an undertaking to register a mortgage, transferring rights, etc., and the rights holders must register the property lawfully forthwith.' (b) If the agreement has expired, this remark is added: 'Since the dates set in the agreement have expired, the ILA will not perform any activity in the property, including giving an undertaking to register a mortgage, transferring rights, etc. …' (c) Whether there are legal notes (legal handling, receivership, attachments, injunctions, pledge, court orders, charge) … (d) Whether undertakings to register a mortgage are recorded … (e) Whether contract documents or inspection reports indicate non-conforming use, building deviations, encroachment … (f) Whether there are debts. (g) Whether there is a pending transfer-of-rights request … If any of these exists, it shall be stated in the rights confirmation."
Proves: the remark/flag fields that can appear on an ILA rights confirmation and the exact wording of two blocking remarks. Does not prove: the layout of owner/property sections.

**Q2.4** · S11 [P] — signing authority and turnaround
HE: «חתימה על אישור זכויות / הודעה על רישום זכויות בנכס — ראש תחום בכיר/ סגנו/מרכז בכיר/מרכז שירות/נציג שירות במוקד (חטיבת השירות); מקדם עסקאות (חטיבה עסקית)» … «SLA לסיום התהליך: 3 ימי עבודה במגזר העירוני; 7 ימי עבודה במגזר החקלאי»
EN: "Signature on a rights confirmation / notice: senior field head / deputy / senior coordinator / service coordinator / service representative at the call centre (Service Division); transactions promoter (Business Division)." … "SLA to complete the process: 3 working days in the urban sector; 7 working days in the agricultural sector."
Proves: the document is signed by an ILA official with one of these roles. Does not prove: the signature type (wet/electronic).

**Q2.5** · S13 SECONDARY [SN] — printout vs. binding confirmation (claimed ILA wording; verify on gov.il)
HE: «בשונה מ"אישור זכויות" רשמי, פלט מחשב שהופק ממאגר המידע של רשות מקרקעי ישראל (רמ"י) אינו מהווה ראיה לתוכנו, ולא ניתן להסתמך עליו כבעל תוקף משפטי מחייב, שכן הוא לא נחתם על ידי גורם מורשה מטעם רמ"י, ותיק הזכויות המנוהל ברמ"י לא נבדק באופן פרטני נכון למועד הגשת הבקשה.»
EN: "Unlike an official 'rights confirmation', a computer printout produced from the ILA database is not evidence of its content and cannot be relied upon as legally binding, because it was not signed by an authorized ILA official and the rights file was not individually reviewed as of the request date."
Status: SECONDARY only. Useful as a rule candidate ("reject ILA database printouts"), but must be confirmed on the ILA page.

**Q2.6** · S12 [P] — ILA issues a rights confirmation together with a mortgage undertaking
HE: «יש להפיק ללקוח ולגורם המלווה כתב התחייבות לרישום משכנתא ואישור זכויות ללא תשלום אגרה.»
EN: "An undertaking to register a mortgage and a rights confirmation shall be issued to the customer and the lender, without a fee."

**Q2.7** · S15 [P, official translation] — Directive 451 s.5a (ILA development contract)
EN: "In a transaction involving a loan for housing on land belonging to the Israel Land Administration … that is executed on the basis of a development contract between the borrower and the Administration, the banking corporation shall inform the guarantors when they sign the guarantee that … a situation might arise in which it will not be possible to attach the land, and as a result the guarantors' signatures on the guarantee agreement could be the sole and exclusive security for repayment of the loan."
HE (S14): «…ייתכן מצב שלא ניתן יהיה להיפרע מהמקרקעין, ועקב כך חתימת הערבים על חוזה הערבות עלולה להיות הבטוחה הבלעדית והיחידה להחזרת ההלוואה.»

**Q2.8** · S35 [P] — Standard 19 s.4.10(ב) (credit-security appraisals): recency of ILA/housing-company confirmations
HE: «אם הנכס בבעלות מינהל מקרקעי ישראל או חברה משכנת והזכויות המוצעות כבטוחה לאשראי טרם נרשמו במרשם המקרקעין, יפורטו הפרטים המופיעים באישור הזכויות עדכני שמועד הוצאתו עד שלושה חודשים לפני מועד עריכת השומה. … אם לאחר 21 יום לא נתקבל האישור, ירשם בשומה כי לא הומצא אישור זכויות עדכני.»
EN: "If the property is owned by the ILA or a housing company and the rights offered as security have not yet been registered, the details in a current rights confirmation issued no more than three months before the appraisal shall be detailed. … If the confirmation was not received after 21 days, the appraisal shall state that no current rights confirmation was provided."
Proves: a 3-month recency convention within Standard-19 appraisals. Does not prove: an ILA validity period (none found).

### B3. Rights confirmation from a housing company / developer (בית משותף לא רשום)

No official template, definition or validity period was found for a housing company's own rights confirmation (see D). What the sources do establish:

**Q3.1** · S21 [P] — collateral package when rights are recorded at the ILA and/or a housing company in the mortgagor's name
HE: «2. נכס שהזכויות בו רשומות על שם המשעבד ברשות מקרקעי ישראל ("רמ"י") ו/או ב"חברה משכנת" — א. שטר משכון חתום בידי בעל הלווה/משעבד אחר. ב. הודעת מישכון חתומה בידי הלווה/משעבד אחר ואישור על רישומה ברשם המשכונות. ג. יפוי כח בלתי חוזר מאושר ע"י נוטריון. ד. טופס שעבוד דירתי חתום בידי הלווה/משעבד אחר. ה. התחייבות לרישום משכנתא של רמ"י או של החברה המשכנת.»
EN: "2. Property whose rights are recorded in the mortgagor's name at the ILA and/or a 'housing company' — (a) pledge deed signed by the borrower/other mortgagor; (b) pledge notice signed by the borrower/other mortgagor and confirmation of its registration at the Registrar of Pledges; (c) irrevocable power of attorney certified by a notary; (d) residential-charge form signed by the borrower/other mortgagor; (e) undertaking to register a mortgage by the ILA or by the housing company."

**Q3.2** · S21 [P] — second-hand purchase where rights are recorded at the ILA/housing company in the seller's name
HE: «4. נכס שהזכויות בו רשומות ברשות מקרקעי ישראל (רמ"י) או בחברה משכנת על שם המוכר ("יד שנייה") — א. ב. ג. כמפורט בסעיף 2 לעיל. ד. התחייבות לרישום משכנתא של החברה המשכנת ו/או של המוכר. ה. הודעת מישכון חתומה בידי בעל הזכויות בנכס ואישור על רישומה ברשם המשכונות. ו. טופס שעבוד דירתי חתום בידי בעל הזכויות בנכס.»
EN: "4. Property whose rights are recorded at the ILA or a housing company in the seller's name (second-hand) — (a)–(c) as in section 2; (d) undertaking to register a mortgage by the housing company and/or the seller; (e) pledge notice signed by the rights holder and confirmation of its registration at the Registrar of Pledges; (f) residential-charge form signed by the rights holder."

**Q3.3** · S21 [P] — first-hand purchase from a housing company
HE: «5. ברכישת נכס "יד ראשונה" מחברה משכנת — א. ב. ג. ד. כמפורט בסעיף 2 לעיל. ה. התחייבות לרישום משכנתא חתומה בידי הקבלן ובידי הבעלים הרשומים של המקרקעין. ו. רישום הערת אזהרה לטובת הבנק בגין ההתחייבויות הנ"ל. ז. ערבות של רוכשי דירות לפי "חוק המכר (דירות) (הבטחת השקעות של רוכשי דירות) התשל"ה - 1974" המוסבת לבנק או בטוחה אחרת לפי אותו חוק. ח. פנקס שוברי התשלום שהונפק על ידי הבנק המלווה (בהלוואות לרכישת דירה מקבלן בפרויקט המלווה על ידי תאגיד בנקאי על פי הסכם ליווי שנחתם לאחר 1.6.2008).»
EN: "5. First-hand purchase from a housing company — (a)–(d) as in section 2; (e) undertaking to register a mortgage signed by the contractor and by the registered owners of the land; (f) registration of a warning note in favor of the bank for those undertakings; (g) a Sale Law purchaser guarantee endorsed to the bank, or another security under that law; (h) the payment-voucher booklet issued by the accompanying bank (for projects accompanied under an agreement signed after 1.6.2008)."

**Q3.4** · S12 [P] — ILA does not issue the mortgage undertaking where a housing company manages the property
HE: «כאשר הנכס מנוהל על ידי רשות מקרקעי ישראל, ואינו מנוהל על ידי חברה משכנת/חברה קבלנית (למעט החברות המפורטות בנספח 2) או רשום בלשכת רישום מקרקעין, מנפיקה הרשות "כתב התחייבות לרישום משכנתא" …»
EN: "Where the property is managed by the ILA, and is not managed by a housing/contractor company (except the companies listed in Appendix 2) or registered at the Land Registry, the Authority issues an 'undertaking to register a mortgage' …"
Proves: for housing-company-managed property the undertaking normally comes from the company (consistent with Q3.1–Q3.3). Does not prove: the content of a company confirmation. (Appendix 2 — the list of companies — was not reproduced in the PDF.)

**Q3.5** · S35 [P] — appraisers must obtain a confirmation "ממינהל מקרקעי ישראל או מחברה משכנת" (Standard 19 s.4.10(ב), see Q2.8).

### B4. New-build securities — Sale Law guarantee, voucher booklet, exclusion letter

**Q4.1** · S29 [M] — s.2: the 7% rule and the five permitted securities
HE: «לא יקבל מוכר מקונה, על חשבון מחיר הדירה, סכום העולה על שבעה אחוזים מהמחיר, אלא אם עשה אחת מאלה … (1) מסר לקונה ערבות בנקאית או ערבות מנותן ערבות אחר להבטחת החזרתם של כל הכספים ששילם לו הקונה על חשבון המחיר, למעט רכיב המע״מ … (2) ביטח את עצמו אצל מבטח שאישר לעניין זה הממונה על שוק ההון … והקונה צויין כמוטב על פי פוליסת הביטוח ודמי הביטוח שולמו מראש … (3) שעבד את הדירה, או חלק יחסי מהקרקע שעליה היא נבנית, במשכנתה ראשונה לטובת הקונה או לטובת חברת נאמנות שאישר לכך השר … (4) רשם לגבי הדירה, או לגבי חלק יחסי של הקרקע שעליה היא נבנית, הערת אזהרה על מכירת הדירה בהתאם להוראות סעיף 126 לחוק המקרקעין … ובלבד שלא נרשמו לגביהם שעבוד, עיקול או זכות של צד שלישי שיש להם עדיפות על ההערה; (5) העביר על שם הקונה את הבעלות או זכות אחרת בדירה …»
EN: "A seller shall not receive from a buyer, on account of the price, more than seven percent of the price unless he did one of these: (1) gave the buyer a bank guarantee or a guarantee from another guarantor securing repayment of all money paid on account of the price, excluding the VAT component …; (2) insured himself with an insurer approved by the Capital Market Commissioner …, with the buyer named as beneficiary and the premium prepaid; (3) charged the apartment, or a proportional share of the land, by a first mortgage in favor of the buyer or an approved trust company …; (4) registered a warning note on the sale of the apartment under s.126 of the Land Law …, provided no charge, attachment or third-party right with priority over the note is registered; (5) transferred ownership or another right in the apartment to the buyer …"

**Q4.2** · S29 [M] — s.2א1: written notice to the buyer
HE: «(א) לא ימכור מוכר דירה לקונה, אלא אם כן הודיע לקונה בכתב, במועד חתימת חוזה המכר, על זכותו על פי חוק זה להבטחת הכספים ששולמו ועל הדרכים שנקבעו לפי החוק לעניין זה. (ב) מוכר שלא התקשר עם תאגיד בנקאי או מבטח בהסכם למתן ליווי פיננסי, יודיע על כך לקונה בכתב, עד מועד חתימת חוזה המכר …»
EN: "(a) A seller shall not sell an apartment unless he notified the buyer in writing, at signing, of the buyer's right under this law to have payments secured and of the prescribed ways. (b) A seller who did not contract with a bank or insurer for financial accompaniment shall notify the buyer of this in writing by the signing date …"

**Q4.3** · S29 [M] — s.3ב: voucher booklet
HE: «התאגיד המלווה יפיק פנקס שוברים לתשלום בעבור כל דירה בפרויקט הבנייה, ימסור אותו למוכר ויפקיד תשלומים בעבור הדירה, לרבות תשלומים שהעביר תאגיד שנתן לקונה הלוואה לרכישת דירה, לחשבון הליווי באמצעות פנקס השוברים בלבד; השוברים יכללו פרטים כפי שיקבע המפקח על הבנקים או הממונה על שוק ההון … תאגיד מלווה ימציא ערבות בנקאית או פוליסת ביטוח או ערבות מנותן ערבות אחר בשל הסכום ששילם הקונה לפי הסדר השוברים, למעט רכיב המע״מ … בתוך 14 ימי עסקים מיום ששולם …»
EN: "The accompanying institution shall issue a voucher booklet for each apartment, give it to the seller, and deposit payments for the apartment — including payments transferred by the buyer's mortgage lender — into the accompaniment account only through the voucher booklet; the vouchers shall include details set by the Supervisor of Banks or the Capital Market Commissioner … The accompanying institution shall provide a bank guarantee, insurance policy or other guarantee for the amount paid under the voucher arrangement, excluding VAT, within 14 business days of payment …"
Proves: mortgage money must also go through the vouchers; a guarantee must follow within 14 business days. Does not prove: the voucher field list (set by the Supervisor; not retrieved — see D).

**Q4.4** · S29 [M] — s.2ג: the "exclusion letter" (הודעה בדבר מחיקת רישום שעבוד)
HE: «(ב) מוכר יפנה בכתב לתאגיד בנקאי או למבטח או לנותן ערבות אחר, לפי העניין, בדרישה שימציא הודעה בכתב, בנוסח שבתוספת, ולפיה שעבוד או התחייבות לשעבוד, שניתנו לטובת התאגיד הבנקאי או המבטח לא ימומשו מתוך הדירה ורישומם יימחק, בהתאם לתנאים האמורים בהודעה …; פנייה כאמור תיעשה בתוך 30 ימים מאחד מאלה: (1) ממועד התשלום הראשון ששילם קונה באמצעות פנקס שוברים … (ג) … ימסור לו התאגיד הבנקאי או המבטח או נותן הערבות האחר את ההודעה בתוך 30 ימים ממועד פניית המוכר אליו; … ועם קבלת ההודעה … יעבירה לקונה.»
EN: "(b) The seller shall apply in writing to the bank, insurer or other guarantor demanding a written notice, in the form in the Schedule, that a charge or undertaking to charge given in its favor will not be enforced against the apartment and its registration will be deleted, under the conditions in the notice …; the application shall be made within 30 days of (1) the buyer's first voucher payment … (c) … the bank/insurer/guarantor shall deliver the notice within 30 days of the seller's application; … and on receipt the seller shall pass it to the buyer."
Proves: the legal basis, timing and core content of the exclusion letter. Does not prove: its exact wording/fields (the Schedule form is "(הושמטה)" on Wikisource — see D).

**Q4.5** · S30 [M] — prescribed bank-guarantee form (the field list)
HE: «תאריך … לכבוד: … (להלן – הרוכש). כללי — פרטי הדירה – גוש, חלקה; תכנית, מגרש; מספר הבניין, מספר הדירה (להלן – הדירה). פרטי המוכר … (להלן – המוכר). פרטי הבנק מוציא הערבות … מהות הערבות — הרינו ערבים בזה כלפיכם בסכום של …, ששילמתם למוכר על חשבון מחיר הדירה (להלן – סכום הערבות) … הפרשי הצמדה — … א. צמוד למדד התשומות בבנייה למגורים … ב. צמוד למדד המחירים לצרכן … ג. צמוד לשער היציג של … (מטבע החוץ המתאים) … "מדד הבסיס" – המדד הידוע ביום תשלום הכספים למוכר. מועד התשלום — … בתוך 60 ימים לאחר קבלת דרישתכם הראשונה בכתב ב… … פקיעת הערבות … המחאת הזכויות על פי הערבות — … אם נתתם לנו הוראה בלתי חוזרת, שאישרנו, לשלם מהסכום המגיע לכם על פי ערבות זו לתאגיד בנקאי או למבטח, אשר נתנו לכם הלוואות לצורך רכישת הדירה … אנו נעביר תחילה את הסכומים האמורים המגיעים למוסד הפיננסי … ערבות לשניים או יותר … רכיב המע״מ — הסכום הנקוב בערבות זו אינו כולל את מס הערך המוסף … חתימה וחותמת הבנק»
EN: "Date … To: … (the buyer). General — apartment details: block, parcel; plan, plot; building number, apartment number. Seller details. Details of the issuing bank. Nature of guarantee — we guarantee to you the sum of …, which you paid the seller on account of the price … Indexation — (a) residential construction-inputs index; (b) consumer price index; (c) representative rate of … (foreign currency) … 'base index' = the index known on the day the money was paid to the seller. Payment date — within 60 days after receiving your first written demand at … Expiry of the guarantee … Assignment — … if you gave us an irrevocable instruction, approved by us, to pay from the amount due under this guarantee to a bank or insurer that lent you money to buy the apartment … we will first transfer the amounts due to that financial institution … Guarantee to two or more … VAT component — the amount does not include VAT … Bank signature and stamp."
Also (expiry events, same form): the guarantee lapses, among other cases, when the bank receives an extract showing ownership/lease registered to the buyer free of charges, or an extract showing a prior-ranking warning note for the buyer (with the bank's written exclusion of its own charge), or, on ILA land, a signed ILA lease contract or ILA confirmation.
Proves: a complete field list for a Sale Law bank guarantee and the mechanism by which it is "endorsed" to the mortgage lender. Does not prove: guarantee numbering or barcodes.

**Q4.6** · S15 [P, official translation] — Directive 451 ss.7, 7a
EN: "7. Before transferring the loan money to the seller in a firsthand purchase (a direct purchase from the contractor), the banking corporation shall act as follows: (a) When a banking corporation finances the seller in any way (such as a loan or guarantee), it must ascertain that the borrower has received from the seller of the apartment the statutory collateral required under the Sale (Apartments) (Assurance of Investments of Persons Acquiring Apartments) Law, 5734–1974 … (b) If there is no business connection between the banking corporation and the seller …, the banking corporation shall inform the borrower of the existence of the Sale (Apartments) Law and what this requires of the seller. 7a. A banking corporation shall not refuse a request by the purchaser of a residential apartment to endorse a guarantee in accordance with the Sale (Apartments) Law on behalf of another banking corporation that has extended credit to that purchaser."
HE (S14): «7. לפני העברת כספי ההלוואה למוכר ברכישה מיד ראשונה, יפעל התאגיד הבנקאי כלהלן: (א) כאשר תאגיד בנקאי מממן את המוכר בדרך כלשהי (כגון בהלוואה או בערבות), עליו לוודא כי הלווה קיבל ממוכר הדירה בטוחות כנדרש על פי חוק המכר (דירות) …»

**Q4.7** · S21 [P] — Mizrahi
HE: «הבנק ידרוש מלווה שקנה דירה חדשה להציג בפניו הוכחה שקיבל בטוחה כזאת או שקיבל התחייבות להמצאתה. הבנק אף רשאי לדרוש כי ערבות על פי החוק תוסב לבנק; על הלווה לוודא שהוא מקבל את הבטוחה המגיעה לו.» … «בפרויקטים שהסכם הליווי לגביהם נחתם לאחר 1.6.2008, מונפק על ידי הבנק המלווה פנקס שוברי תשלום, אשר רק באמצעותו ניתן לבצע את התשלומים לרכישת הדירה כולל התשלומים על חשבון ההלוואה.»
EN: "The bank will require a borrower who bought a new apartment to show proof that he received such a security or an undertaking to provide it. The bank may also require that a guarantee under the law be endorsed to the bank." … "In projects whose accompaniment agreement was signed after 1.6.2008, the accompanying bank issues a voucher booklet, and only through it may payments for the apartment be made, including payments on account of the loan."

**Q4.8** · S23 [F] — Mizrahi checklist for buying from a contractor
HE: «התחייבות לרישום משכנתא חתומה בידי הקבלן — החתמת המוכר על טופס ייעודי שתקבלו מהבנק — מי מבצע? הלווה מול הקבלן. ההתחייבות תחתם על-ידי הקבלן בפני עו"ד. הסבת ערבות, התחייבות להמצאת ערבות ומכתב החרגה — מסמכים שיש להמציא מהקבלן … העברת שוברי תשלום — בפרויקט המלווה על ידי גוף פיננסי – התשלום לקבלן מתבצע באמצעות שוברי תשלום. את פנקס השוברים שתקבלו מהקבלן יש להציג לבנקאי»
EN: "Undertaking to register a mortgage signed by the contractor — the seller signs a dedicated form you receive from the bank; the contractor signs it before a lawyer. Endorsement of guarantee, undertaking to provide a guarantee, and exclusion letter — documents to obtain from the contractor … Payment vouchers — in a project accompanied by a financial body, payment to the contractor is made by vouchers; show the voucher booklet you receive from the contractor to the banker."

**Q4.9** · S28 [SN] — Mizrahi voucher validation (an authenticity check for vouchers in Mizrahi-accompanied projects)
HE: «רוכשי דירות בפרויקטים שנבנו בלווי פיננסי של מזרחי-טפחות מעבירים לקבלן תשלומים באמצעות שוברים. כאן ניתן לאשר ולאמת את פרטי הפרויקט - מספר חשבון ושם הפרויקט - המופיעים בשוברי התשלום. … נא למלא מספר חשבון בן 6 ספרות … נא למלא מספר סניף בן 3 ספרות … שם פרוייקט הבנייה»
EN: "Buyers in projects financially accompanied by Mizrahi-Tefahot pay the contractor with vouchers. Here you can confirm and verify the project details — account number and project name — printed on the vouchers … enter a 6-digit account number … enter a 3-digit branch number … construction project name."
Proves: vouchers carry account no. (6 digits), branch no. (3 digits) and project name, verifiable online for Mizrahi projects. Does not prove: a cross-bank verification service.

**Q4.10** · S32 [SN] — seller's report to the Ministry
HE: «על פי התקנות כל מוכר דירה חדשה – קבלן, יזם וכדומה – ימסור לממונה במשרד הבינוי והשיכון הצהרה על מכירת הדירה ועל סוג הבטוחה שניתנה לקונה לפי סעיף 2 לחוק: ערבות בנקאית, פוליסת ביטוח, שעבוד במשכנתא ראשונה, הערת אזהרה, רישום זכויות. על ההצהרה להימסר לא יאוחר מ-40 ימים ממועד חתימת חוזה המכר.»
EN: "Under the regulations every seller of a new apartment shall submit to the Supervisor at the Ministry a declaration on the sale and on the type of security given to the buyer under s.2: bank guarantee, insurance policy, first mortgage, warning note, registration of rights. The declaration must be submitted within 40 days of signing the sale contract."

**Q4.11** · S29 [M] — s.2ב: ILA land — security only until completion, possession and an ILA contract
HE: «היתה הקרקע שעליה הדירה הנמכרת ממקרקעי ישראל … לא יהא המוכר חייב להבטיח את כספי הקונה לפי סעיף 2 אלא לתקופה שתסתיים בהתמלא כל אלה: (1) הושלמה בניית הדירה בהתאם לחוזה המכר; (2) נמסרה ההחזקה בדירה לקונה; (3) נחתם חוזה בין הקונה לבין רשות מקרקעי ישראל …»
EN: "If the land is Israel Land …, the seller must secure the buyer's money only until all of these are met: (1) construction completed per the contract; (2) possession delivered; (3) a contract signed between the buyer and the ILA …"

### B5. Warning note — הערת אזהרה (buyer's note and bank's note)

**Q5.1** · S05 [M] — Land Law s.126
HE: «(א) הוכח להנחת דעתו של הרשם כי בעל מקרקעין, או בעל זכות שכירות, שאילה, זיקת הנאה, זכות קדימה או משכנתה, התחייב בכתב לעשות בהם עסקה, או להימנע מעשות בהם עסקה, ירשום הרשם, על פי בקשת מי שהתחייב או מי שזכאי לפי ההתחייבות (להלן – הזכאי), הערה על כך; לענין זה אין נפקא מינה אם ההתחייבות היתה בהסכם, בהרשאה בלתי חוזרת או במסמך אחר, ואם היתה מפורשת או משתמעת, מוחלטת או מותנית. (ב) נרשמה ההערה על פי בקשת הזכאי בלבד, יודיע הרשם מיד על רישומה למי שהתחייב כאמור.»
EN: "(a) Where the registrar is satisfied that an owner of land, or holder of a lease, loan, easement, pre-emption right or mortgage, undertook in writing to make a transaction in it or to refrain from one, the registrar shall, at the request of the obligor or the person entitled under the undertaking (the beneficiary), register a note; it does not matter whether the undertaking was in an agreement, an irrevocable power of attorney or another document, express or implied, absolute or conditional. (b) If registered at the beneficiary's request only, the registrar shall promptly notify the obligor."

**Q5.2** · S05 [M] — Land Law s.127 (effect)
HE: «(א) נרשמה הערת אזהרה וכל עוד לא נמחקה, לא תירשם עסקה הסותרת את תוכן ההערה, אלא בהסכמת הזכאי או לפי צו בית המשפט. (ב) נרשמה הערת אזהרה ולאחר מכן הוטל עיקול … או שניתן צו לקבלת נכסים בפשיטת רגל או צו פירוק … הרי כל עוד לא נמחקה ההערה, לא יהיה בכל אלה כדי לפגוע בזכויות הזכאי הנובעות מההתחייבות נשוא ההערה …»
EN: "(a) While a warning note is registered and not deleted, no transaction contradicting it shall be registered, except with the beneficiary's consent or by court order. (b) If after the note an attachment was imposed … or a receiving order in bankruptcy or a winding-up order was given …, as long as the note is not deleted these shall not prejudice the beneficiary's rights under the undertaking …"
Proves: why the bank wants its own note (undertaking to register a mortgage) and the buyer's note registered before money moves.

**Q5.3** · S05 [M] — s.128 (note on need for consent)
HE: «הוכח, להנחת דעתו של הרשם, כי עשיית עסקה בידי בעל המקרקעין או בעל זכות במקרקעין מותנית – על פי חיקוק, על פי צו של בית משפט או על פי התחייבות בכתב של הבעל – בהסכמתו של צד שלישי, ירשום הרשם, לפי בקשת הצד השלישי, הערה על כך.»
EN: "Where a transaction by the owner is conditional — by enactment, court order or the owner's written undertaking — on a third party's consent, the registrar shall, at the third party's request, register a note."

**Q5.4** · S04 [M] — reg. 21 (how a warning note is registered)
HE: «(א) רישום הערת אזהרה לפי סעיף 126 לחוק יהיה על פי בקשה חתומה על ידי המתחייב או הזכאי, המאומתת בידי עורך דין או רשם, בדרך שמאמתים שטר עסקה; הבקשה תוגש לרישום בלשכה שרשומים בה המקרקעין … (ב) לבקשה יצורפו מסמכים אלה: (1) התחייבות בכתב כמשמעותה בסעיף 126 לחוק; הוגשה הבקשה בידי המתחייב והזכאי יחד, רשאי הממונה לפטור את המבקשים מן החובה לצרף התחייבות כאמור …; (2) אין המתחייב בעל הזכות הרשומה – כתב הסכמה לרישום ההערה, בחתימת בעל הזכות הרשומה, המאומת בידי עורך דין או רשם; (3) מסמכים המוכיחים את זהות כל מי שחתם על ההתחייבות, לרבות מסמכי תאגיד …»
EN: "(a) A s.126 warning note is registered on an application signed by the obligor or the beneficiary, verified by a lawyer or registrar in the manner a transaction deed is verified, filed at the office where the land is registered. (b) Attach: (1) the written undertaking; if obligor and beneficiary apply jointly, the Chief Registrar may waive it; (2) if the obligor is not the registered right holder — the registered holder's written consent, verified by a lawyer or registrar; (3) identity documents of everyone who signed, including corporate documents."

**Q5.5** · S06 [SN] — the gov.il service
HE: «שירות זה מאפשר לרשום או לבטל הערת אזהרה על התחייבות לעשיית עסקה, הימנעות מעשיית עסקה, הערה על צורך בהסכמה, התחייבות במסגרת תמ"א 38.»
EN: "This service allows registering or cancelling a warning note on an undertaking to make a transaction, to refrain from a transaction, a note on need for consent, or an undertaking under TAMA 38."

**Q5.6** · S08 [SN][M] — the official application form (field list)
HE: «בקשה לרישום הערת אזהרה ☐ לפי סעיף 126 לחוק המקרקעין, תשכ"ט- 1969 ☐ לפי סעיף 128 לחוק המקרקעין, תשכ"ט- 1969 … 1. תיאור המקרקעין … ☐ לפי סעיף 126 - על התחייבות לעשות עסקה ☐ לפי סעיף 126 - על הימנעות מעשיית עסקה ☐ לפי סעיף 128 - על הצורך בהסכמה 3. פרטי מי שהתחייב ופירוט זכותו במקרקעין — שם משפחה/שם תאגיד שם פרטי סוג זיהוי** מס' זיהוי כתובת — מהות הזכות במקרקעין החלקים בזכות 4. פרטי הזכאי שלטובתו ניתנה ההתחייבות — שם משפחה/שם תאגיד שם פרטי סוג זיהוי** מס' זיהוי כתובת … 5. המסמכים המצורפים ☐הסכם ☐ ייפוי כוח בלתי חוזר ☐ מסמך אחר … ** ת.ז,. דרכון, מס' חברה וכד' … אישור עו"ד על בדיקת מסמכי תאגיד»
EN: "Application to register a warning note ☐ under s.126 ☐ under s.128 … 1. Description of the land … ☐ s.126 undertaking to make a transaction ☐ s.126 refraining ☐ s.128 need for consent. 3. Details of the obligor and his right in the land — surname/corporate name, first name, ID type**, ID number, address — nature of the right, shares in the right. 4. Details of the beneficiary — surname/corporate name, first name, ID type**, ID number, address … 5. Attached documents ☐ agreement ☐ irrevocable power of attorney ☐ other … ** ID card, passport, company number, etc. … Lawyer's confirmation of checking corporate documents."
Proves: the form's fields. Caveat: copy hosted by a third party.

**Q5.7** · S09 [P][M] — procedure: warning note "with the consent of all parties" for an undertaking to register a mortgage
HE: «ד. כאשר מוגשת בקשה לרישום הערת אזהרה בהסכמת כל הצדדים בגין התחייבות לרישום משכנתה, אין צורך לצרף את כתב ההתחייבות. ככל שיצורף כתב ההתחייבות, הוא יישמר כמסמך סרוק בתיק הרישום, אך בכל מקרה הוא לא ייבדק ע"י לשכת הרישום, ולא ייחתם ע"י לשכת הרישום. ה. כאשר מצורף טופס הסכמת בעלים לרישום הערת אזהרה בגין התחייבות לרישום משכנתה, ניתן לקבל טופס הסכמה נפרד מהבעלים הרשום בכפוף לשני תנאים מצטברים: (1) על טופס ההסכמה להיות מאומת בידי עו"ד לפי תקנה 21ב(2) לתקנות המקרקעין …; (2) ניתן לקשור את הטופס באופן וודאי לטופס הבקשה (בנק, נכס, סכום וכד').»
EN: "(d) When an application to register a warning note with all parties' consent for an undertaking to register a mortgage is filed, the undertaking need not be attached; if attached, it is kept scanned but is not checked or stamped by the registry. (e) A separate owner's consent form is accepted if (1) verified by a lawyer under reg. 21(b)(2) …; and (2) it can be linked with certainty to the application (bank, property, amount, etc.)."
Proves: bank warning notes are typically registered on a joint-consent application; the registry does not check the underlying undertaking — so the bank must. Linking keys: bank, property, amount.

**Q5.8** · S22 [F] — Mizrahi (second-hand purchase)
HE: «רישום הערת אזהרה לטובת הבנק — על הטופס ששמו "בקשה לרישום הערת אזהרה בגין התחייבות לרישום משכנתא בהסכמת כל הצדדים" צריכים לחתום המוכרים, ועורך דינם צריך לאמת את חתימתם. לאחר החתימה, עורך הדין ירשום הערת אזהרה לטובת בנק מזרחי-טפחות. יש להחזיר לבנקאי בסניף את הטופס המקורי החתום על-ידי המוכרים ומאומת על-ידי עורך הדין. הרישום בטאבו נעשה אונליין.»
EN: "Warning note in favor of the bank — the sellers sign the form 'application to register a warning note for an undertaking to register a mortgage with the consent of all parties', and their lawyer verifies their signatures. The lawyer then registers a warning note in favor of Mizrahi-Tefahot. Return to the banker the original form signed by the sellers and verified by the lawyer. Registration at the Tabu is done online."

**Q5.9** · S21 [P] — Mizrahi (property registered at Tabu in the seller's name)
HE: «3. נכס שרשום בטאבו על שם המוכר ("יד שנייה") — א. ב. ג. ד. כמפורט בסעיף 2 לעיל. ה. התחייבות לרישום משכנתא חתומה בידי המוכר. ו. רישום הערות אזהרה לגבי הנכס: לטובת הלווים - בגין הסכם הרכישה; לטובת הבנק - בגין התחייבות לרישום משכנתא של המוכר.»
EN: "3. Property registered at the Tabu in the seller's name (second-hand) — (a)–(d) as in section 2 [pledge deed, pledge notice + registration at the Registrar of Pledges, notarized irrevocable POA, residential-charge form]; (e) undertaking to register a mortgage signed by the seller; (f) warning notes on the property: in favor of the borrowers — for the purchase agreement; in favor of the bank — for the seller's undertaking to register a mortgage."

**Q5.10** · S09 [P][M] — procedure 1.3.2.13 (when the mortgage replaces the bank's note)
HE: «נרשמה הערת אזהרה בגין התחייבות לרישום משכנתה, ולאחר מכן מוגשת בקשה לרישום זכות משכנתה באותם מקרקעין ובין אותם צדדים, וסכום החוב שונה (גבוה או נמוך) מזה המצוין בהתחייבות - ביטול הרישום של הערת האזהרה ייעשה רק לאחר קבלת הסכמת בעל המשכנתה.»
EN: "Where a warning note for an undertaking to register a mortgage was registered, and later a mortgage is filed on the same land between the same parties with a different amount (higher or lower) than in the undertaking — the warning note is deleted only with the mortgagee's consent."

**Q5.11** · S32 [SN] — a warning note takes effect immediately (Sale Law context)
HE: «שימו לב כי הערת אזהרה נכנסת לתוקף מיד וכי אינה תלויה בתנאים נוספים כגון התקדמות הבנייה, בניית המחיצות וכדומה.»
EN: "Note that a warning note takes effect immediately and does not depend on further conditions such as construction progress, building of partitions, etc."

### B6. Mortgage registration at the Land Registry — רישום משכנתה / שטר משכנתה

**Q6.1** · S07 [SN]
HE: «בקשה לרישום משכנתה — שירות זה מאפשר רישום משכנתה על בעלי זכות הרשומה בפנקסי המקרקעין.»
EN: "Application to register a mortgage — this service allows registering a mortgage over holders of a right registered in the land registers."
Proves: a Land Registry mortgage requires a right registered in the land registers; otherwise the bank uses an undertaking + warning note and/or a pledge (B7, B8).

**Q6.2** · S24 [F] — Mizrahi: what the mortgage deed contains
HE: «שטר משכנתא נועד לביצוע שיעבוד הנכס לבנק לפי הסכם ההלוואה. השטר מופק לצורך רישום משכנתא על הנכס בטאבו. השטר מפרט את פרטי הנכס הממושכן, פרטי הממשכן, הבנק שלטובתו נרשמה המשכנתא והתנאים המיוחדים של המשכנתא.»
EN: "A mortgage deed charges the property to the bank under the loan agreement; it is produced for registering a mortgage at the Tabu. The deed details the mortgaged property, the mortgagor, the bank in whose favor the mortgage is registered, and the mortgage's special conditions."

**Q6.3** · S21 [P] — Mizrahi: property registered in the mortgagor's name
HE: «1. נכס שרשום בלשכת רישום המקרקעין ("טאבו") על שם המשעבד — א. רישום משכנתא לטובת הבנק בטאבו. ב. טופס שעבוד דירתי חתום בידי הלווה/משעבד אחר.»
EN: "1. Property registered at the Land Registry in the mortgagor's name — (a) registration of a mortgage in favor of the bank at the Tabu; (b) residential-charge form signed by the borrower/other mortgagor."

**Q6.4** · S09 [P][M] — procedure 1.1.1(א)(2)(ג): validity of any transaction deed (including a mortgage deed)
HE: «(ג) תוקפו של שטר עסקה (בכל סוגי השטרות) יהיה לשנה מיום אימות החתימה על גבי השטר. מעבר לתקופה זו, ועד לתקופה של שלוש שנים מיום אימות החתימה על גבי השטר, ניתן יהיה לקבל את השטר, בכפוף להמצאת אישור עורך הדין שאימת את חתימת הצדדים לשטר … לפיו העסקה עודנה בתוקף והצדדים בחיים. … בחלוף 3 שנים מיום אימות החתימה, לא ניתן יהיה עוד לעשות שימוש בשטר.»
EN: "(c) A transaction deed (of any type) is valid for one year from the date its signature was verified. After that and up to three years, it may be accepted with a confirmation from the verifying lawyer … that the transaction is still valid and the parties are alive. After 3 years from verification the deed can no longer be used."
Proves: a hard validity rule usable for deeds. Caveat: compendium dated 30/10/2022 (mirror).

**Q6.5** · S41 [M] — no municipal certificate is needed to register a mortgage
HE: «(ד) רישום משכנתה על נכס אינו טעון הצגת תעודה כאמור בסעיף קטן (א); לעניין זה, ”משכנתה“ – כמשמעותה בסעיף 4 לחוק המקרקעין, התשכ״ט–1969.»
EN: "(d) Registering a mortgage on a property does not require presenting a certificate under subsection (a) …"
Conflict note: the 2022 compendium (S09, proc. 1.1.1(ב)(2)) still lists the municipal no-debts certificate among documents for registering a mortgage; the later statutory amendment (תשפ"ג) in S41(ד) and Tel Aviv's notice (S42: "נוטלי משכנתאות … החל מ … 1.6.23 לא … אישורים של הרש[ויות] המקומיות ב[עניי]ן העדר חובות, בהתאם לתיקון חקיקה") supersede it.

**Q6.6** · S07 [SN] — remote signature verification accepted (news item 29/06/25)
HE: «להלן נוהל מקל לפיו מעתה ניתן לקבל אימות חתימה שנעשה בהיוועדות חזותית מרחוק על תצהירים, ייפויי כח, בקשות לרישום בפנקסי המקרקעין, שטרות עסקה וכן על כלל המסמכים הדורשים אימות בהתאם לתקנות המקרקעין (ניהול ורישום), התשע"ב-2011 …»
EN: "A relieving procedure: signature verification done by remote video conference is now accepted on affidavits, powers of attorney, applications to register in the land registers, transaction deeds and all documents requiring verification under the Land Regulations 2011 …"
Proves: a lawyer's verification may legitimately have been done remotely — do not flag that alone as anomalous.

### B7. Undertaking to register a mortgage — התחייבות לרישום משכנתא

**Q7.1** · S12 [P] — meaning (ILA)
HE: «…מנפיקה הרשות "כתב התחייבות לרישום משכנתא", שמשמעותו התחייבות שלא לרשום בלשכת רישום מקרקעין את הזכויות בנכס, אלא אם במעמד הרישום תרשם גם המשכנתא לטובת הגורם המלווה וכן התחייבות שלא לאשר העברת זכויות בנכס ללא הסכמת הגורם המלווה.»
EN: "…the Authority issues an 'undertaking to register a mortgage', meaning an undertaking not to register the rights at the Land Registry unless the mortgage in favor of the lender is registered at the same time, and an undertaking not to approve a transfer of rights without the lender's consent."

**Q7.2** · S12 [P] — removal, partners, spouses
HE: «3. לאחר פרעון ההלוואה או גרירתה לנכס אחר, על בעל הזכויות לפנות לרשות מקרקעי ישראל בבקשה לסלק את ההתחייבות לרישום המשכנתא הרשומה בספרי הרשות, וזאת בצרוף אישור הגורם המלווה. 4. בנכס שרשום בשותפות ניתן להפיק התחייבות לרישום משכנתא רק על חלקו של שותף אחד בנכס. בנכס שנרכש על ידי שני בני זוג לא תנתן התחייבות לרישום משכנתא על שם אחד מבני הזוג אלא רק בהסכמת שני בני הזוג.»
EN: "3. After repayment or transfer of the loan to another property, the rights holder must apply to the ILA to remove the undertaking, attaching the lender's confirmation. 4. In a property held in partnership, an undertaking may be issued on one partner's share only. In a property bought by two spouses, no undertaking shall be given in one spouse's name except with both spouses' consent."

**Q7.3** · S12 [P] — conditions for issuing
HE: «1.1 הסכם בתוקף (למעט נחלות ללא הסכם חכירה). 1.2 הנכס ללא עיקול; אם נרשם עיקול – יש להמציא צו ביטול עיקול או הסכמה מאת הגורם שהוציא את צו העיקול … 1.3 הנכס ללא משכון / פסק משקם / מניעה משפטית / הערות מגבילות כלשהן. 1.4 אם קיימת התחייבות לרישום משכנתא נוספת על הנכס, יש להמציא מכתב הסכמה … המאשר את דרגת המשכנתא המבוקשת וסכומה. … 1.6 לא קיימים חובות לרשות. … 1.7 לא קיימות הפרות להסכם לרבות הערות לשימושים חורגים/חריגות בנייה. 1.8 הנכס אינו רשום בלשכת רישום מקרקעין ואינו ניתן לרישום בלשכת רישום מקרקעין.»
EN: "1.1 A valid agreement (except farms without a lease); 1.2 no attachment (or a cancellation order/consent of the issuing authority); 1.3 no pledge / rehabilitation judgment / legal impediment / restrictive notes; 1.4 if another undertaking exists — a consent letter confirming the requested rank and amount; 1.6 no debts to the ILA; 1.7 no breaches incl. non-conforming use/building deviations; 1.8 the property is not registered and not registrable at the Land Registry."

**Q7.4** · S12 [P] — the lender's release letter (field list)
HE: «סילוק התחייבות לרישום משכנתא מותנה בהמצאת הפניה חתומה על ידי הגורם המלווה: ▪ עבור בנק או חברת ביטוח - מסמך סילוק על גבי נייר בטחוני או באמצעות כספות מאובטחות בציון שם פרטי ושם משפחה של מורשי החתימה מטעם הגורם המלווה, הכולל את הפרטים הבאים: מספרי זיהוי (ת.ז/ח.פ) ושמות בעלי הזכויות ; גוש וחלקה; כתובת; סכום ההתחייבות; דרגת המשכנתא; ציון תאריך מתן ההתחייבות ע"י הרשות ומספר חוזה או תיק ברשות.»
EN: "Removing an undertaking requires a referral signed by the lender: for a bank or insurer — a release document on security paper or via secure vaults, stating the first and last names of the lender's authorized signatories, including: ID numbers (ID/company no.) and names of the rights holders; block and parcel; address; amount of the undertaking; mortgage rank; date the ILA gave the undertaking; and the ILA contract or file number."
Proves: the identifiers that tie an ILA undertaking to a property and a lender; also an authenticity channel (security paper / secure vault).

**Q7.5** · S12 [P] — amount may be "unlimited"; exceptional cases need a letter of intent
HE: «ג. בקשה להפחתת סכום ההתחייבות (לרבות לשינוי מ- "ללא הגבלה" לסכום נקוב) או לשינוי דרגה …» … «קבלת מכתב כוונות מאת הגורם המלווה … הגורם המלווה אינו גורם מלווה זר ו/או גורם פרטי אחר שאינו בנק או חברת ביטוח בישראל.»
EN: "(c) A request to reduce the undertaking amount (including from 'unlimited' to a stated sum) or to change rank …" … "[in exceptional approvals:] receipt of a letter of intent from the lender … the lender is not a foreign lender and/or another private party that is not a bank or insurer in Israel."

**Q7.6** · S22 [F] — Mizrahi: seller's undertaking (second-hand)
HE: «התחייבות מוכר — את הטופס ששמו "התחייבות", עליכם להעביר באמצעות עורך הדין שלכם למוכרים או לעורך דינם. לאחר מכן, יש להחזיר לבנקאי את הטופס המקורי כשהוא חתום על ידי כל המוכרים ומאומת על ידי עורך דין»
EN: "Seller's undertaking — pass the form called 'undertaking' via your lawyer to the sellers or their lawyer; then return the original to the banker signed by all sellers and verified by a lawyer."

### B8. Pledge at the Registrar of Pledges — הודעת משכון / דוח עיון

**Q8.1** · S22 [F] — Mizrahi
HE: «הודעת משכון — הסבר: הבנק דורש כי תמשכנו את הזכויות שלכם בנכס כביטחון למשכנתא — איפה ואיך מבצעים: את המשכון רושמים אונליין מול רשם המשכונות. ניתן לעשות זאת בפגישה בסניף — עלות רישום לרשם המשכונות: 175 ₪ … דו"חות עיון — הסבר: לאחר רישום המשכון, יש להפיק דו"ח עיון מרשם המשכונות לכל אחד ממבקשי המשכנתא — איפה ואיך מבצעים: אפשר לעשות זאת באתר www.gov.il בעמוד "עיון בשעבודים ומשכונות". את דו"חות העיון שהופקו יש להעלות באפליקציית טפחות טאצ' או לשלוח לבנקאי במייל — עלות: 11 ₪ עבור כל דו"ח»
EN: "Pledge notice — the bank requires you to pledge your rights in the property as security; it is registered online with the Registrar of Pledges, possibly at the branch meeting; registration cost ₪175 … Inspection reports — after registration, produce an inspection report from the Registrar for each mortgage applicant on gov.il ('inspection of charges and pledges') and upload/send it; cost ₪11 per report."
Note: in a second-hand purchase Mizrahi requires a pledge even when the property is registered at the Tabu (Q5.9 items (a)–(d)).

**Q8.2** · S23 [F] — Mizrahi: confirmation of registration and per-ID reports
HE: «בסיום התהליך המקוון מתקבל במחשב הבנקאי מסמך אישור על רישום משכון. לאחר מכן, יש להפיק מאתר האינטרנט של הרשם דוחות עיון על שם הלווים והמשעבדים - זהו דו"ח המציג את נתוני כל המשכונים על-פי מספר ת.ז.»
EN: "At the end of the online process the banker's computer receives a confirmation of pledge registration. Then produce from the Registrar's website inspection reports in the names of the borrowers and mortgagors — a report showing all pledges by ID number."

**Q8.3** · S33 [M] — regs 5(א), 5(ה)
HE: «(א) המבקש לרשום משכון … ימציא לרשם, הודעת מישכון, ערוכה לפי טופס 1 שבתוספת הראשונה לרבות נספחיו … (ה) בהודעת משכון שמצוין בה חייב או ממשכן לחיובו של אחר, שנפטר … ההודעה תיחתם בידי מנהל העיזבון או יורשיו של החייב ותוגש בצירוף צו קיום צוואה, צו ירושה או החלטת בית המשפט על מינוי מנהל העיזבון …»
EN: "(a) An applicant shall submit a pledge notice in Form 1 of the First Schedule with its annexes … (e) In a notice naming a deceased debtor/pledgor, the notice shall be signed by the estate administrator or heirs and filed with a probate order, inheritance order or court decision appointing an administrator …"

**Q8.4** · S33 [M] — regs 13, 13א: formal report vs. online inspection
HE: «”דו״ח רישום“ – אישור על רישומו של משכון הקיים במאגר, לפי חתך החיפוש שצוין בבקשת העיון;» … «(א) אדם רשאי לעיין במאגר באמצעות האינטרנט ולהפיק דוח עיון או נסח עיון … (ב) נסח עיון או דוח עיון שהופק באמצעות האינטרנט אינו מהווה דוח רישום או נסח רישום, כהגדרתו בתקנה 13.»
EN: "'Registration report' — confirmation of registration of a pledge existing in the database, by the search criterion …" … "(a) A person may inspect via the internet and produce an inspection report … (b) An inspection report produced via the internet is not a registration report …"
Proves: the online "דוח עיון" Mizrahi asks for is, by regulation, not a formal registration report. (Policy question — see E.)

**Q8.5** · S34 [SN][M] — official Form 1 "הודעת מישכון" (field list)
HE: «1. תקופת הרישום: א. ציין את מס' השנים ב. תאריך סיום תקופת המשכון (אלא אם יבוטל לפני כן) 2. הנושים: … 3. החייבים: … 4. ממשכן לחיובו של אחר - תקנה 7 … 5. נכס שהוא זכות לגבי מקרקעין, שאינה רשומה בפנקסי מרשם המקרקעין כמשמעותם בסעיף 123 לחוק המקרקעין, התשכ"ט – 1969 גוש ___ חלקה ___ תת חלקה ___ מגרש ___ רחוב ___ מס' בית ___ דירה ___ ישוב ___ תאור ___ … 8. אם קיימת בהסכם קביעה לגבי משכון נוסף נא לסמן ב- X 9. לרישום הערה לפי תקנה 5 (ד), נא לסמן ב- X 10. רצ"ב: נספח א' נושים / חייבים נוספים נספח ב' נכסים נוספים … לשימוש משרדי: 1. מס' רישום המשכון ___ מס' פעולה / בקשה ___ 2. סכום האגרה שנגבתה ___ ש"ח לפי קבלה מס' ___»
EN: "1. Registration period: (a) number of years (b) end date of the pledge period (unless cancelled earlier). 2. Creditors … 3. Debtors … 4. Pledgor for another's debt (reg. 7) … 5. Property that is a right relating to land not registered in the land registers (s.123 Land Law): block, parcel, sub-parcel, plot, street, house no., apartment, locality, description … 8. Mark if the agreement provides for an additional pledge. 9. Mark for a note under reg. 5(d). 10. Attached: Annex A additional creditors/debtors; Annex B additional assets … Office use: 1. pledge registration number; action/request no. 2. fee collected, receipt no."
Proves: the pledge has a registration period and end date (a validity field), and identifies unregistered land rights by the same block/parcel/sub-parcel keys. Debtor address rule: «מענו של יחיד כפי שיירשם במאגר הוא המען הרשום של היחיד במרשם האוכלוסין» (reg. 6(א), S33) — "an individual's address in the database is his registered address in the population registry".

**Q8.6** · S24 [F] — Mizrahi: documents for releasing liens after full repayment
HE: «קבלת שחרורי שעבודים ומשכונים (לאחר סילוק מלא) בנוהל מזורז. שחרור שעבוד יבוצע 30 יום לאחר קבלת אסמכתה להעברת הכספים. … - נסח טאבו או אישור זכויות - דו"ח רישום משכון ודו"ח תוצאות עיון»
EN: "Expedited release of charges and pledges (after full repayment). The release is executed 30 days after receiving proof of the funds transfer … [attach] Tabu extract or rights confirmation; pledge registration report and inspection results report."

### B9. Purchase agreement — הסכם מכר / חוזה רכישה

No official consumer guide enumerating all contract fields for a second-hand purchase was found, nor Israel Bar guidance (see D). Authoritative anchors:

**Q9.1** · S05 [M] — Land Law s.8
HE: «התחייבות לעשות עסקה במקרקעין טעונה מסמך בכתב.»
EN: "An undertaking to make a transaction in land requires a written document."

**Q9.2** · S31 [M] — new apartments: the specification must be attached
HE: «(א) המוכר דירה חייב לצרף לחוזה המכר מפרט והוראות תחזוקה ושימוש. (א1) המוכר יצרף לחוזה המכר, בעת חתימתו, את המפרט וכן את הוראות התחזוקה והשימוש חתומות בידיו … (ב) כל תיקון במפרט טעון חתימת שני הצדדים.» … «(א) המפרט יהיה בטופס שקבע השר בצו …»
EN: "(a) A seller of an apartment must attach a specification and maintenance/use instructions to the sale contract. (a1) … at signing, signed by him … (b) Every amendment to the specification requires both parties' signatures." … "(a) The specification shall be in the form set by the Minister by order …"

**Q9.3** · S38 [SN] — what the parties report to the Tax Authority (a cross-check source for contract data)
HE: «בהתאם להוראות סעיף 73(א) לחוק מיסוי מקרקעין, על המוכר להגיש הצהרה בתוך 30 ימים מיום המכירה. על ההצהרה לכלול: 1. פרטי הזכות. 2. פרטי העסקה. 3. התמורה בעד מכירת הזכות ותאריך מכירתה. 4. התמורה בעד רכישת הזכות ותאריך רכישתה בעבר. 5. הוצאות המותרות בניכוי. 6. סכום מס השבח ודרך חישובו. 7. זכאות לפטור או להנחה במס בהתאם לחוק. בהתאם להוראות סעיף 73(ג) לחוק מיסוי מקרקעין, על הרוכש להגיש הצהרה בתוך 30 ימים מיום המכירה. 1. פרטי הזכות. 2. פרטי העסקה. 3. התמורה ששולמה בעד הזכות. 4. סכום מס הרכישה ודרך חישובו. 5. זכאות לפטור או להנחה במס בהתאם לתקנות מס רכישה.» … attachments listed: «- חוזה מכר. - חוזה רכישה. - נסח טאבו.»
EN: "Under s.73(a) the seller must file a declaration within 30 days of the sale, including: right details; transaction details; consideration and sale date; original purchase consideration and date; deductible expenses; betterment-tax amount and calculation; exemption/relief. Under s.73(c) the buyer must file within 30 days: right details; transaction details; consideration paid; purchase-tax amount and calculation; exemption/relief." Attachments include "sale contract; purchase contract; Tabu extract".

**Q9.4** · S21 [P] — Mizrahi requirements tied to the contract
HE: «הסכם רכישה של הנכס (אם הנכס אינו רשום ע"ש הלווה או המשעבד).» … «בהלוואות לרכישת דירה - חוזה רכישת הדירה חתום כחוק וכן צילום תעודת הזהות ומספר חשבון הבנק של מוכר הדירה בצירוף מסמך לאימות פרטי החשבון (שיק, אישור מהבנק וכד');»
EN: "Purchase agreement for the property (if the property is not registered in the borrower's/mortgagor's name)." … "For apartment-purchase loans — the purchase contract duly signed, plus a copy of the seller's ID card and the seller's bank account number with a document verifying the account (cheque, bank confirmation, etc.)."

**Q9.5** · S15 [P, official translation] — contract dates that drive the loan (Directive 451 ss.6, 11(c))
EN: "6. A banking corporation that transfers the loan money to the seller, on the basis of written instructions received from the borrower, shall act as follows: (a) Execute the loan in accordance with the date specified in the contract between the borrower and the seller, unless the banking corporation and the borrower have agreed in writing on another date …" … "11(c) A banking corporation shall not require a borrower to insure a residential apartment he has purchased from a contractor at a date prior to the one on which the seller has undertaken, in the sale contract, to transfer the apartment to the buyer …"
Proves: the contract's payment dates and (new build) delivery date are operative fields.

**Q9.6** · S22 [F] — Mizrahi: contract-linked disbursement and payment instructions
HE: «תשלום על חשבון ההלוואה — זהו טופס מפרט את החשבון או את חשבונות הבנק אליהם צריך להעביר את כספי המשכנתא למוכרים (או לעורך הדין, לטובת סילוק משכנתא של המוכרים וכו'). את הטופס ממלא עורך הדין והוא מחתים עליו את המוכרים … בהתאם לחוזה הרכישה, הבנק יעביר את הסכום האחרון של כספי המשכנתא רק לאחר קבלת אישורי המיסים עבור הנכס (תשלום מס שבח לדוגמה) או לאחר שיופקד בנאמנות עורך דין לחשבון נאמנות ספציפי. יש לצרף את אישורי המס הרשומים בחוזה או לציין את פרטי חשבון הנאמנות, ולצרף אסמכתה גם לחשבון זה» … «אישור תשלום הון עצמי — על המוכרים לאשר את גובה תשלום ההון העצמי שהועבר אליהם …»
EN: "Payment on account of the loan — a form listing the bank account(s) to which mortgage money is to be paid to the sellers (or to the lawyer, e.g., to pay off the sellers' mortgage); the lawyer fills it and has the sellers sign … Per the purchase contract, the bank transfers the last tranche only after receiving the tax approvals (e.g., betterment tax) or after it is deposited in a specific lawyer trust account; attach the tax approvals listed in the contract or give the trust account details with proof." … "Confirmation of equity paid — the sellers must confirm the amount of equity transferred to them …"

### B10. Taxes, betterment levy and municipal certificate for transfer

**Q10.1** · S40 [M] — Land Taxation Law s.16(א)(2)
HE: «(2) מכירת זכות במקרקעין לא תירשם בפנקס המקרקעין, אלא אם כן המנהל אישר שהיא פטורה ממס או ששולם המס המגיע על פי שומה שנעשתה לפי הוראות סעיף 78(ב)(1) או (2); לא נעשתה שומה כאמור, תירשם המכירה אם ניתנה ערבות בנקאית … או ערובה אחרת להנחת דעתו של המנהל …»
EN: "(2) A sale of a right in land shall not be registered unless the Director confirmed it is exempt or that the tax due under an assessment under s.78(b)(1)/(2) was paid; absent such an assessment, it may be registered if a bank guarantee … or other security satisfactory to the Director was given …"

**Q10.2** · S40 [M] — s.16(א)(2א) (exempt residential sale — the fast route)
HE: «(2א) על אף האמור בפסקה (2), ביקש מוכר של דירת מגורים מזכה … פטור ממס שבח …, תירשם מכירת הזכות בפנקסי המקרקעין, אם אישר המנהל כי התקיימו התנאים כאמור ותנאים אלה: (א) הצהרת המוכר והצהרת הרוכש נמסרו במועד הקבוע בסעיף 73 …; (ב) חלפו 10 ימים מיום ההצהרה או מהיום שהמציאו הרוכש והמוכר למנהל את כל המסמכים והפרטים שנדרש להמציאם, לפי המאוחר; …»
EN: "(2a) … where the seller of a qualifying residential apartment requested a betterment-tax exemption, the sale shall be registered if the Director confirmed the conditions are met, including: (a) seller's and buyer's declarations filed on time …; (b) 10 days passed from the declaration or from delivery of all required documents, whichever is later; …"

**Q10.3** · S38 [SN] — assessment notice and payment voucher
HE: «המשרד האזורי שאליו הוגשה ההצהרה יבדוק את תקינות הגשתה. עם קליטת ההצהרה, תישלח הודעת שומה ושובר לתשלום השומה העצמית.»
EN: "The regional office will check the filing; once the declaration is recorded, an assessment notice and a voucher for paying the self-assessment are sent."

**Q10.4** · S09 [P][M] — what the Land Registry requires for a sale (procedure 1.1.1(א)) and the identifier-match rule (1.1.2)
HE: «(4) אישור על תשלום מס שבח מקרקעין או פטור, מופנה לרשם המקרקעין … (5) אישור על תשלום מס רכישה או פטור, מופנה לרשם המקרקעין. (6) אישור על תשלום מס מכירה או פטור … יש לדרוש המצאת אישור מס מכירה רק במקרים בהם המקרקעין נמכרו בין 1.1.2000 ל- 1.8.2007 … (7) אם לא בוצעה עסקה בנכס מאז יום 31.12.1999, יש לצרף אישור על תשלום מס רכוש, או פטור ממנו, בתוקף ליום הגשת התיק … (8) אישור היעדר חובות לעירייה/ רשות מקומית, תקף ליום הגשת התיק. במקרים בהם נדחה תיק לצורך השלמות או תיקונים והוגש מחדש, ניתן יהיה לעשות שימוש באישור המקורי כל עוד לא חלפו שלושה חודשים ממועד תום תקופת אישור זה. (9) אישור הוועדה המקומית לתכנון ולבניה על תשלום או פטור מהיטל השבחה.» … «1.1.2 … א. יש לוודא שמספרי הגוש, החלקה ותת החלקה המופיעים באישורים על תשלומי החובה, יהיו זהים למספרים הרשומים בפנקסי המקרקעין. ב. … במקרה בו קיימת אי התאמה בין זיהוי הנכס המופיע באישורי המסים לבין הנכס מושא העסקה/הפעולה, ניתן יהיה לצרף לאישור המס תצהיר עורך דין לעניין זיהוי הנכס …»
EN: "(4) Certificate of betterment-tax payment or exemption, addressed to the Land Registrar; (5) certificate of purchase-tax payment or exemption, addressed to the Registrar; (6) sale-tax certificate — only for sales between 1.1.2000 and 1.8.2007; (7) if no transaction since 31.12.1999 — property-tax certificate valid on the filing date; (8) municipal/local-authority no-debts certificate valid on the filing date; if the file was rejected and refiled, the original may be used for up to three months after its validity ended; (9) local planning committee certificate of payment of, or exemption from, betterment levy." … "1.1.2 (a) The block, parcel and sub-parcel numbers on the compulsory-payment certificates must be identical to those in the land registers. (b) Where the tax certificate's property identification does not match, a lawyer's affidavit on the property's identification may be attached …"
Proves: the set of clearances for a transfer, their addressee, a validity rule for the municipal certificate, and an identifier-match rule. Caveat: compendium dated 30/10/2022 (mirror).

**Q10.5** · S41 [M] — Municipalities Ordinance s.324
HE: «(א) לא תירשם בפנקסי המקרקעין כל העברה של נכס, אלא אם הוצגה לפני הרשם, תעודה חתומה בידי ראש העיריה או מי שהוא הסמיך לכך, המעידה שכל החובות המגיעים לעיריה מאת בעל הנכס ביחס לאותו נכס עד ליום מתן התעודה והנובעים מהוראות הפקודה או מדין אחר – סולקו במלואם או שאין חובות כאלה. (ב) תעודה כאמור הנחזית כחתומה על ידי ראש העיריה יקבלוה הרשם או עוזר הרשם כחתומה על ידיו, זולת אם נראה להם שאין היא חתומה כך.»
EN: "(a) No transfer of property shall be registered unless a certificate signed by the mayor or his delegate is presented, certifying that all debts owed to the municipality by the owner for that property up to the certificate date … were paid in full or that there are none. (b) The registrar shall accept a certificate that appears signed by the mayor as so signed, unless it appears otherwise." (+ (ד) mortgage exemption, Q6.5.)

**Q10.6** · S42 [SN] — Tel Aviv-Yafo: validity
HE: «תעודה זו היא תנאי להסדרת הליך רישום הבעלים ברשם המקרקעין (טאבו), ותוקפה הוא עד שנה מיום תשלום אגרת טאבו, בתנאי ששולמו מלוא החובות לעירייה כאמור.» … «במקרים בהם התעודה ניתנה לתקופה קצרה משנה, אפשר להאריך את תוקף התעודה עד שנה ממועד תשלום האגרה הראשונה.»
EN: "This certificate is a condition for registering the owner at the Land Registry, and it is valid for up to one year from payment of the Tabu certificate fee, provided all debts were paid." … "Where it was issued for less than a year, its validity may be extended up to one year from the first fee payment."
Proves: Tel Aviv's rule only; other municipalities may differ. The certificate may carry its own validity date (field).

**Q10.7** · S43 [M] — betterment levy certificate (Third Schedule s.10(א))
HE: «לא תירשם בפנקסי המקרקעין פעולה שהיא בבחינת מימוש זכויות במקרקעין, אלא לאחר שהוצגה בפני הרשם תעודה החתומה ביד יושב ראש הועדה המקומית או ביד מי שהסמיכו לכך, המעידה כי שולמו כל הסכומים המגיעים אותה שעה כהיטל החל על המקרקעין על פי תוספת זו, או ניתנה ערובה לתשלומו, כולו או מקצתו …»
EN: "No act that constitutes realization of rights in land shall be registered unless a certificate signed by the local committee chair or his delegate is presented, certifying that all amounts then due as betterment levy were paid, or security for payment was given …"

**Q10.8** · S22 [F] — Mizrahi: tax approvals the bank collects (second-hand)
HE: «אישורי מיסים — עלינו לקבל מכם את כל אישורי המיסים בעסקה. … - העתק דיווח העסקה לשלטונות המס (מש"ח) + אישור דיווח דיגיטלי - אישור תשלום מס רכישה - אישור תשלום מס שבח (או אישור על הפקדת הסכום לתשלום מס השבח בנאמנות עורך דין) - אישור עירייה עדכני על היעדר חובות של בעל הנכס מול העירייה»
EN: "Tax approvals — we need all tax approvals in the transaction … copy of the transaction report to the tax authorities ('מש"ח') + digital reporting confirmation; purchase-tax payment confirmation; betterment-tax payment confirmation (or confirmation that the betterment-tax amount was deposited in a lawyer's trust); a current municipal certificate that the owner has no debts to the municipality."
(The abbreviation "מש"ח" is not expanded on the page — see E.)

**Q10.9** · S39 [SN][M] — Tax Authority form 7161 (fast route conditions)
HE: «2. התנאים לקבלת אישורים לעסקה במסלול דירות מגורים פטורות – סעיף 16(א)(2א) במסלול זה יוכל הרוכש לבקש אישור מס שבח ואישור מס רכישה המוכר יוכל לבקש אישור מס שבח בלבד א. המוכר הגיש הצהרה במועד על מכירה פטורה … על טופס 7000 ב. הצהרת הרוכש הוגשה במועד בהתאם לסעיף 73 ג. שולמה השומה העצמית במס רכישה …»
EN: "2. Conditions for approvals in the exempt-residential route (s.16(a)(2a)): the buyer may request betterment-tax and purchase-tax approvals; the seller only betterment-tax approval. (a) the seller filed on time an exempt-sale declaration on form 7000; (b) the buyer's declaration was filed on time; (c) the purchase-tax self-assessment was paid …"

**Q10.10** · S46 SECONDARY [SN] — certificates downloadable from the personal area (since 2/4/2023)
HE: «רשות המסים משיקה שירות חדש לציבור המאפשר לכל אזרח לקבל באזור האישי, באתר רשות המסים, את אישורי המסים שניתנו לצורך רישום עסקאות הנדל"ן שביצע בפנקסי רישום המקרקעין (טאבו). האישורים יהיו זמינים עבור עסקאות שבוצעו משנת 1983 ואילך.»
EN: "The Tax Authority launches a service letting every citizen obtain, in the personal area, the tax approvals issued for registering his real-estate transactions at the Tabu, for transactions from 1983 onward."
Status: news report only; useful to know that a digital copy of the certificate should exist.

**Q10.11** · S40 [M] — buyer's advance payment on the seller's tax (all sales, not only foreign residents)
HE: «(ב) … במכירת זכות במקרקעין שתמורתה נקבעה בכסף בלבד יהיה הרוכש חייב להעביר למנהל תשלום על חשבון המס שהמוכר חייב בו … (1) … לפני כ״א בחשוון התשס״ב (7 בנובמבר 2001) – 15% מהתמורה; (2) … מיום … 7 בנובמבר 2001 ואילך – 7.5% מהתמורה …»
EN: "(b) … in a cash-only sale the buyer must transfer to the Director a payment on account of the seller's tax: (1) right acquired before 7 November 2001 — 15% of the consideration; (2) from 7 November 2001 — 7.5% …"

### B11. Appraisal for the mortgage — שמאות מקרקעין

**Q11.1** · S15 [P, official translation] — Directive 451 s.4c(c)(2): the bank refers the customer and lists its appraisers
EN: "(2) Reference to carrying out an appraisal, with a detailed listing of the appraisers with whom the banking corporation works for appraising assets for the purpose of receiving housing loans and those working in the asset's geographic area, and an explanation regarding the provisions of Section 9(e) …"
HE (S14): «(2) הפנייה לביצוע שמאות, תוך פירוט רשימת השמאים עימם עובד התאגיד הבנקאי לצורך הערכת נכסים לצרכי קבלת הלוואות לדיור, והפועלים באזור הגאוגרפי בו מצוי הנכס, והסבר לגבי האמור בסעיף 9(ה) …»
Note: s.9(ה) still cross-refers to "4ג(ב)(8)", while the referral now sits in 4ג(ג)(2) — an internal cross-reference inconsistency in the directive.

**Q11.2** · S14 [P] + S15 official translation — s.9(ג)–(ה): cost, copy to the borrower, 90-day reuse
HE: «(ג) פנה התאגיד הבנקאי לשמאי לבצע הערכת נכס, רשאי התאגיד הבנקאי לחייב את הלווה בהוצאות הממשיות שהיו לו או כפי שנקבע בתעריפון העמלות של התאגיד הבנקאי, לפי הסכום הנמוך ביניהם. (ד) חייב התאגיד הבנקאי את הלווה בגין הערכת השמאי, ימסור לו העתק מדוח השומה. (ה) תאגיד בנקאי לא יסרב סירוב בלתי סביר לבקשת לווה לעשות שימוש בהערכת נכס שהציג לווה, ובלבד שניתנה לבקשת תאגיד בנקאי אחר לצורך מתן הלוואה לדיור, ושהשמאי נכלל ברשימת השמאים המפורטת בהפניה לביצוע שמאות שניתנה ללקוח …, ושלא חלפו 90 ימים ממועד הערכת הנכס. התאגיד הבנקאי רשאי לדרוש כי השמאי יפנה את הערכת הנכס ישירות אליו, וכן הוא רשאי לדרוש ביצוע התאמות בשומה.»
EN (official): "(c) If the banking corporation has asked an appraiser to appraise a property, the banking corporation may charge the borrower for the actual costs it has incurred or as determined in the banking corporation's list of fees, whichever is lower. (d) If the banking corporation has charged the borrower for the appraiser's costs, it should give him a copy of the appraiser's report. (e) The banking corporation shall not unreasonably refuse a borrower's request to use a property appraisal presented by the borrower, provided that it was given at the request of another banking corporation for the purpose of extending a housing loan, and that the appraiser is included in the list of appraisers … and that 90 days have not passed from the date of the property appraisal. The banking corporation may require that the appraiser transmit the appraisal directly to it, and it may require adjustments to be made in the appraisal."
Proves: the customer gets a copy when charged; 90-day reuse window. Does not prove: who owns the report.

**Q11.3** · S14 [P] + S15 — s.10: how the appraisal is done and what it must contain
HE: «(א) השומה תיערך בידי שמאי מוסמך באופן בלתי תלוי במידע שמצוי בידי התאגיד הבנקאי; עריכת השומה מחייבת ביקור פיזי בנכס, וכן הכנת תרשים של הנכס. (ב) השומה המוגשת לתאגיד הבנקאי תכלול תיאור מפורט של הנכס וכן את כל אותם הפרטים הנדרשים על ידי משרדי הממשלה המוסמכים בשמאות דירות להלוואות מוכוונות, וכן הצהרת השמאי על תאריך ביקורו בנכס.»
EN (official): "(a) The appraisal shall be performed by a certified appraiser independently of the information in the possession of the banking corporation; the performance of the appraisal requires physically visiting the property, as well as making a drawing of it. (b) The appraisal submitted to the banking corporation shall include a detailed description of the property, all the details required by the authorized government ministries for appraising apartments for directed loans, and the appraiser's declaration regarding the date of his visit to the property."

**Q11.4** · S18 [P] — BoI draft circular (2018) explanatory note: reasonable refusals of another bank's appraisal (draft — final text may differ)
HE: «כדוגמא לסירוב סביר לעשות שימוש בהערכת נכס שמציג לווה ניתן לציין הערכת נכס אשר בוצעה שלא לצורך מתן הלוואה לדיור, הערכת נכס שחסר בה פרט מהותי לדעת התאגיד הבנקאי, הערכת נכס שבוצעה על ידי שמאי שהתמחותו אינה באזור הגאוגרפי בו נערכה השומה וכד'.»
EN: "Examples of a reasonable refusal: an appraisal not made for a housing loan; an appraisal missing a material detail in the bank's view; an appraisal by an appraiser whose specialization is not in the geographic area, etc."

**Q11.5** · S22 [F] — Mizrahi: who appoints, who receives
HE: «שמאות — הסבר: בכל בקשה למשכנתא יש לפנות לשמאי לצורך הערכת שווי הדירה … איפה ואיך מבצעים? תקבלו מהבנקאי טופס אשר כולל רשימה של 3 שמאים, מהם תבחרו את מי שתרצו לצורך הערכת שווי הדירה. בטופס מפורטים המסמכים אותם יש להעביר לשמאי והתעריף אותו תשלמו. לאחר ביצוע ההערכה, השמאי יעביר ישירות לבנק את הערכת השווי (השמאות). ניתן לבקש העתק של השמאות מהשמאי.»
EN: "Appraisal — every mortgage application needs an appraiser to value the apartment … You get from the banker a form listing 3 appraisers; you choose one. The form lists the documents to give the appraiser and the fee. After the appraisal, the appraiser sends the valuation directly to the bank. You may request a copy of the appraisal from the appraiser."
Proves: the bank provides the panel and receives the report directly; the customer may get a copy. Authenticity implication: a report arriving only from the customer (not from the appraiser) should be flagged.

**Q11.6** · S21 [P] — Mizrahi appraisal types, payer, and price ranges
HE: «כמו כן, במקרים בהם נדרשת שמאות כתנאי לביצוע ההלוואה, עלות שמאות תשולם ישירות לשמאי על ידי הלקוח. … הערכת שמאי להלוואות מוכוונות (לזכאי משרד השיכון בלבד) ועד שווי נכס של 2.1 מ' ₪ — 390 ₪ - 481 ₪; שומה מקוצרת/רגילה (לאחר רכישה) – משמשת לדירות גן וגג עד לשווי של 1.3 מ' ש"ח (כולל), וכן לכל יתר סוגי הדירות בבניה בבית קומות בסכום של עד 5 מ' ₪ (כולל) — 850 ₪ - 4,420 ₪; סוג שמאות מורחבת (לאחר רכישה) - משמשת למגרשים, בניה עצמית, צמודי קרקע, דירות גן וגג בסכום שעולה על 1.3 מ' ₪. בנוסף משמשת לכל יתר סוגי הדירות בבית קומות בשווי העולה על 5 מ' ₪ ועד לסכום של 10 מ' ₪ (כולל) ובכפוף לכך ששיעור המימון אינו עולה על 50% וסכום אשראי אינו עולה על 3 מ' ₪ — 1,600 ₪ - 6,040 ₪; סוג שמאות תקן 19 (לאחר רכישה) –משמשת לנחלות. בנוסף משמשת לכל יתר הנכסים בשווי העולה על 5 מ' ₪ ועד 10 מ' ₪ (כולל) במקרה ששיעור המימון עולה על 50% ו/או במקרה שסכום האשראי עולה על 3 מ' ₪ — 4,400 ₪ - 9,750 ₪; סוג שמאות תקן 19 (לאחר רכישה) משמשת למקרים בהם שווי הנכס עולה על 10 מ' ₪ — התעריף בתיאום הלקוח מול השמאי; סוג שמאות תקן 19 – שמאות טרום רכישה.»
EN: "Where an appraisal is a loan condition, the customer pays the appraiser directly. … Directed-loan appraisal (Ministry of Housing eligibles only), property value up to ₪2.1m — ₪390–481; short/regular appraisal (post-purchase) — garden/roof apartments up to ₪1.3m and other apartments in multi-storey buildings up to ₪5m — ₪850–4,420; extended appraisal (post-purchase) — plots, self-build, ground-attached houses, garden/roof apartments above ₪1.3m, and other apartments above ₪5m up to ₪10m if LTV ≤ 50% and credit ≤ ₪3m — ₪1,600–6,040; 'Standard 19' appraisal (post-purchase) — farms (nachalot), and other properties above ₪5m up to ₪10m where LTV > 50% and/or credit > ₪3m — ₪4,400–9,750; 'Standard 19' (post-purchase) above ₪10m — fee agreed with the appraiser; 'Standard 19' — pre-purchase appraisal."
Proves: Mizrahi's appraisal-type selection rules (configuration for the system). Does not prove: that these types are regulatory categories.

**Q11.7** · S35 [P] — Standard 19 scope excludes residential mortgage appraisals
HE: «התקן יחול על שומות מקרקעין המיועדות לבטוחה עבור בנק, חברת ביטוח או גורם אחר המספק אשראי. התקן לא יחול על שומות לדירות מגורים הנערכות לצורך קבלת הלוואה לדיור ("משכנתא").»
EN: "The standard applies to appraisals intended as security for a bank, insurer or other credit provider. It does not apply to appraisals of residential apartments prepared for obtaining a housing loan ('mortgage')."
Proves: Standard 19's extra rules (2-month extract, 3-month confirmation, forced-sale reduction, "value for security purposes") are not a regulatory requirement for ordinary residential mortgage appraisals; when Mizrahi orders a "תקן 19" appraisal (Q11.6), they apply by the bank's choice.

**Q11.8** · S36 [P] — Standard 1.1 applies to all appraisals (in force for appraisals signed from 1/4/2025): mandatory sections, visit timing, signature, declarations
HE: «התקן חל על כל שומות המקרקעין.» … «שומות המקרקעין לסוגיהן יכללו את הסעיפים האלה: סוג השומה ומועד כתיבתה (בכותרת המסמך); זהות מזמין השומה והקשר שלו לנכס הנשום; מטרת השומה; המועד הקובע לשומה; מועד הביקור בנכס וזהות המבקר; זיהוי הנכס; מפת איתור הנכס [±]; תיאור הנכס והסביבה; תמונת חזית הנכס [±]; המצב התכנוני; הזכויות בנכס (או המצב המשפטי); היסטוריה של הנכס, שומות ועסקאות בנכס [±]; פירוט חוות דעת של מומחים שנעזר בהם השמאי [±]; עקרונות, גורמים ושיקולים; תחשיב; שווי הזכויות הנישומות (השומה); חתימת השמאי; הצהרות» … «נוסח הסעיף יהיה קבוע: "ביקור בנכס נערך ביום [שנה/חודש/יום] ע"י _____". הביקור בנכס ייערך עד שלושה חודשים טרם מועד הוצאת השומה.» … «ככל שהשומה תודפס לשם העברתה למשתמשים, אזי השמאי יחתום בחתימת ידו על גבי מסמך השומה המודפס שערך לאחר סעיף השומה. שומת מקרקעין שתועבר למשתמשים כקובץ ממוחשב, תיחתם בחתימה אלקטרונית מאושרת של השמאי שערך אותה, או לחלופין בחתימה אלקטרונית מאובטחת שהונפקה לשמאי על ידי גורם ממשלתי …» … «"אני מצהיר כי אין לי כל עניין אישי בנכס נשוא השומה, בבעלי הזכויות בו או במזמין השומה".» … «א. הוספת הכיתוב "מבוססת הנחה" בכותרת השומה.»
EN: "The standard applies to all real-estate appraisals." … "Appraisals of all types shall include: appraisal type and writing date (in the title); identity of the orderer and his relation to the property; purpose; valuation date; visit date and visitor identity; property identification; location map [±]; description of property and surroundings; front photo [±]; planning status; rights in the property (legal status); history, prior appraisals and transactions [±]; experts relied on [±]; principles, factors and considerations; calculation; value of the appraised rights; appraiser's signature; declarations" ([±] = may be omitted in a 'full' appraisal if not relevant). … "Fixed wording: 'A visit to the property was made on [YYYY/MM/DD] by ___'. The visit shall take place up to three months before the appraisal is issued." … "If printed for users, the appraiser signs by hand after the value section. An appraisal delivered as a computer file shall be signed with the appraiser's approved electronic signature, or with a secure electronic signature issued to the appraiser by a government body …" … "'I declare I have no personal interest in the appraised property, its rights holders or the orderer.'" … "(a) add 'assumption-based' to the appraisal title" [when a counterfactual assumption was requested or a fact could not be checked].

**Q11.9** · S37 [M] — Ethics Regulations, Schedule (minimum contents of any appraisal report)
HE: «אלה הפרטים המהווים את המינימום הנדרש לדו״ח שומה שנערך ביד שמאי: (1) זיהוי הנכס (המיקום, מהות הנכס, שטח הנכס, גוש, חלקה או מספר מגרש לפי תכנית בנין עיר, מען וכיוצא באלה); (2) תיאור הנכס והסביבה; (3) הזכויות המוערכות (בעלות, חכירה, דיירות מוגנת וכיוצא באלה); (4) המצב התכנוני (ייעוד הקרקע והתכניות החלות עליה); (5) מטרת השומה; (6) הודעת השמאי על עריכת ביקור בנכס, בציון עורך הביקור ומועד הביקור; (7) המועד הקובע לענין השומה; (8) העקרונות שלפיהם נערכה השומה; (9) בהערכת מקרקעין: ייווסף פירוט של אפשרויות השימוש בנכס, לרבות אפשרויות שינוי השימוש בו, תוספות בניה אפשריות וכיוצא באלה; (10) נעזר השמאי בעריכת השומה במומחה – יפורטו זהות המומחה, פרטי מומחיותו והענין שבו חיווה את דעתו; (11) מצב הרישוי בנכס; (12) תחשיבים; (13) נקבע שכר השמאי לפי תוצאות מתן השירות כאמור בתקנה 4 – יצוין עניין זה.»
EN: "These are the minimum details of an appraisal report: (1) property identification (location, nature, area, block, parcel or plot number per the town plan, address, etc.); (2) description of the property and surroundings; (3) the rights appraised (ownership, lease, protected tenancy, etc.); (4) planning status (land designation and applicable plans); (5) purpose; (6) the appraiser's statement on the visit, naming the visitor and the visit date; (7) valuation date; (8) principles; (9) for land: possible uses, change of use, possible additions, etc.; (10) any expert relied on — identity, expertise, subject; (11) the property's permit/licensing status; (12) calculations; (13) if the fee depends on the outcome — this shall be stated."

**Q11.10** · S21 [P] — the appraisal feeds the insurance amount
HE: «סכום הביטוח: מומלץ כי סכום הביטוח ישקף את עלויות הבנייה מחדש של הנכס (להלן: "ערך כינון"). ברוב המקרים, ערך הכינון נקבע על ידי השמאי שמעריך את שווי הנכס.»
EN: "Sum insured: it is recommended that it reflect the cost of rebuilding the property ('reinstatement value'). In most cases the reinstatement value is set by the appraiser who values the property."
Also S22: «פוליסת ביטוח נכס - פוליסה בגובה ערך הכינון (הסכום המוערך הדרוש לבניית הנכס מחדש), נתון הזה רושם השמאי.» — "a property policy for the reinstatement value … this figure is written by the appraiser."

### B12. Mortgage insurance — life insurance and structure/property insurance

**Regulator note.** The binding rules found are the **Bank of Israel's** Directive 451 s.11 and the Banking (Service to Customer) Law. **No Capital Market Authority circular** on mortgage insurance was retrievable in this session (see D).

**Q12.1** · S15 [P, official translation] + S14 HE — s.11(a)–(b): bank as irrevocable beneficiary; any insurer; 14-day answer
EN: "11. (a) A banking corporation may require the borrower to insure the property that serves as collateral for the loan, and to take out life insurance within the limits of the amount of the loan received, only if the banking corporation shall be the irrevocable beneficiary. (b) (1) The banking corporation shall inform the borrower that he may undertake the aforesaid insurance directly, and not via a corporation which is an insurance agent controlled by the banking corporation (hereafter: external insurance). In that case, the banking corporation may insist on the fulfillment of the conditions required in order to ensure its rights. A notice to this effect shall appear in a prominent position and in large letters … (2) If a borrower has taken out external property insurance or external life insurance, and has provided the policy to the branch …, the banking corporation shall give the borrower a confirmation of receipt of the policy at the time he hands it to the banking corporation. The banking corporation shall notify the borrower and the insurer within fourteen days that the policy does not satisfy its requirements, and that the banking corporation itself has therefore insured the borrower, or that the policy does satisfy its requirements. (3) … not later than thirty days before the end of the insurance year, that his insurance is about to expire …"
HE (S14): «(א) תאגיד בנקאי רשאי לדרוש מהלווה לבטח את הנכס המשמש כערובה להלוואה, וכן לבצע ביטוח חיים בגבולות סכום ההלוואה שקיבל, ובלבד שהתאגיד הבנקאי יהא מוטב בלתי חוזר.»
Proves: customer may buy from any insurer; the bank must accept or reject within 14 days; the bank may insist on conditions protecting its rights. Does not prove: the conditions' wording (bank-specific — Q12.6–Q12.8).

**Q12.2** · S15 [P, official translation] — s.11(c)–(d): start date for new builds; insured value cap; ₪30,000 floor
EN: "(c) A banking corporation shall not require a borrower to insure a residential apartment he has purchased from a contractor at a date prior to the one on which the seller has undertaken, in the sale contract, to transfer the apartment to the buyer unless the apartment is transferred to the buyer before the said date … (d)(1) A banking corporation shall not require a borrower to insure the pledged property for a value exceeding the adjusted loan balance. Accordingly, the banking corporation shall offer the borrower, in a separate document, the possibility of insuring the property for a value not exceeding the adjusted loan balance …"
HE (S14): «(3) תאגיד בנקאי לא יחייב לווה לבצע ביטוח חיים וביטוח נכס בהלוואות בסכומים עד 30,000 ש"ח או שיתרתן אינה עולה על סכום זה. … לעניין סעיף זה - "יתרת הלוואה משוערכת בלתי מסולקת" - יתרת הלוואה משוערכת, בניכוי ערך הקרקע המתייחס לדירה, ובתוספת עד 20% מהיתרה שהתקבלה.»
EN: "(3) A bank shall not require life and property insurance for loans up to ₪30,000 or whose balance does not exceed that sum … 'Adjusted unpaid loan balance' = the adjusted loan balance, less the land value attributable to the apartment, plus up to 20% of the resulting balance."

**Q12.3** · S14 [P] — s.11(ה): annual notice (coverage ratio; cancel any time with an alternative policy)
HE: «(2) שיעור הכיסוי בגין כל אחד מהביטוחים. לעניין זה, בביטוח נכס, שיעור הכיסוי הוא הסכום המבוטח חלקי ערך המבנה (כינון); (3) הבהרה כי הלקוח יכול לבטל את הפוליסה בכל עת ללא עמלה, אם יציג בפני התאגיד הבנקאי פוליסת ביטוח חילופית שהתאגיד הבנקאי הוא המוטב הבלתי חוזר בה;»
EN: "(2) the coverage ratio of each insurance; for property insurance, the sum insured divided by the building's (reinstatement) value; (3) a clarification that the customer may cancel the policy at any time without a fee if he presents an alternative policy in which the bank is the irrevocable beneficiary."

**Q12.4** · S14 [P] — s.15ג(א1)–(א2): after repayment — release letter to the insurer; cancel the policy-pledge clause
HE: «התאגיד הבנקאי ימסור ללווה אישור ייעודי, ממוען לחברת הביטוח, הכולל את הסכמת התאגיד הבנקאי להקטנת סכום הביטוח או לביטול השעבוד הקיים לטובת התאגיד הבנקאי. … (א2) … יצוין, בין היתר, כי לאור פירעון ההלוואה מודיע התאגיד הבנקאי, כי ניתן מבחינתו לבטל את סעיף שעבוד הפוליסה לטובתו.»
EN: "The bank shall give the borrower a dedicated letter addressed to the insurer with its consent to reduce the sum insured or cancel the existing pledge in its favor … (a2) … stating that, the loan having been repaid, the bank agrees that the policy-pledge clause in its favor may be cancelled."
Proves: "סעיף שעבוד הפוליסה" (policy pledge clause) is the regulatory term for the bank's lien on the policy.

**Q12.5** · S20 [M] — Banking (Service to Customer) Law s.7 (no tying)
HE: «(א) לא יתנה תאגיד בנקאי מתן שירות בקניית שירות אחר או נכס ממנו או מאדם אחר שהתאגיד ציין, אלא אם קיים קשר עסקי סביר בין השירות המבוקש לבין קיום התנאי.»
EN: "(a) A banking corporation shall not make a service conditional on buying another service or asset from it or from a person it designated, unless there is a reasonable business connection between the requested service and the condition."

**Q12.6** · S22 [F] — Mizrahi: required policies and clauses
HE: «פוליסת ביטוח — הסבר: עליכם לרכוש שני סוגי פוליסות ביטוח: - פוליסת ביטוח חיים - פוליסה עבור כל אחד מהלווים בגובה סכום המשכנתא ולכל תקופתה. הבנק צריך להיות מוטב בלתי חוזר בפוליסה, והפוליסה צריכה להיות משועבדת לבנק מזרחי-טפחות. חשוב לשים לב, כי מספר הסניף וכתובת הסניף רשומים בפוליסה - פוליסת ביטוח נכס - פוליסה בגובה ערך הכינון (הסכום המוערך הדרוש לבניית הנכס מחדש), נתון הזה רושם השמאי. הפוליסה צריכה לכלול את הסעיפים הבאים: א. סעיף שעבוד לטובת בנק מזרחי-טפחות (כולל מספר הסניף וכתובת סניף) ב. רישום הבנק כמוטב בלתי חוזר ג. התחייבות להודעה מוקדמת במקרה של ביטול הפוליסה (30 יום מראש) … באפשרותכם לרכוש את הפוליסות בכל חברת ביטוח ובאמצעות כל סוכנות ביטוח, וגם באמצעות סוכנות הביטוח של הבנק.»
EN: "Insurance policy — you must buy two policies: Life — for each borrower, for the mortgage amount and its whole term; the bank must be irrevocable beneficiary and the policy must be pledged to Mizrahi-Tefahot; make sure the branch number and branch address appear in the policy. Property — for the reinstatement value (estimated cost to rebuild), a figure written by the appraiser; it must include: (a) a pledge clause in favor of Mizrahi-Tefahot (incl. branch number and address); (b) the bank recorded as irrevocable beneficiary; (c) an undertaking to give prior notice of cancellation (30 days in advance) … You may buy the policies from any insurer and through any agency, or through the bank's agency."

**Q12.7** · S21 [P] — Mizrahi guide: property and life insurance terms, partial insurance, exemptions
HE: «ככלל, חובה לבטח כל נכס שישועבד להבטחת ההלוואה (לגבי מי שרכש דירת מגורים מקבלן, החובה לבטח את הנכס תחול רק מהמועד בו התחייב הקבלן למסור את הדירה לקונה).» … «הבנק רשאי לעמוד על קיומם של תנאים הדרושים לשם הבטחת זכויותיו, לרבות קיומם של הסעיפים הבאים: סעיף שעבוד לטובתו וקביעת הבנק כמוטב בנוסח שייקבע על ידי הבנק מעת לעת, סעיף רעידת אדמה וסעיף הודעה מוקדמת של 30 יום במקרה של ביטול הפוליסה. דרישות בקשר לביטוח זה מפורטות במסמכי השעבוד של הנכס אשר יימסרו לכם בתהליך ביצוע ההלוואה.» … «הנכם רשאים לבחור בביטוח בסכום נמוך מסכום ערך הכינון (להלן: "ביטוח חלקי") בסכום שלא יפחת מהיתרה המשוערכת של כל ההלוואות המובטחות בשעבוד אותו הנכס, בניכוי ערך הקרקע המתייחס לדירה, בהתאם להערכת שמאי שתציגו, בתוספת עד 20% מהיתרה שהתקבלה (להלן: "ביטוח לפי יתרה"), ובהיעדר הערכה כאמור - לפי נתונים כלליים שבידי הבנק.» … «הבנק דורש, בדרך כלל, שכל לווה הכשיר לכך, יהיה מבוטח בביטוח חיים ממועד ביצוע ההלוואה ועד למועד פרעונה המלא של ההלוואה, אשר ישולם לבנק לזכות חשבון ההלוואה, במקרה של פטירת הלווה, בסכום יתרת ההלוואה בתוספת עמלת פרעון מוקדם.» … «יתרת כל ההלוואות של הלווה בשעבוד נכס מסוים אינה עולה על 30,000 ₪. לא חלה חובת ביטוח על רכיבי מענק והלוואות עומדות. גיל הלווה בעת ביצוע ההלוואה עולה על 70 שנה.» … «פוליסת ביטוח נכס ופוליסת ביטוח חיים כולל הצהרת בריאות;»
EN: "As a rule every property pledged must be insured (for a new apartment from a contractor — only from the date the contractor undertook to deliver it)." … "The bank may insist on conditions protecting its rights, including: a pledge clause in its favor and naming the bank as beneficiary in wording the bank sets from time to time, an earthquake clause, and a 30-day prior-notice-of-cancellation clause; details are in the property charge documents given during execution." … "You may choose insurance below reinstatement value ('partial insurance') of no less than the adjusted balance of all loans secured by the property, less the land value attributable to the apartment per an appraisal you present, plus up to 20% ('insurance by balance'); absent such an appraisal — per general data held by the bank." … "The bank generally requires every eligible borrower to be life-insured from execution until full repayment, payable to the bank on death, for the loan balance plus the early-repayment fee." … "[Life-insurance exemptions:] total balance secured by the property ≤ ₪30,000; grant components and standing loans; borrower older than 70 at execution." … "Property policy and life policy including a health declaration."

**Q12.8** · S26 [F] — Mizrahi FAQ: how to submit an external policy
HE: «את פוליסות הביטוח ניתן לרכוש בכל חברות הביטוח, או בטפחות סוכנות לביטוח (1989) בע"מ … ניתן לאתר את החברה המבטחת, תוקף הביטוח, סכום הביטוח, כתובת הנכס המבוטח ושמות המבוטחים בביטוח חיים. … פוליסה חדשה למשכנתא קיימת ניתן לשלוח אלינו למייל polisa@umtb.co.il … - לשלוח כל פוליסה במייל נפרד, כקובץ pdf ללא תמונות. … - לרשום את בנק מזרחי-טפחות כמוטב בלתי חוזר ולוודא קיום סעיף הודעה 30 יום לפני ביטול הפוליסה. - לוודא שהסכומים המצוינים בפוליסה תואמים לדרישות הבנק ושתקופת הפוליסה תואמת את תקופת ההלוואה.»
EN: "Policies may be bought from any insurer or from Tefahot Insurance Agency … [In the bank's site you can see] the insurer, insurance validity, sum insured, insured property address and names of life-insured persons. … Send a new policy to polisa@umtb.co.il … each policy in a separate e-mail, as a PDF file without images … record Mizrahi-Tefahot as irrevocable beneficiary and make sure there is a 30-day notice clause before cancellation; make sure the amounts match the bank's requirements and the policy period matches the loan period." (The page also asks to state the borrower's name and the mortgage loan number.)

**Q12.9** · S27 [SN] — Mizrahi checks each policy
HE: «הפוליסה תיבדק על ידינו. לאחר אישור, נשלח אישור מסמך אישור לכתובת שלך המעודכנת בבנק. אם הפוליסה אינה תקינה, נשלח מכתב הכולל הסבר לתיקון הדרוש.»
EN: "The policy will be checked by us. After approval we send a confirmation to your address on file. If the policy is not in order, we send a letter explaining the correction needed."

**Q12.10** · S25 [F] — Mizrahi: external policies; ₪30,000 floor; coverage of the bank-agency structure product
HE: «אם החלטתם לקחת משכנתא במזרחי-טפחות אך לרכוש ביטוח למשכנתא שלא באמצעות טפחות סוכנות לביטוח, יש להמציא לבנק עותק של הפוליסה העונה על דרישות הבנק, בתנאים המפורטים בהסכם ההלוואה.» … «הביטוחים נדרשים עבור כל הלוואה שיתרתה מעל 30,000 ₪.» … «פוליסת הביטוח כוללת, בין היתר, כיסוי נגד הסיכונים העיקריים למבנה כתוצאה מאש, ברק, רעם, רעידת אדמה, שיטפון ועוד, כיסוי נזקי מים ואינסטלציה ודיור חלופי ל-12 חודשים או בגובה 15% מסכום הביטוח (הנמוך מביניהם) …»
EN: "If you take a Mizrahi mortgage but buy insurance not through Tefahot Agency, give the bank a copy of a policy meeting the bank's requirements, under the conditions in the loan agreement." … "Insurance is required for any loan with a balance above ₪30,000." … "[The agency's structure policy] covers, among others, fire, lightning, thunder, earthquake, flood, water and plumbing damage, and alternative housing for 12 months or 15% of the sum insured (lower of the two)…"
Proves: the agency product's coverage; Does not prove: that every external policy must match these coverages (the stated mandatory clauses are in Q12.6–Q12.7).

**Q12.11** · S23 [F] — Mizrahi: property not yet built
HE: «לגבי נכס שבנייתו לא הושלמה, תדרשו להתחייב להמציא פוליסת ביטוח נכס בעתיד לכשתושלם הבנייה.»
EN: "For a property whose construction is not complete, you will be asked to undertake to provide a property policy in the future when construction is completed."

### B13. Seller's existing mortgage — letter of intent, payoff confirmation, lien release

**Q13.1** · S14 [P] — Directive 451 v22, Annex 3: the prescribed "letter of intent to whom it may concern" (field list)
HE: «1. הרינו לאשר כי עם קבלת סך השווה ליתרת ההלוואות הבלתי מסולקות שמספריהן ____ ביום פירעונן בפועל (לרבות עמלות פירעון מוקדם) שחייב לנו (שם הלווה), ואשר בגינן משועבד לנו (פרטי הנכס), (להלן: הנכס), עד ליום (10/MM/YY למכתב כאמור שהוצא מיום ה-26 לחודש הקודם / 25/MM/YY למכתב כאמור שהוצא מיום ה-11 באותו החודש) (מחק את המיותר), נפעל לביטול השעבוד הקיים לטובתנו על הנכס תוך (מספר הימים המדויק על פי סעיף 9א לחוק הבנקאות (שירות ללקוח), התשמ"א-1981), וזאת על פי חובתנו מכוח סעיף 9א … 2. היתרה הבלתי מסולקת של סך ההלוואות האמורות לעיל שבגינן משועבד לנו הנכס, נכון להיום היא: ____. יתרה זו כוללת עמלות פירעון מוקדם בסך של ____. 3. … על מנת לברר את הסכום המדויק לעניין סעיף 1 לעיל, נבקשך לפנות, עובר להעברת הסכום האמור, ל ____. את הסכום יש להפקיד לחשבון (פרטי חשבון התאגיד הבנקאי). 4. התשלום השוטף הקרוב שעתיד להשתלם ביום ____ בגין הלוואה מספר ____ הוא בסך ____ (נדרש פירוט לגבי כל הלוואה בנפרד). 5. לצורך סילוק ההלוואה, הרינו מסכימים שיירשם שעבוד בדרגה (שווה/שניה - מחק את המיותר) על הנכס פרטי הנכס, לזכות (שם הגוף הפיננסי). 6. … אנו נמסור את גובה היתרה המדויקת ליום פירעון ההלוואה למלווה המוסדי שיחזיק במסמך זה … הערה: סעיף 5 ימולא רק בהתקיים מצב כאמור בסעיף 15ב(ג)»
EN (official translation, S15, v22): "1. We hereby confirm that on receipt of a sum equal to the adjusted loan balance, whose numbers are …, on the actual day of payment (including fees for early repayment) owed to us by (name of borrower), and in respect of which (details of the property) … was pledged to us, by (10/MM/YY if such a letter is issued from the 26th of the previous month / 25/MM/YY if such a letter is issued from the 11th of the same month) …, we will act to cancel the existing lien in our favor on the property within (exact number of days according to section 9a of the Banking (Service to the Customer) Law …). 2. The adjusted loan balance … currently stands at …. This balance includes fees for early repayment amounting to …. 3. … To understand fully the exact sum …, we ask you, prior to transferring the said amount, to approach (name). The amount should be deposited in account (details of the banking corporation's account). 4. The next current payment that is expected to be paid on (date) in respect of loan number (number) is for the amount of (amount). (Details for each loan must be given separately). 5. In order to facilitate the payment of the loan, we hereby agree to a (junior/equal) lien on the property … in favor of (name of the financial institution). 6. … we will send the exact amount of loan balance at the date of repayment … Comment: Section 5 will apply only in the situation as described in 15b(c)."
Note: in v22 Hebrew, item 6 addresses "המלווה המוסדי שיחזיק במסמך זה" (the institutional lender holding this document); the English translation still says "the banking corporation in possession of this document". The Hebrew governs.
Proves: a complete field list and a **built-in validity window** (until the 10th or 25th of the month, depending on the issue date).

**Q13.2** · S14 [P] — s.15ב: when it is given and how fast
HE: «15ב. … ימסור התאגיד הבנקאי ללווה, המודיע על כוונתו לבצע פירעון מוקדם, את הפרטים הבאים בכתב: (א) פירוט יתרת ההלוואה לפי מרכיביה השונים והודעה על מועדי מתן אישור הסילוק … (ב) אישור על כך שלאחר פירעון מלא של ההלוואה, יסיר התאגיד הבנקאי את השעבוד המוטל על הנכס … והכל על פי נוסח מכתב הכוונות שבתוספת השלישית. (ג) הודיע הלווה על כוונתו לפרוע את ההלוואה באמצעות הלוואה אחרת ממלווה מוסדי, ימסור התאגיד הבנקאי ללווה את הסכמתו על כך שיירשם שעבוד בדרגה שנייה על הנכס … (ה) התאגיד הבנקאי ימסור את המידע האמור בסעיפים קטנים (ב) ו-(ג) עד שלושה ימי עסקים ממועד הודעתו של הלווה. (ו) … גם באופן מקוון ובטלפון. (ז) … בפורמט המאפשר שמירה והדפסה.»
EN: "15b. … the bank shall give a borrower who announces early repayment, in writing: (a) the balance by components and the dates for the payoff confirmation …; (b) confirmation that after full repayment it will remove the lien … per the letter-of-intent wording in the Third Annex; (c) if repaying through another institutional lender — its consent to a second-rank lien …; (e) items (b)–(c) within three business days of the borrower's notice; (f) also online and by phone; (g) in a format that allows saving and printing."
And s.15ב1 (bank-to-bank delivery of the letter of intent): «(2) התאגיד הבנקאי המקורי יעביר את מכתב הכוונות ומסמכים נוספים הנדרשים ממנו … ישירות אל התאגיד הבנקאי החדש, וימסור ללווה העתק מהמסמכים …» — "the original bank shall send the letter of intent … directly to the new bank and give the borrower a copy". Start date of s.15ב1: «מועד התחילה של סעיף 15ב1 כנוסחו בעדכון מספר 22 להוראה 451 יהיה ביום 1 באפריל 2025.» (S17 [SN]) — "1 April 2025".
Note: s.15ב1 covers refinancing of the borrower's own loan; whether a seller's bank sends the letter directly to the buyer's bank in a purchase is not stated (see E).

**Q13.3** · S24 [F] — Mizrahi's own letter of intent: issue time and validity
HE: «הנפקת מכתב כוונות דיגיטלי — את הבקשה צריכים להגיש לקוחות שמסלקים או ממחזרים משכנתא והתבקשו להנפיק מכתב כוונות הכולל את פרטי הנכס המשועבד להבטחת ההלוואה, כפי שמופיעים ברישומי הבנק. כדי שבמכתב הכוונות יירשמו פרטי הנכס העדכניים ביותר, מומלץ לצרף לבקשה נסח טאבו עדכני או אישור זכויות עדכני. מכתב כוונות מונפק עד 3 ימי עסקים מקבלת הבקשה בבנק. תוקפו של מכתב הכוונות הוא 30 יום מיום הנפקתו. ביום הסילוק יש להתקשר ולברר את היתרה העדכנית …»
EN: "Digital letter of intent — for customers repaying or refinancing who were asked for a letter of intent containing the pledged property's details as recorded by the bank. To get the most current details, attach a current Tabu extract or rights confirmation. Issued within 3 business days of receipt. **Valid for 30 days from issue.** On the payoff day, call to confirm the current balance …"
Conflict note: the BoI template expresses validity as "until the 10th/25th"; Mizrahi states 30 days from issue for letters it issues. Both may need to be supported (see E).

**Q13.4** · S14 [P] — s.15ג(ב)–(ג): payoff confirmation (אישור סילוק)
HE: «(ב) לאחר ביצוע פירעון מלא של ההלוואה, ימסור התאגיד הבנקאי ללווה, תוך חמישה ימי עסקים, אישור סילוק בו ייכתב כי הלווה פרע את מלוא ההלוואה, וכי אין לתאגיד הבנקאי אינטרס בנכס המשועבד, ככל שכך המצב, וכי התאגיד הבנקאי מחויב לבטל את השעבודים בגין ההלוואה תוך פרקי הזמן המפורטים בסעיף 9א לחוק הבנקאות (שירות ללקוח) … (ג) … בנסיבות בהן הפירעון בוצע באמצעות תשלום במזומן או באמצעות העברה בנקאית, והלווה המציא לתאגיד הבנקאי אסמכתא המעידה על ביצוע התשלום, ימסור התאגיד הבנקאי ללווה אישור סילוק הלוואה, לא יאוחר משני ימי עסקים ממועד מסירת האסמכתא.»
EN: "(b) After full repayment the bank shall give the borrower, within five business days, a payoff confirmation stating that the borrower repaid the whole loan, that the bank has no interest in the pledged property (if so), and that the bank must cancel the liens within the periods in s.9a … (c) … where repayment was by cash or bank transfer and the borrower provided proof, the confirmation shall be given within two business days of the proof."

**Q13.5** · S20 [M] — Banking Law s.9א: deletion deadline
HE: «(א) פרע לקוח, בעצמו ולא באמצעות ערב, את כל חיוביו שלהבטחתם נוצרו שעבודים, יבטל התאגיד הבנקאי את השעבודים … היה השעבוד משכנתה או משכון רשום, יגיש התאגיד הבנקאי, תוך 30 ימים מיום הפרעון, הודעה על מחיקת השעבוד למי שאצלו הוא נרשם. … (ג) הוצאות מחיקת רישום משכנתה או משכון כאמור יחולו על התאגיד הבנקאי.»
EN: "(a) Where a customer himself (not via a guarantor) repaid all obligations secured by charges, the bank shall cancel the charges … if the charge is a mortgage or registered pledge, the bank shall file, within 30 days of repayment, a notice of deletion with the body where it is registered. … (c) Deletion costs are borne by the bank."

**Q13.6** · S22 [F] + S21 [P] — Mizrahi: what the buyer's bank needs from the seller's side
HE (S22): «אם המוכרים משלמים משכנתא, יש לצרף מכתב כוונות מהבנק בו מתנהלת המשכנתא שלהם» … «איסור על הסרת שעבודים — אם הנכס משועבד לטובת גורם אחר (למשל בנק אחר), יש להעביר לבנקאי אישור על הסרת השעבודים או מכתב כוונות מהגורם המשעבד»
HE (S21): «אם הנכס משועבד (לדוגמה, להבטחת הלוואה של המוכר) - אישור שחרור השעבוד, אישור סילוק ההלוואה או אישור פרי פסו, הכל כפי שהבנק ידרוש;»
EN: "If the sellers are paying a mortgage, attach a letter of intent from the bank holding their mortgage" … "[heading as printed: 'prohibition on removing charges'] — if the property is charged to another party (e.g., another bank), give the banker a confirmation of removal of the charges or a letter of intent from the chargee." … "If the property is charged (e.g., for the seller's loan) — a charge release, a loan payoff confirmation, or a pari-passu confirmation, as the bank requires."

**Q13.7** · S14 [P] — s.19א: consent to a second-rank charge within 7 days
HE: «19א. תאגיד בנקאי לא יסרב סירוב בלתי סביר לבקשת לווה למתן הסכמתו לשעבוד נכס בדרגה שניה לטובת גורם אחר. אישור כאמור יימסר ללווה תוך שבעה ימים …»
EN: "19a. A bank shall not unreasonably refuse a borrower's request to consent to a second-rank charge in favor of another party; the consent shall be given within seven days …"

### B14. Seller's spouse consent

**Q14.1** · S22 [F] — Mizrahi
HE: «הסכמת בן או בת הזוג למכירת הנכס — אם למוכר/ת יש בן או בת זוג שאינם מופיעים כמוכר בחוזה, נדרש לקבל את הסכמתם. את ההסכמה מקבלים בטופס בשם "החתמת בן זוג של המוכר". את הטופס תקבלו מהבנקאי בטפחות ועליכם להחתים עליו את בן או בת הזוג ואת עורך הדין של המוכרים ולהחזירו לבנקאי» … «צילום תעודת זהות של המוכרים — יש לצרף צילום תעודת זהות, כולל הספח המעיד על המצב המשפחתי של המוכרים»
EN: "Spouse's consent to the sale — if the seller has a spouse who is not a seller in the contract, their consent is required, on a form called 'signature of the seller's spouse', signed by the spouse and the sellers' lawyer and returned to the banker." … "Copy of the sellers' ID cards — including the appendix showing the sellers' marital status."
Proves: a Mizrahi requirement, and the evidence used to detect it (ID appendix). Does not prove: a statutory basis (not found — see D).

**Q14.2** · S12 [P] — ILA: spouses (for undertakings)
HE: «בנכס שנרכש על ידי שני בני זוג לא תנתן התחייבות לרישום משכנתא על שם אחד מבני הזוג אלא רק בהסכמת שני בני הזוג.»
EN: "In a property bought by two spouses, an undertaking to register a mortgage shall not be given in one spouse's name except with both spouses' consent."

### B15. Foreign-resident seller

**Q15.1** · S22 [F] — Mizrahi
HE: «אישור לרישום בפנקסי המקרקעין עבור מוכר תושב חוץ — אם מוכר הדירה הוא תושב חוץ (מזוהה על ידי דרכון), העברת הכספים תמורת הדירה חייבת בניכוי מס במקור. לכן נדרש להציג לסניף, לפני העברת הכספים, טופס בשם "אישור לרישום בפנקסי המקרקעין", אותו יש לבקש מעורך הדין»
EN: "Certificate for registration in the land registers for a foreign-resident seller — if the seller is a foreign resident (identified by passport), transferring the purchase money requires withholding tax at source; therefore, before the funds are transferred, present to the branch a form called 'certificate for registration in the land registers', obtained from the lawyer."

**Q15.2** · S40 [M] — s.49א(א): foreign resident's single-apartment exemption needs a foreign tax authority certificate
HE: «תושב ישראל או תושב חוץ שאין לו דירת מגורים במדינה שבה הוא תושב, המוכר את כל הזכויות במקרקעין שיש לו בדירת מגורים מזכה … יהיה זכאי … לפטור ממס במכירתה; לעניין סעיף קטן זה, יראו תושב חוץ כמי שיש לו דירת מגורים במדינה שבה הוא תושב, כל עוד לא המציא אישור משלטונות המס באותה מדינה כי אין לו דירה כאמור.»
EN: "An Israeli resident, or a foreign resident who has no residential apartment in his country of residence, selling all his rights in a qualifying apartment … is entitled to an exemption …; a foreign resident is deemed to own an apartment in his country of residence as long as he has not produced a certificate from that country's tax authorities that he has none."
Plus s.15(ב) advance payment (Q10.11) applies to all sales. The specific withholding provision Mizrahi refers to was not located (see D).

### B16. Seller who inherited — צו ירושה / צו קיום צוואה

**Q16.1** · S04 [M] — regs 17–18 (registering an inheritance at the Land Registry)
HE: «(א) לעניין סימן זה, ”רישום ירושה“ – לרבות רישום צו ירושה וצו קיום צוואה, הסכם חלוקת עיזבון … צו חלוקת עיזבון … או צו מינוי מנהל עיזבון. (ב) רישום ירושה ייערך על פי בקשה של מעוניין בדבר …» … «(ב) לבקשה יצורף צו ירושה, צו קיום צוואה, צו חלוקת עיזבון, הסכם חלוקת עיזבון או צו מינוי מנהל עיזבון, אם ניתן או אושר בידי בית משפט, בית דין דתי או רשם לענייני ירושה. (ג) מונה מנהל עיזבון, יגיש מנהל העיזבון את הבקשה לרישום ירושה או שהבקשה תוגש בהסכמתו.»
EN: "(a) 'Registration of inheritance' includes registering an inheritance order, probate order, estate-division agreement, estate-division order or an order appointing an administrator. (b) On the application of an interested party …" … "(b) Attach the inheritance order / probate order / division order / division agreement / administrator order, if given or approved by a court, religious court or the Registrar of Inheritance. (c) If an administrator was appointed, he files or consents."

**Q16.2** · S45 [P] — digital orders sent directly to the Land Registry (anti-forgery)
HE: «הרשם מנפיק צו דיגיטלי הנשלח אוטומטית לכתובת הדואר האלקטרוני (למייל) של מגיש הבקשה או עורך הדין שמייצג אותו. לאחר הגשת בקשה לפעולה, מועבר הצו הדיגיטלי ישירות ע"י הרשם גם לבנקים, חברות הביטוח וגופי הממשלה הרלוונטיים, כגון לשכת רישום המקרקעין (ה"טאבו"), רשות מנהל מקרקעי ישראל, רשות המיסים, רשות התאגידים, משרד התחבורה ועוד. העברה ישירה זו זו חוסכת לזוכים את הצורך בהצגת הצו בעת קבלת שירות מגופים אלה ומונעת את האפשרות לזיוף הצו. חשוב לדעת! שירות הפקת צווים דיגיטליים ניתן לגבי כל הצווים שהוציא הרשם החל משנת 1998 …» … «כל הצווים שניתנו ע"י הרשם החל משנת 1998 נמצאים במערכת ארצית של הרשם ומונפקים כצווים דיגיטליים.»
EN: "The Registrar issues a digital order e-mailed automatically to the applicant or his lawyer. After a request for action, the digital order is transmitted directly by the Registrar also to banks, insurers and relevant government bodies such as the Land Registry, the ILA, the Tax Authority, the Corporations Authority, the Ministry of Transport, etc. This direct transfer saves heirs from presenting the order and prevents forgery. Digital orders are available for all orders issued by the Registrar since 1998 …" … "All orders issued by the Registrar since 1998 are in the Registrar's national system and issued as digital orders."

**Q16.3** · S44 [SN] — online lookup and signed copies
HE: «- בקשות שהוגשו לרשם הירושה ומצבן. - צווי ירושה שנתנו על ידי רשם הירושה. - בדיקת קיום בקשת ירושה על מנוח ברשם הירושה, בתי הדין הרבניים ובתי המשפט. … - קבלת העתק מצו שניתן ע"י הרשם לענייני ירושה, חתום בחתימה אלקטרונית או בחיתום אפוסטיל.»
EN: "Requests filed with the Registrar and their status; inheritance orders given by the Registrar; checking whether an inheritance request about a deceased exists at the Registrar, rabbinical courts and courts; … obtaining a copy of an order given by the Registrar, signed electronically or with an Apostille."
Proves: an official verification route (lookup by deceased's ID per SECONDARY guides) and the expected signature (electronic). Does not prove: coverage of orders issued by courts before digitization.

### B17. Other collateral documents the bank collects (Mizrahi)

**Q17.1** · S23 [F] — residential-charge form
HE: «טופס שעבוד דירתי — טופס עליו חותמים הלווים בפני הבנקאי לאחר קבלת הסברים מהבנקאי. … בטופס זה מאשרים את קבלת ההסבר ביחס לזכויות משעבדי דירת המגורים במקרה בו ייאלץ הבנק לממש את המשכנתא ולמכור את הדירה»
EN: "Residential-charge form — signed by borrowers before the banker after explanations … confirming they received the explanation of the rights of mortgagors of a residential apartment if the bank must enforce the mortgage and sell the apartment."

**Q17.2** · S22 [F] / S23 [F] — notarized irrevocable power of attorney
HE (S22): «ייפוי כוח נוטריוני — הסבר: באמצעות טופס זה אתם נותנים לבנק ייפוי כוח להשלים את רישום הנכס על שמכם אם עורך הדין לא יעשה זאת — איפה ואיך מבצעים: את הטופס תקבלו מהבנקאי ועליכם לחתום עליו בפני נוטריון. יש להחזיר לבנקאי את הטופס המקורי, חתום ומאומת על-ידי נוטריון»
EN: "Notarial power of attorney — gives the bank power to complete registration of the property in your names if the lawyer does not; sign before a notary and return the original signed and certified by the notary."

**Q17.3** · S22 [F] — single/replacement apartment affidavit; lease agreement
HE: «תצהיר בנושא בעלות על דירה יחידה או חליפית — … על כל אחד מכם לחתום על טופס נפרד, לדאוג שעורך דין יאמת את החתימה … (רלוונטי במשכנתא בשיעור מימון העולה על 50%)» … «הסכם שכירות — אם הדירה מושכרת יש לצרף את הסכם השכירות שנחתם עם השוכרים»
EN: "Affidavit on owning a single or replacement apartment — each signs a separate form, verified by a lawyer … (relevant where LTV exceeds 50%)." … "Lease agreement — if the apartment is rented, attach the lease signed with the tenants."

**Q17.4** · S21 [P] — waiver of alternative housing in charge documents
HE: «מובהר בזאת, כי הבנק דורש שכל מסמכי השעבוד לצורך ביצוע ההלוואה יכללו ויתור על זכות לקבלת דיור חלופי ו/או במקרים מסויימים, לזכויות דיור מוגן, שעשויות להיות, על פי דין, לבעל דירת מגורים.»
EN: "The bank requires all charge documents to include a waiver of the right to alternative housing and/or, in some cases, of protected-tenancy rights that a residential owner may have by law."

**Q17.5** · S14 [P] + S19 [SN] — the approval in principle lists the documents and sets the document window
HE (S14): «(3) רשימת המסמכים אשר הוא נדרש להמציא לצורך קבלת ההלוואה.» … «(4) התאגיד הבנקאי יקבע תקופה סבירה להמצאת המסמכים הדרושים לאימות הנתונים … תקופה כאמור לא תפחת מ-24 ימים מיום מתן האישור העקרוני …» … «(ז) … במקרה בו האישור העקרוני הינו עבור הלוואה שאין צורך לבצע עבורה שעבוד חדש, לא תפחת התקופה … מ-12 ימים …»
EN (S19, BoI): "The list of required documents will be provided with the approval in principle." EN (S14): "(3) the list of documents he must provide … (4) the bank shall set a reasonable period to provide the documents … not less than 24 days from the approval in principle … (g) … for a loan not requiring a new charge, not less than 12 days."
Mizrahi (S21) maps this to rate-lock validity: «אם על פי אישור הבקשה להלוואה לא נדרש רישום שעבוד נוסף להבטחת ההלוואה - תוקף שמירת הריבית יהיה 12 יום מיום האישור.» — "if no additional charge is needed — the rate is held 12 days from approval" (24 days where a new charge is needed, first approval).

---

## (C) Suggested extraction fields per document

Field names are proposals for the schema; the **Basis** column says whether a source requires or names the field. Types: `str`, `date`, `datetime`, `int`, `money` (ILS unless stated), `bool`, `enum`, `list<…>`.

### C1. Land Registry extract (נסח רישום)

| Field | Type | Notes | Basis |
| --- | --- | --- | --- |
| `extract_type` | enum: `regular_full` / `historical` / `concentrated` / `historical_scanned` / `partial` | First three official; last two seen only in a secondary source | SOURCE-BACKED for first three (S01 Q1.4); PROPOSED for last two (S47) |
| `issued_at` | datetime | "correct as of the day it was produced" | SOURCE-BACKED (S01 Q1.3); time component PROPOSED |
| `gush`, `chelka` | int | Primary property keys | SOURCE-BACKED (S01/S02 Q1.5) |
| `tat_chelka` | int / null | Required for condominium units; ≠ apartment number | SOURCE-BACKED (S02 Q1.5) |
| `registry_office` | str | Office where the land is registered | PROPOSED (regs refer to "הלשכה שרשומים בה המקרקעין", S04 reg 21/18) |
| `register_type` | enum: rights / condominium / deeds | The three registers | SOURCE-BACKED (S04 reg 7) |
| `registered_owners[]` | list<{name, id_type, id_number, share}> | Owners SOURCE-BACKED; ID and share as columns PROPOSED | SOURCE-BACKED: owners (S01 Q1.2); PROPOSED: subfields |
| `mortgages[]` | list<{mortgagee, rank, amount, deed_no, date}> | | SOURCE-BACKED: existence (S01 Q1.2); PROPOSED: subfields |
| `attachments_and_orders[]` | list<{type, issuer, date, ref}> | עיקולים, צווים שיפוטיים | SOURCE-BACKED (S01 Q1.2) |
| `restrictions[]` | list<str> | הגבלות | SOURCE-BACKED (S01 Q1.2) |
| `notes[]` | list<{note_type: 126_transaction / 126_refrain / 128_consent / 129 / court / other, beneficiary, date, ref}> | Includes warning notes | SOURCE-BACKED: note types (S05 ss.126–130; S06 Q5.5); PROPOSED: subfields |
| `leases[]` | list<{lessee, start, end, capitalized}> | חכירות | PROPOSED (secondary descriptions only) |
| `area_sqm`, `attached_areas[]`, `common_property_share`, `bylaws_note` | various | הצמדות, חלק ברכוש המשותף, תקנון | PROPOSED (secondary only) |
| `esignature_valid` | bool | Validate the approved electronic signature on the PDF | SOURCE-BACKED (S01/S02 Q1.6; S04 reg 92) |
| `is_digital_original` | bool | False for printouts/scans → not a true copy | SOURCE-BACKED (S04 reg 92(ג) Q1.7) |
| `apostille` | bool | | SOURCE-BACKED (S01 Q1.1) |
| `post_registration_extract` | bool | Extract produced after warning-note registration | SOURCE-BACKED (S22 Q1.13) |

### C2. ILA rights confirmation / notice (אישור זכויות / הודעה על רישום זכויות בנכס)

| Field | Type | Notes | Basis |
| --- | --- | --- | --- |
| `ila_doc_type` | enum: `rights_confirmation` / `rights_registration_notice` / `database_printout` | Printout is not binding (secondary) | SOURCE-BACKED for first two (S11 Q2.1); printout from SECONDARY (S13 Q2.5) |
| `issued_at` | date | | PROPOSED |
| `ila_file_or_contract_no` | str | Used in ILA release letters | PROPOSED (named for release letters in S12 Q7.4) |
| `gush`, `chelka`, `migrash`, `address` | | | PROPOSED (gush/chelka/address named in S12 Q7.4) |
| `rights_holders[]` | list<{name, id_number}> | | PROPOSED (named for release letters in S12 Q7.4) |
| `right_type`, `agreement_period` | | lease / capitalized lease / development contract | PROPOSED (Standard 19 lists lease terms, S35) |
| `remark_registrable_in_tabu` | bool + text | Blocks ILA activity incl. mortgage undertakings | SOURCE-BACKED (S11 Q2.3(a)) |
| `remark_agreement_expired` | bool + text | Blocks ILA activity | SOURCE-BACKED (S11 Q2.3(b)) |
| `legal_notes[]` | list<enum: legal_handling, receivership, attachment, injunction, pledge, court_order, charge> | | SOURCE-BACKED (S11 Q2.3(c)) |
| `mortgage_undertakings[]` | list<{lender, amount, rank, date}> | Existence SOURCE-BACKED; subfields PROPOSED | SOURCE-BACKED (S11 Q2.3(d)) |
| `irregularities[]` | list<enum: nonconforming_use, building_deviation, encroachment> | | SOURCE-BACKED (S11 Q2.3(e)) |
| `debts_flag` | bool | | SOURCE-BACKED (S11 Q2.3(f)) |
| `pending_transfer_request` | bool | | SOURCE-BACKED (S11 Q2.3(g)) |
| `signer_name`, `signer_role` | str | Must be an authorized ILA role | SOURCE-BACKED (S11 Q2.4) |
| `requested_by_bank_under_poa` | bool | Bank holding an undertaking may request | SOURCE-BACKED (S11 Q2.2) |

### C3. Housing-company / developer rights confirmation

| Field | Type | Notes | Basis |
| --- | --- | --- | --- |
| `issuer_company_name`, `issuer_company_no` | str | | PROPOSED |
| `project_name`, `building_no`, `apartment_no`, `gush`, `chelka`, `migrash` | | | PROPOSED |
| `rights_holders[]` {name, id_number, share} | | Must match seller(s) | PROPOSED |
| `registration_status` (not yet registered as condominium / pending) | enum | | PROPOSED |
| `charges_and_undertakings[]` (incl. undertaking to register a mortgage) | list | | PROPOSED |
| `issued_at`, `signatory` | | | PROPOSED |
| `ila_notice_exists` | bool | ILA issues only a "notice" for such properties | SOURCE-BACKED (S11 Q2.1) |

### C4. New-build securities

**C4a. Sale Law bank guarantee (ערבות חוק מכר)**

| Field | Type | Basis |
| --- | --- | --- |
| `guarantee_date` | date | SOURCE-BACKED (S30 Q4.5 "תאריך") |
| `beneficiary_buyers[]` | list<str> | SOURCE-BACKED (S30 "לכבוד … הרוכש") |
| `apartment.gush`, `.chelka`, `.plan`, `.plot`, `.building_no`, `.apartment_no` | | SOURCE-BACKED (S30 "פרטי הדירה") |
| `seller_details` | str | SOURCE-BACKED (S30) |
| `issuing_bank_details` | str | SOURCE-BACKED (S30) |
| `guarantee_amount` | money | SOURCE-BACKED (S30) |
| `indexation` | enum: construction_inputs / cpi / fx(currency) | SOURCE-BACKED (S30) |
| `base_index_rule` | str ("index known on the day paid to the seller") | SOURCE-BACKED (S30) |
| `demand_address` | str | SOURCE-BACKED (S30) |
| `vat_excluded` | bool | SOURCE-BACKED (S30; S29 s.2(1)) |
| `irrevocable_payment_instruction_to_lender` | bool + lender name | SOURCE-BACKED mechanism (S30 "המחאת הזכויות"); endorsement required by bank (S21 Q4.7; S15 s.7a) |
| `bank_signature_and_stamp` | bool | SOURCE-BACKED (S30) |
| `guarantee_number`, `project_name` | str | PROPOSED |

**C4b. Payment voucher / voucher booklet (פנקס שוברים)**

| Field | Type | Basis |
| --- | --- | --- |
| `accompaniment_account_no` (6 digits), `branch_no` (3 digits), `project_name` | str | SOURCE-BACKED (S28 Q4.9) |
| `one_booklet_per_apartment` | bool | SOURCE-BACKED (S29 s.3ב Q4.3) |
| `voucher_no`, `amount`, `apartment_id`, `buyer_ids`, `paid_at` | | PROPOSED (voucher content set by the Supervisor — not retrieved) |

**C4c. Exclusion letter (הודעה בדבר מחיקת רישום שעבוד / "מכתב החרגה")**

| Field | Type | Basis |
| --- | --- | --- |
| `issuer` (bank / insurer / other guarantor) | str | SOURCE-BACKED (S29 s.2ג Q4.4) |
| `commitment_not_enforce_and_delete` | bool + conditions text | SOURCE-BACKED (S29 s.2ג(ב)) |
| `seller_request_date`, `issue_date` (≤30 days after request) | date | SOURCE-BACKED timing (S29 s.2ג(ב)–(ג)) |
| `apartment_identifiers`, `buyer_names_ids`, `project`, `signatures` | | PROPOSED (Schedule form not retrieved) |

### C5. Warning note application (בקשה לרישום הערת אזהרה) and registered note

| Field | Type | Basis |
| --- | --- | --- |
| `registry_office` | str | SOURCE-BACKED (S08 form header "לשכת רישום המקרקעין ב-") |
| `property_description` (gush/chelka/tat-chelka) | | SOURCE-BACKED (S08 "1. תיאור המקרקעין") |
| `note_basis` | enum: 126_transaction / 126_refrain / 128_consent | SOURCE-BACKED (S08; S05) |
| `obligor[]` {surname_or_corp, first_name, id_type, id_number, address, right_nature, share_in_right} | | SOURCE-BACKED (S08 section 3) |
| `beneficiary[]` {surname_or_corp, first_name, id_type, id_number, address} | | SOURCE-BACKED (S08 section 4) |
| `attached_docs` | enum set: agreement / irrevocable_poa / other | SOURCE-BACKED (S08 section 5) |
| `registered_owner_consent` (if obligor ≠ registered owner) | bool | SOURCE-BACKED (S04 reg 21(ב)(2)) |
| `lawyer_verification` {name, license_no, date, stamp} | | SOURCE-BACKED (S04 reg 21(א); S08) |
| `corporate_docs_confirmation` | bool | SOURCE-BACKED (S08; S04 reg 21(ב)(3)) |
| `joint_consent_form` (bank form "בהסכמת כל הצדדים") + linking keys {bank, property, amount} | | SOURCE-BACKED (S09 Q5.7; S22 Q5.8) |
| `registration_confirmation` | bool | SOURCE-BACKED (S22 Q1.13) |

### C6. Mortgage deed (שטר משכנתה) / registered mortgage

| Field | Type | Basis |
| --- | --- | --- |
| `property_details`, `mortgagor_details`, `mortgagee_bank`, `special_conditions` | | SOURCE-BACKED (S24 Q6.2) |
| `deed_no`, `rank`, `amount_or_obligations`, `schedule_of_land`, `third_party_rights_statement`, `warning_note_deletion_consent` | | PROPOSED (official deed form seen only as a third-party copy) |
| `signature_verified_at` | date | SOURCE-BACKED for validity check (S09 Q6.4) |

### C7. Undertaking to register a mortgage (התחייבות לרישום משכנתא)

| Field | Type | Basis |
| --- | --- | --- |
| `issuer_type` | enum: ILA / housing_company / contractor+registered_owners / seller | SOURCE-BACKED (S12 Q7.1; S21 Q3.1–Q3.3, Q5.9) |
| `lender_name` | str | SOURCE-BACKED (S12 "לטובת הגורם המלווה") |
| `rights_holders[]` {name, id_number} | | SOURCE-BACKED for ILA release letters (S12 Q7.4); PROPOSED for the undertaking itself |
| `gush`, `chelka`, `address` | | same as above |
| `undertaking_amount` (incl. "unlimited") | money / "unlimited" | SOURCE-BACKED (S12 Q7.5) |
| `mortgage_rank` | int | SOURCE-BACKED (S12 Q7.4) |
| `undertaking_date`, `ila_contract_or_file_no` | | SOURCE-BACKED (S12 Q7.4) |
| `signed_by_all_sellers`, `lawyer_verified` | bool | SOURCE-BACKED (S22 Q7.6; S23 Q4.8) |
| `spouses_both_consented` (ILA, spouse-owned) | bool | SOURCE-BACKED (S12 Q7.2) |

### C8. Pledge registration (הודעת משכון) and inspection report (דוח עיון)

| Field | Type | Basis |
| --- | --- | --- |
| `registration_period_years`, `pledge_end_date` | int, date | SOURCE-BACKED (S34 Form 1 item 1) |
| `creditors[]`, `debtors[]` {name, id_type, id_number, address} | | SOURCE-BACKED (S34 items 2–3) |
| `pledgor_for_another` | bool | SOURCE-BACKED (S34 item 4) |
| `asset_unregistered_land_right` {gush, chelka, tat_chelka, migrash, street, house_no, apartment, locality, description} | | SOURCE-BACKED (S34 item 5) |
| `additional_pledge_clause`, `reg5d_note` | bool | SOURCE-BACKED (S34 items 8–9) |
| `pledge_registration_no`, `fee_receipt_no` | str | SOURCE-BACKED (S34 office-use section) |
| `deceased_debtor_with_order` | bool | SOURCE-BACKED (S33 reg 5(ה)) |
| `inspection_report.search_id`, `.produced_online` | str, bool | SOURCE-BACKED (S33 regs 13–13א; S23 Q8.2) |
| `inspection_report.is_formal_registration_report` | bool (false if online) | SOURCE-BACKED (S33 reg 13א(ב) Q8.4) |
| `inspection_report.active_pledges[]` | list | PROPOSED |

### C9. Purchase agreement (הסכם מכר)

| Field | Type | Basis |
| --- | --- | --- |
| `is_written_and_signed` | bool | SOURCE-BACKED (S05 s.8; S21 "חתום כחוק") |
| `seller_bank_account` + proof document | str | SOURCE-BACKED (S21 Q9.4) |
| `seller_id_copy` (incl. appendix) | doc ref | SOURCE-BACKED (S21 Q9.4; S22 Q14.1) |
| `consideration`, `transaction_date` | money, date | SOURCE-BACKED as tax-declaration content (S38 Q9.3) — PROPOSED as contract fields |
| `payment_schedule[]` {date, amount} | | SOURCE-BACKED as operative date (S15 s.6(a) Q9.5); fields PROPOSED |
| `delivery_date` (new build) | date | SOURCE-BACKED as operative (S15 s.11(c) Q9.5) |
| `specification_attached_signed` (new build) | bool | SOURCE-BACKED (S31 s.2) |
| `sale_law_notice_given` (new build) | bool | SOURCE-BACKED (S29 s.2א1) |
| `tax_approvals_before_last_tranche` / `trust_account` | bool / str | SOURCE-BACKED as bank practice (S22 Q9.6) |
| `parties[]` {name, id, role}, `property_ids` {gush, chelka, tat_chelka, address, apartment_no, attachments}, `price`, `possession_date`, `warning_note_clause`, `mortgage_financing_clause`, `seller_mortgage_payoff_clause`, `lawyers[]` {name, license_no}, `signature_dates` | | PROPOSED (no official field list found) |

### C10. Tax and municipal clearances

| Document / field | Type | Basis |
| --- | --- | --- |
| Tax certificate for registration: `tax_type` (betterment / purchase / sale-tax 2000–2007 / property tax) | enum | SOURCE-BACKED (S09 Q10.4) |
| … `addressed_to_land_registrar` | bool | SOURCE-BACKED (S09) |
| … `gush`, `chelka`, `tat_chelka` (must equal the register) | | SOURCE-BACKED (S09 1.1.2) |
| … `route` (16(א)(2) / 16(א)(2א)) | enum | SOURCE-BACKED (S40; S39) |
| … `certificate_no`, `parties`, `issued_at` | | PROPOSED |
| Purchase-tax assessment notice & voucher: `assessment_no`, `amount_due`, `paid` | | SOURCE-BACKED that a notice + voucher exist (S38 Q10.3); fields PROPOSED |
| Declarations (form 7000): contents per S38 | | SOURCE-BACKED (S38 Q9.3) |
| Municipal certificate (s.324): `signed_by_mayor_or_delegate` | bool | SOURCE-BACKED (S41 Q10.5) |
| … `debts_cleared_to_date` | date | SOURCE-BACKED (S41) |
| … `valid_until` | date | SOURCE-BACKED for Tel Aviv (≤1 year, S42); "valid on filing date" (S09) |
| … `property_ids`, `owner_name`, `certificate_no` | | PROPOSED |
| Betterment-levy certificate: `signed_by_committee_chair_or_delegate`, `levy_paid_or_secured` | | SOURCE-BACKED (S43 Q10.7) |

### C11. Appraisal report (שומת מקרקעין)

| Field | Type | Basis |
| --- | --- | --- |
| `appraisal_type` (title) + `written_at` | enum + date | SOURCE-BACKED (S36) |
| `assumption_based` (title contains "מבוססת הנחה") | bool | SOURCE-BACKED (S36) |
| `orderer` + `relation_to_property` (e.g., bank officer) | str | SOURCE-BACKED (S36; S35 4.2) |
| `purpose` | str | SOURCE-BACKED (S36; S37 item 5) |
| `valuation_date` | date | SOURCE-BACKED (S36; S37 item 7) |
| `visit_date`, `visitor` | date, str | SOURCE-BACKED (S36; S37 item 6; S15 s.10(b)) |
| `property_identification` {location, nature, area, gush, chelka/plot, address} | | SOURCE-BACKED (S37 item 1; S36) |
| `property_description`, `planning_status`, `rights_appraised`, `licensing_status` | | SOURCE-BACKED (S37 items 2–4, 11; S36) |
| `drawing_of_property` | bool | SOURCE-BACKED (S15 s.10(a)) |
| `principles`, `calculations` | text | SOURCE-BACKED (S37 items 8, 12; S36) |
| `appraised_value` (amount or range) | money | SOURCE-BACKED (S36 6.12) |
| `reinstatement_value` | money | SOURCE-BACKED as Mizrahi input (S21/S22 Q11.10); method SOURCE-BACKED only for Std-19 (S35 4.16) |
| `appraiser_signature` (wet on print / approved e-sign on file) | enum + valid | SOURCE-BACKED (S36 6.13) |
| `no_personal_interest_declaration` | bool | SOURCE-BACKED (S36 6.14) |
| `success_fee_disclosure` | bool | SOURCE-BACKED (S37 item 13) |
| `requesting_bank`, `appraiser_on_bank_panel` | str, bool | SOURCE-BACKED for reuse check (S14 s.9(ה)) |
| `delivered_directly_by_appraiser` | bool | SOURCE-BACKED as Mizrahi process (S22 Q11.5) |
| `appraiser_name`, `license_no`, `market_value_inputs`, `net_area`, `condition` | | PROPOSED |
| Standard-19 extras (`value_for_security`, `forced_sale_factor`, `taxes_on_realization`) | | SOURCE-BACKED only when a Std-19 appraisal is ordered (S35); PROPOSED otherwise |

### C12. Life insurance policy (mortgage)

| Field | Type | Basis |
| --- | --- | --- |
| `insurer` | str | SOURCE-BACKED (S26) |
| `insured_persons[]` (each borrower) | list | SOURCE-BACKED (S22 Q12.6; S26) |
| `sum_insured` | money | SOURCE-BACKED (S22 "בגובה סכום המשכנתא"; S21 "יתרת ההלוואה בתוספת עמלת פרעון מוקדם") |
| `policy_period` = loan term | dates | SOURCE-BACKED (S22 "לכל תקופתה"; S26) |
| `irrevocable_beneficiary` = lending bank | bool + name | SOURCE-BACKED (S14 s.11(a); S22; S26) |
| `policy_pledged_to_bank` incl. `branch_no`, `branch_address` | | SOURCE-BACKED (S22 Q12.6) |
| `cancellation_notice_days` (=30) | int | SOURCE-BACKED (S21; S26) |
| `health_declaration_attached` | bool | SOURCE-BACKED (S21 Q12.7) |
| `borrower_name`, `mortgage_loan_no` (on submission) | str | SOURCE-BACKED (S26) |
| `policy_no`, `start_date`, `premium`, `track_breakdown` | | PROPOSED |

### C13. Property / structure insurance policy

| Field | Type | Basis |
| --- | --- | --- |
| `insurer`, `insured_property_address` | str | SOURCE-BACKED (S26) |
| `sum_insured` + `basis` (reinstatement / by-balance) | money + enum | SOURCE-BACKED (S21 Q12.7; S22) |
| `pledge_clause_in_favor_of_bank` incl. `branch_no`, `branch_address` | | SOURCE-BACKED (S22 Q12.6) |
| `irrevocable_beneficiary` = bank | bool | SOURCE-BACKED (S14 s.11(a); S22) |
| `cancellation_notice_days` (=30) | int | SOURCE-BACKED (S21; S22; S26) |
| `earthquake_clause` | bool | SOURCE-BACKED (S21) |
| `policy_period` vs loan term | dates | SOURCE-BACKED (S26) |
| `start_date` (new build ≥ contract delivery date allowed) | date | SOURCE-BACKED (S14/S15 s.11(c)) |
| `coverages[]`, `deductible`, `policy_no` | | PROPOSED |

### C14. Seller's bank letter of intent / payoff confirmation

| Field | Type | Basis |
| --- | --- | --- |
| `issuing_bank` | str | SOURCE-BACKED (S14 Annex 3) |
| `loan_numbers[]` | list<str> | SOURCE-BACKED (Annex 3 item 1) |
| `borrower_name` | str | SOURCE-BACKED (item 1) |
| `property_details` | str | SOURCE-BACKED (item 1) |
| `valid_until` (10th or 25th rule) | date | SOURCE-BACKED (item 1) |
| `issue_date` | date | PROPOSED (implied by the 10th/25th rule; Mizrahi 30 days from issue, S24) |
| `lien_cancellation_days` (per s.9א) | int | SOURCE-BACKED (item 1) |
| `outstanding_balance_as_of` + `early_repayment_fees` | money | SOURCE-BACKED (item 2) |
| `contact_for_exact_amount` | str | SOURCE-BACKED (item 3) |
| `deposit_account` {bank, branch, account} | | SOURCE-BACKED (item 3) |
| `next_payment[]` {date, loan_no, amount} | list | SOURCE-BACKED (item 4) |
| `consent_second_or_equal_lien` + `in_favor_of` | enum + str | SOURCE-BACKED (item 5; only under s.15ב(ג)) |
| Payoff confirmation: `full_repayment_confirmed`, `no_interest_in_property`, `lien_cancellation_obligation` | bool | SOURCE-BACKED (S14 s.15ג(ב) Q13.4) |
| Lien release: `release_doc_type` (release / payoff / pari-passu) | enum | SOURCE-BACKED (S21 Q13.6) |

### C15–C17. Seller-side status documents

| Document / field | Basis |
| --- | --- |
| Spouse consent form ("החתמת בן זוג של המוכר"): `signed_by_spouse`, `signed_by_sellers_lawyer` | SOURCE-BACKED (S22 Q14.1) |
| … `spouse_name`, `spouse_id`, `property_ids`, `date` | PROPOSED |
| Seller ID copy incl. appendix: `marital_status`, `spouse_listed` | SOURCE-BACKED (S22 Q14.1) |
| Foreign-resident seller: `identified_by_passport`, `certificate_for_registration_presented_before_disbursement` | SOURCE-BACKED (S22 Q15.1) |
| … `foreign_tax_authority_no_apartment_certificate` (if exemption claimed) | SOURCE-BACKED (S40 s.49א Q15.2) |
| Inheritance: `order_type` (inheritance / probate / division order / division agreement / administrator) | SOURCE-BACKED (S04 reg 17) |
| … `issuing_body` (court / religious court / Registrar) | SOURCE-BACKED (S04 reg 18(ב)) |
| … `electronic_signature_valid`, `verified_via_registrar_lookup` | SOURCE-BACKED (S44 Q16.3; S45 Q16.2) |
| … `deceased_name`, `deceased_id`, `heirs[]` {name, id, share}, `order_no`, `order_date`, `inheritance_registered_in_tabu` | PROPOSED |

### Cross-document checks (rules the system can run)

| # | Check | Basis |
| --- | --- | --- |
| X1 | Gush/Chelka/Tat-Chelka identical across extract, contract, appraisal, warning-note application, mortgage deed or undertaking, pledge notice, tax certificates, guarantee (new build), letter of intent | Tax certificates: SOURCE-BACKED (S09 1.1.2). Others: PROPOSED |
| X2 | Do **not** compare Tat-Chelka with the apartment number | SOURCE-BACKED (S02) |
| X3 | Sellers in the contract = registered owners on the extract (or rights holders on ILA/housing-company confirmation); if the obligor of a warning note is not the registered owner → registered owner's consent required | SOURCE-BACKED for consent (S04 reg 21(ב)(2)); name match PROPOSED |
| X4 | Seller undertaking and warning-note form signed by **all** sellers and lawyer-verified | SOURCE-BACKED (S22 Q7.6, Q5.8) |
| X5 | Post-registration extract shows warning notes for both the buyers and the bank | SOURCE-BACKED (S22 Q1.13; S21 Q5.9) |
| X6 | Existing mortgage on the extract → require letter of intent / release / payoff / pari-passu; letter of intent not past its `valid_until` (BoI 10th/25th; Mizrahi 30 days) | SOURCE-BACKED (S21, S22, S14 Annex 3, S24) |
| X7 | Attachments, orders or restrictive notes on the extract/ILA confirmation → escalate | SOURCE-BACKED purpose (S23 Q1.12); ILA blocking remarks (S11 Q2.3; S12 Q7.3) |
| X8 | Extract, appraisal, ILA confirmation, death/inheritance orders: reject printed copies of e-signed files where a digital original is expected | SOURCE-BACKED for extracts (S04 reg 92); appraisal e-sign (S36 6.13); PROPOSED for others |
| X9 | Appraisal from another bank: ≤90 days old and appraiser on the bank's panel | SOURCE-BACKED (S14 s.9(ה)) |
| X10 | Appraisal: visit ≤3 months before issue; visit date and visitor stated; signature valid; "assumption-based" flagged | SOURCE-BACKED (S36; S15 s.10(b)) |
| X11 | Insurance: beneficiary = lending bank; pledge clause with branch no. & address; 30-day cancellation clause; earthquake clause (property); sum and period ≥ requirement; property sum ≈ appraisal reinstatement value or ≥ by-balance minimum | SOURCE-BACKED (S22, S21, S26, S14 s.11) |
| X12 | Insurance start for a new apartment may be the contract delivery date | SOURCE-BACKED (S14/S15 s.11(c)) |
| X13 | Municipal certificate valid on the filing date (Tel Aviv: ≤1 year from fee) — needed for transfer, **not** for mortgage registration | SOURCE-BACKED (S09; S42; S41(ד)) |
| X14 | Tax approvals present before the last tranche (or trust account evidenced) | SOURCE-BACKED as Mizrahi practice (S22 Q9.6) |
| X15 | New build: payments only via vouchers to the accompaniment account; guarantee amount covers payments made (excl. VAT); guarantee endorsed to the bank; exclusion letter obtained | SOURCE-BACKED (S29 ss.2, 3ב, 2ג; S30; S21; S23) |
| X16 | Transaction/mortgage deed age ≤1 year from signature verification (≤3 years with lawyer confirmation) | SOURCE-BACKED (S09 Q6.4) |
| X17 | Seller via inheritance: order exists, type and issuing body recorded, verified on the Registrar system; inheritance registered (or registration filed) | SOURCE-BACKED (S04 regs 17–18; S44; S45) |
| X18 | Foreign-resident seller (passport) → "אישור לרישום בפנקסי המקרקעין" before disbursement | SOURCE-BACKED (S22 Q15.1) |
| X19 | Seller's spouse not in the contract (per ID appendix) → spouse-consent form | SOURCE-BACKED as Mizrahi practice (S22 Q14.1) |
| X20 | Reject look-alikes as substitutes: MOCH registration-status printout; ILA database printout | SOURCE-BACKED (S10 Q1.10); SECONDARY for ILA printout (S13) |
| X21 | Pledge: one inspection report per borrower/mortgagor ID; registration period covers the loan | SOURCE-BACKED for reports (S22, S23); period-covers-loan PROPOSED |

---

## (D) NOT FOUND (could not be verified from an authoritative source in this session)

1. **A verification code or online authenticity-lookup service for Land Registry extracts.** Only the approved electronic signature on the digital file is documented (S01, S04).
2. **Any official validity / maximum-age period for a Land Registry extract** (official text says only "correct as of the day it was produced"). Mizrahi's required recency for the extract is not published on the pages read. The 2-month rule in Standard 19 applies only to credit-security appraisals.
3. **The official section/column layout of an extract** (owners with ID and share, leases with end date, area, attached areas, common-property share). Regulations delegate the form to the Chief Registrar (S04 reg 8); only secondary descriptions were found.
4. **The ILA rights confirmation's official template, its validity period**, and the ILA web page itself (gov.il blocked). The "database printout is not binding" text was seen only in a third-party reproduction (S13).
5. **Any official definition, template or validity for a housing company's own rights confirmation.**
6. **The prescribed form of the Sale Law exclusion notice** (Schedule to s.2ג) — omitted on Wikisource ("הושמטה"); not retrieved elsewhere.
7. **The Supervisor of Banks' specification of voucher contents** (Sale Law s.3ב(ב)).
8. **Capital Market Authority circulars on mortgage life/structure insurance** — minimum coverage, policy-pledge wording, or a "רשימת דרישות מינימליות" (minimum-requirements list). The CMA calculators (life.cma.gov.il, dira.cma.gov.il) responded but their content was not retrieved; no CMA circular surfaced in search.
9. **A regulatory list of minimum requirements for an external mortgage policy.** Only Directive 451 s.11 (bank may insist on conditions protecting its rights) and Mizrahi's own clause list were found.
10. **Israel Bar Association guidance on purchase-agreement contents**, and an official gov.il field list for a second-hand purchase agreement.
11. **A statutory basis for requiring the seller's spouse's consent** in an ordinary sale (found only as Mizrahi practice and as an ILA rule for mortgage undertakings on spouse-owned property).
12. **The specific statutory withholding mechanism for a foreign-resident seller** that Mizrahi cites (s.15(ב) advance payment applies to all sales; s.49א concerns the exemption). The exact form name/issuer of "אישור לרישום בפנקסי המקרקעין" for this case was not confirmed on a Tax Authority page.
13. **Validity period of Tax Authority certificates for registration**, and whether they are transmitted electronically to the Land Registry (only a news report on personal-area downloads, S46).
14. **The "details required by the authorized government ministries for directed-loan apartment appraisals"** referenced by Directive 451 s.10(b).
15. **The official mortgage-deed form on gov.il** (only a third-party copy was seen in search).
16. **Mizrahi's internal form templates** (seller undertaking, residential-charge form, spouse-consent form, payment-on-account form, equity-paid confirmation, pledge deed) — not public.
17. **Bank of Israel circular 2160 (2005) on marketing life/structure insurance with housing loans** — page behind a bot wall.
18. **Any Directive 451 version after version 22 (7/23)** — none found (only the postponement of s.15ב1 to 1.4.2025); cannot be excluded.
19. **ILA Procedure 90.02B Appendix 2** (companies that do not issue mortgage undertakings) — not reproduced in the PDF.

---

## (E) Open questions for the bank (Mizrahi-Tefahot) and legal

1. **Recency rules.** What maximum age does Mizrahi accept for a Tabu extract, an ILA rights confirmation and a housing-company confirmation — at approval in principle, at signing, and at each disbursement? Is a fresh extract required on the disbursement day?
2. **Digital originals.** Must the extract (and ILA confirmation, inheritance order, appraisal) be the signed digital file? How should scans, printouts and forwarded e-mails be treated? Which certificate authorities should the PDF-signature validator trust?
3. **Extract type.** When is a historical extract required (recent transfers, fraud signals, inheritance chains)? Is a concentrated extract ever acceptable?
4. **ILA and housing companies.** For ILA land, is only a signed "אישור זכויות" acceptable (never a database printout)? For housing-company properties, what must the company's confirmation contain, and is the ILA "notice on registration of rights" also needed?
5. **Letter of intent validity.** Which governs a disbursement: the BoI template's 10th/25th "valid until" date, or Mizrahi's 30-days-from-issue rule? Are other banks' letters on non-standard templates accepted? Does the seller's bank deliver the letter directly to Mizrahi in a purchase (as s.15ב1 does for refinancing)?
6. **Pledges.** Is the online "דוח עיון" sufficient, given reg. 13א(ב) says it is not a formal registration report? What registration period must the pledge cover?
7. **Warning notes.** Must both the buyer's and the bank's notes appear on a post-registration extract before the first disbursement? In new-build projects with guarantees and vouchers, is a bank warning note also mandatory?
8. **Appraisal configuration.** Confirm the appraisal-type thresholds (value, LTV, credit amount, property type) from the guide as system configuration; who verifies "appraiser on our panel" for a reused appraisal; how a report sent by the customer (not the appraiser) should be handled.
9. **Insurance wording.** Exact required pledge-clause and beneficiary wording ("בנוסח שייקבע על ידי הבנק"); minimum structure coverages beyond earthquake; how to compute the "insurance by balance" minimum (land-value source); acceptable insurers.
10. **Spouse consent.** Trigger conditions (marital status on the ID appendix? community-property concerns?), acceptable form, and the legal basis legal wants cited.
11. **Foreign-resident seller.** Which certificate exactly (issuer, form number), and before which tranche?
12. **Inherited property.** Must the inheritance be registered at the Tabu before signing/disbursement, or is an order plus a filed registration acceptable?
13. **Municipal certificate.** Given s.324(ד), when does the bank still require it (buyer's transfer only), and should validity be checked per municipality's own rule?
14. **Tax approvals.** Which approvals must exist before which tranche (contract-driven vs. mandatory)? What does "מש"ח" in the Mizrahi checklist stand for, and what document is it?
15. **Sale Law checks.** Must the system reconcile guarantee amounts against payments made, confirm endorsement to Mizrahi, and confirm an exclusion letter? Mizrahi's voucher-validation tool covers Mizrahi-accompanied projects only — what is the check for other banks' projects?
16. **Deed age.** Should the system enforce the 1-year (≤3 years with lawyer confirmation) deed-validity rule on mortgage deeds before submission?
17. **Directive 451 currency.** Confirm with Compliance that version 22 (7/23) is the latest consolidated text and whether any later Supervisor letters change sections 9–11, 15ב–15ג or Annex 3.

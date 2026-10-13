# R5 — Reading Israeli mortgage documents: OCR, document-AI and LLM capabilities (verified 2026-10-12)

**Scope.** Current (2026-10-12) capabilities relevant to extracting fields, with page + bounding-box evidence, from Israeli mortgage documents: Hebrew RTL text mixed with English and digits, tables, payslips, bank statements, and scanned or photographed PDFs.

**Method.** Every claim below is tied to a source ID from section A. Each source was fetched on **2026-10-12** from the vendor's official documentation (or the project's official repository for open-source tools), and the quotes are copied verbatim. Where a page could not be read directly, the source entry says so. Anything that could not be confirmed is labelled **NOT VERIFIED** and collected in section F. One small **local experiment** (E1) was run to observe real RTL extraction behaviour. It is labelled as our own test, not vendor documentation.

**Labels used:** `VERIFIED` = quoted from an official source today. `NOT VERIFIED` = no official confirmation found. `LOCAL TEST` = our own experiment (E1). `ENGINEERING` = a design recommendation inferred from the cited facts, not a vendor statement.

---

## Executive summary (10 points)

1. **No managed document-AI or LLM service in this review was verified to process data inside Israel.** Gemini on Vertex lists only `global`/`us`/`eu` for current models [V2][V3]. Document AI offers `us`/`eu` plus 7 non-Israeli single regions [D5]. Azure Document Intelligence is not offered in Israel Central [A7][A8]. Textract has no `il-central-1` endpoint [W3]. Claude's inference geo is `us`/`global` only [C4]. OpenAI has no Israel region [O2]. Israeli cloud regions do exist (GCP `me-west1` [V7], Azure Israel Central [A9], AWS `il-central-1` [W4]), so **only self-hosted OCR (Tesseract, Surya, docTR) can keep processing in Israel**.
2. **Printed Hebrew** is supported by Google Document AI OCR [D1], Azure Read/Layout [A1], Tesseract `heb` [T1], and Surya 2 (vendor-reported 90.9% on its own benchmark [S2]). Gemini lists Hebrew as a supported language [V1], but no official Hebrew OCR accuracy is published. **AWS Textract does not support Hebrew** [W1][W2]. **PaddleOCR PP-OCRv5 does not list Hebrew** [P1].
3. **Hebrew handwriting is not supported** by Document AI ("Not Supported") [D1], Azure v4.0 (Hebrew is absent from the handwriting list) [A1], or Textract (English only) [W2]. Gemini and the open-source tools: NOT VERIFIED. Route handwriting to human review.
4. **Word-level boxes with confidence** come from Document AI (tokens with `boundingPoly` and a `[0,1]` confidence) [D2][D3], Azure (word `polygon` and `confidence`) [A2], Tesseract TSV/hOCR [T9], docTR [R2], and PyMuPDF for born-digital PDFs [M1]. **Gemini has no native word boxes**: it returns prompted `box_2d` as `[ymin, xmin, ymax, xmax]` normalized to 0–1000, documented for images [G2]. Claude citations give **page ranges only** and cannot cite images [C2].
5. **Prebuilt bank-statement and payslip models are US/English-only**: Azure `prebuilt-bankStatement.us` and `prebuilt-payStub.us` are en-US [A4][A5][A6], and Document AI's Bank Statement and Pay Slip parsers are English-only [D1]. Hebrew payslips and statements need generic OCR plus our own schema.
6. **Gemini (current: `gemini-3.8-flash`, GA 2026-09-02) [G6][V2]:** PDFs up to 50 MB / 1000 pages on the Gemini API [G1], or 3,000 pages per file on Vertex [V2]. Gemini 3 also feeds the PDF's embedded text to the model [G1]. PDF OCR quality "typically saturates at `medium`" resolution [G3]. In `generateContent`, `responseSchema` is now **deprecated** ("Use responseFormat instead") [G5]. Gemini 2.5 Pro on Vertex retires **2026-10-20** [V3].
7. **Data use:** paid Gemini API use is not used to improve Google products [G7]; Vertex will not "train or fine-tune any AI/ML models without your prior permission" [V6]; OpenAI API data is not used for training by default [O2]; Anthropic retained data "is never used for model training without your express permission" [C5]. **Textract by default may use content to improve the service** unless you opt out [W1]. **Unpaid Gemini use must not receive personal data** [G7].
8. **The PDF text layer is the cheapest and most exact source, but RTL order is unreliable.** In our local test with 4 producers (E1), PyMuPDF's *word tokens* were letter-correct in every case, but line order varied by producer. pdfplumber's default output came out in visual order ("רכש" instead of "שכר"), and `char_dir="rtl"` **reversed the digits** ("76.543,21" instead of "12,345.67"). Use word tokens plus geometry; never trust the content-stream order.
9. **Authenticity:** online Land Registry (Tabu) extracts carry an "approved electronic signature" and are official only in digital form [IL1]. pyHanko can validate PDF signatures against explicit trust roots [H2], but its incremental-update difference analysis is "(very) experimental" [H1]. Metadata (Producer, ModDate) and incremental-save counts (`version_count`) [M6] are **weak** signals only.
10. **LLM-as-judge:** use explicit rubrics with binary outputs [J9]; correct for position bias by swapping order [J1][J2]; use self-consistency voting [J4]; calibrate and allow abstention, escalating low-confidence cases to humans [J5][J6][J7].

---

## A. Source inventory

All sources were retrieved **2026-10-12**. Where a page shows "Last updated", it is noted. Quotes are verbatim; "…" marks an omission.

### A.1 Google Gemini API (ai.google.dev)

- **[G1]** https://ai.google.dev/gemini-api/docs/document-processing (Last updated 2026-10-08)
  - "Gemini models can process documents in PDF format, using native vision to understand entire document contexts."
  - "Gemini supports PDF files up to 50MB or 1000 pages. This limit applies to both inline data and Files API uploads. Each document page is equivalent to 258 tokens."
  - "larger pages are scaled down to a maximum resolution of 3072 x 3072 while preserving their original aspect ratio, while smaller pages are scaled up to 768 x 768 pixels."
  - "Native text inclusion: Text natively embedded in the PDF is extracted and provided to the model."
  - "Rotate pages to the correct orientation before uploading." / "Avoid blurry pages."
  - "Analyze and interpret content, including text, images, diagrams, charts, and tables, even in long documents up to 1000 pages."
- **[G2]** https://ai.google.dev/gemini-api/docs/image-understanding
  - "Models are trained to detect objects in an image and get their bounding box coordinates. The coordinates, relative to image dimensions, scale to [0, 1000]. You need to descale these coordinates based on your original image size."
  - "The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000."
  - "Inline image data limits your total request size (text prompts, system instructions, and inline bytes) to 20MB."
  - "Gemini models support a maximum of 3,600 image files per request."
- **[G3]** https://ai.google.dev/gemini-api/docs/media-resolution (Last updated 2026-09-23)
  - PDFs, recommended `medium`, 560 max tokens: "Optimal for document understanding; quality typically saturates at `medium`. Increasing to `high` rarely improves OCR results for standard documents."
  - "Setting the `resolution` on individual content items is exclusive to Gemini 3 models."
- **[G4]** https://ai.google.dev/gemini-api/docs/structured-output (Last updated 2026-09-23)
  - "You can configure Gemini models to generate responses that adhere to a provided JSON Schema."
  - "Gemini's structured output mode supports a subset of the JSON Schema specification."
  - "`format`: Specifies a syntax for the string, such as `date-time`, `date`, `time`."
  - "Validation: While output is syntactically correct JSON, always validate values in your application."
  - "Schema complexity: Very large or deeply nested schemas may be rejected."
- **[G5]** https://ai.google.dev/api/generate-content (Last updated 2026-09-23)
  - "responseSchema (deprecated) … This item is deprecated! … Deprecated. Use responseFormat instead."
- **[G6]** https://ai.google.dev/gemini-api/docs/models (Last updated 2026-10-09)
  - Table rows: "Gemini 3.8 Flash | gemini-3.8-flash"; "Gemini 3.1 Pro | gemini-3.1-pro-preview"; "Gemini 3.5 Flash-Lite | gemini-3.5-flash-lite".
  - "For any new projects, use our latest models: 3.5 Flash-Lite or 3.8 Flash."
- **[G7]** https://ai.google.dev/gemini-api/terms ("Effective March 23, 2026")
  - Paid: "Google doesn't use your prompts (including associated system instructions, cached content, and files such as images, videos, or documents) or responses to improve our products".
  - Paid: "This data may be stored transiently or cached in any country in which Google or its agents maintain facilities."
  - Unpaid: "Do not submit sensitive, confidential, or personal information to the Unpaid Services."
- **[G8]** https://ai.google.dev/gemini-api/docs/available-regions (Last updated 2026-04-28). "Israel" appears in the list of available regions.

### A.2 Google Cloud: Vertex AI (now titled "Gemini Enterprise Agent Platform") and Compute

- **[V1]** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/google-models (Last updated 2026-10-09)
  - "All the Gemini models can understand and respond in the following languages: … Hebrew (`iw`) …"
- **[V2]** https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash
  - "Maximum number of pages per file: 3,000"; "Maximum file size per file for the API or Cloud Storage imports: 50 MB(application/pdf)".
  - "Supported regions — Model availability: Global: `global` Multi-region: `us`, `eu`"; "ML processing: Multi-region: `us`, `eu`".
  - "`gemini-3.8-flash` Launch stage: GA Release date: September 2, 2026".
- **[V3]** Model pages under `…/models/gemini/{3-7-flash, 3-6-flash, 3-5-flash, 3-5-flash-lite, 3-1-pro, 2-5-flash, 2-5-pro}`. **None of them contains `me-west1`.** Examples:
  - 3.7 Flash: "Model availability Global: global Multi-region: us , eu ML processing Multi-region: us , eu".
  - 3.1 Pro preview: "Model availability Global: global".
  - 2.5 Pro: "Retirement date † : October 20, 2026".
- **[V4]** https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations
  - "Important: Endpoints don't guarantee data residency or in-region ML processing."
  - "Don't use the global endpoint if you have ML processing requirements, because you can't control or know which region your ML processing requests are sent to when a request is made."
  - The Middle East table has a column "Tel Aviv (me-west1)". Its per-model availability marks are rendered client-side and were empty in the static HTML, so they are unreadable (see section F).
- **[V5]** https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/data-residency
  - "Requests submitted to a `global` endpoint may be processed in any Google Cloud location around the world, and therefore don't provide any data residency guarantees."
  - The per-model ML-processing table has columns for US, EU, Brazil, Canada, France, Germany, Netherlands, UK, Australia, India, Japan, Singapore and South Korea. **There is no Israel column.**
- **[V6]** https://docs.cloud.google.com/vertex-ai/generative-ai/docs/data-governance (Last updated 2026-10-09)
  - "Google won't use your data to train or fine-tune any AI/ML models without your prior permission or instruction. This applies to all managed models on Gemini Enterprise Agent Platform, including GA and pre-GA models."
  - "Google may log prompts to detect potential abuse and violations of its Acceptable Use Policy and Prohibited Use Policy".
- **[V7]** https://docs.cloud.google.com/compute/docs/regions-zones. "me-west1-a Tel Aviv, Israel, Middle East".

### A.3 Google Cloud Document AI

- **[D1]** https://docs.cloud.google.com/document-ai/docs/languages (Last updated 2026-10-09)
  - Enterprise Document OCR: "This processor allows you to identify and extract text, including handwritten text, from documents in more than 200 languages."
  - Language table row: "Hebrew | `iw` | `Hebr`". The handwriting cell is marked `aria-label="Not Supported"`, whereas English, Arabic, Japanese and Russian are `aria-label="Supported"`. This was read from the raw HTML.
  - Hebrew is also listed for Form Parser, Layout Parser and Custom Extractor.
  - Custom Extractor: "If using generative AI for extraction, then: Only the English language is officially supported."
  - Bank Statement Parser and Pay Slip Parser: supported languages are "English | `en`" only.
- **[D2]** https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr
  - "Enterprise Document OCR can detect blocks, paragraphs, lines, words, and symbols from PDFs and images, as well as deskew documents for better accuracy."
  - "Extract embedded or native text from digital PDFs: This feature extracts text and symbols exactly as they appear in the source documents, even for rotated texts, extreme font sizes or styles, and partially hidden text."
  - "Image-quality score provides you with page-level quality metrics in eight dimensions, including blurriness, the presence of smaller-than-usual fonts, and glare."
  - "Font style detection: Identify word-level font properties including font type, font style, handwriting, weight, and color."
  - "Note: Pages are 1-indexed."
- **[D3]** https://docs.cloud.google.com/document-ai/docs/reference/rest/v1/Document (Last updated 2026-10-09)
  - "confidence … Confidence of the current Layout within context of the object this layout is for. For example, confidence can be for a single token, a table, a visual element, etc. depending on context. Range [0, 1]."
  - "NOTE: the vertex coordinates are in the same scale as the original image."
- **[D4]** https://docs.cloud.google.com/document-ai/limits (Last updated 2026-10-09)
  - "Enterprise Document OCR … Maximum pages (online/synchronous requests): 15 Maximum pages (batch/offline/asynchronous requests): 500 Maximum pages (imageless mode online/synchronous requests): 30".
  - "Maximum file size for online processing requests 40 MB".
- **[D5]** https://docs.cloud.google.com/document-ai/docs/regions (Last updated 2026-10-09)
  - "Document AI supports the following multi-region locations: us (United States) eu (European Union) Document AI provides limited support for the following single-region locations: asia-south1 (Mumbai) asia-southeast1 (Singapore) australia-southeast1 (Sydney) europe-west2 (London) europe-west3 (Frankfurt) europe-west4 (Amsterdam) northamerica-northeast1 (Montréal)".
- **[D6]** https://docs.cloud.google.com/document-ai/docs/layout-parse-chunk
  - "pretrained-layout-parser-v1.6-2026-01-13 Preview version powered by Gemini 3.0 Flash LLM. Note: This processor version uses the Vertex AI Gemini global endpoint and is not compliant with Data Residency (DMZ) standards."
  - "Tables spanning multiple pages might be split in two tables."
- **[D7]** https://docs.cloud.google.com/document-ai/docs/release-notes. February 16, 2026: "Bounding box support only exists for version processor pretrained-layout-parser-v1.0-2024-06-03."

### A.4 Microsoft Azure Document Intelligence (now titled "Azure Document Intelligence in Foundry Tools")

- **[A1]** https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/ocr?view=doc-intel-4.0.0
  - Read, printed text: "Hebrew | `he`". Layout, printed text: "Hebrew | `he`".
  - Read and Layout, handwritten text (v4.0): the only languages listed are English, Japanese, Chinese Simplified, Korean, French, Portuguese, German, Spanish, Italian, Russian, Thai and Arabic. **Hebrew is not listed.**
- **[A2]** https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/read?view=doc-intel-4.0.0
  - "The model outputs bounding `polygon` coordinates and `confidence` for the extracted words."
  - "For PDFs and TIFFs, up to 2,000 pages can be processed." / "The file size for analyzing documents is 500 MB for the paid (S0) tier and 4 MB for the free (F0) tier."
  - "The minimum height of the text to be extracted is 12 pixels for a 1024 x 768-pixel image. This dimension corresponds to about 8-point text at 150 dots per inch."
  - "The response includes classifying whether each text line is of handwriting style or not, along with a confidence score."
  - "The searchable PDF capability enables you to convert an analog PDF, such as scanned-image PDF files, to a PDF with embedded text."
- **[A3]** https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0
  - "Each cell with its bounding polygon is output along with information whether the area is recognized as `columnHeader` or not. The model supports extracting tables that are rotated."
  - "Do your tables span multiple pages? If so, … split the PDF into pages before you send it to Document Intelligence. After the analysis, post-process the pages to a single table."
- **[A4]** https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/language-support/prebuilt?view=doc-intel-4.0.0
  - "Model ID: prebuilt-bankStatement | English (United States) `en-US`"; "Model ID: prebuilt-paystub | English (United States) `en-US`".
  - The invoice model lists "Hebrew (`he`)" and the currency code "`ILS` | Israeli New Shekel (`il`)". The mortgage models (1003/1004/1005/1008/closingDisclosure) are en-US.
- **[A5]** https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/bank-statement?view=doc-intel-4.0.0
  - "…analyze and extract data from US bank statements." Model ID `prebuilt-bankStatement.us`.
  - "The prebuilt-bankStatement.us version 2027-11-30 supports the en-us locale." (The year is reproduced as written on the page.)
- **[A6]** https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/pay-stub?view=doc-intel-4.0.0
  - Model ID `prebuilt-payStub.us`. "The prebuilt-payStub.us version supports the en-us locale."
- **[A7]** https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/table. Parsed from the page's embedded dataset:
  - Records for "Azure AI Document Intelligence" exist for 35 regions, including Qatar Central and UAE North, but **not for Israel Central**.
  - The Israel Central record list includes "Microsoft Foundry / Azure Machine Learning" and "Azure AI Search", but not Document Intelligence.
- **[A8]** https://azure.microsoft.com/en-us/pricing/details/document-intelligence/
  - The region selector contains `<option class="fake-disabled" aria-disabled="true" value="israel-central">Israel Central</option>`, together with the page message "Pricing is not available in the selected region". Qatar Central, UAE North and West Europe are enabled.
- **[A9]** https://learn.microsoft.com/en-us/azure/reliability/regions-list. "Israel Central | 3 | N/A | Israel | Israel | israelcentral".
- **[A10]** https://learn.microsoft.com/en-us/rest/api/aiservices/document-classifiers/get-classify-result?view=rest-aiservices-v4.0%20(2024-11-30)
  - "The unit used by the width, height, and polygon properties. For images, the unit is "pixel". For PDF, the unit is "inch"."

### A.5 AWS

- **[W1]** https://aws.amazon.com/textract/faqs/
  - "Amazon Textract can extract printed text, forms and tables in English, German, French, Spanish, Italian and Portuguese."
  - "(Currently English, Spanish, Italian, Portuguese, French, German. Handwriting, Invoices and Receipts, Identity documents and Queries processing are in English only)."
  - "A confidence score is a number between 0 and 100".
  - "Amazon Textract may store and use document and image inputs processed by the service solely to provide and maintain the service and to improve and develop the quality of Amazon Textract and other Amazon machine-learning/artificial-intelligence technologies." Opt-out is via an AWS Organizations policy.
- **[W2]** https://docs.aws.amazon.com/textract/latest/dg/limits-document.html
  - "Amazon Textract supports English, French, German, Italian, Portuguese, and Spanish text detection."
  - "Handwritten character recognition is only supported in English."
  - "PDF and TIFF files have a limit of 500 MB in memory and a limit of 3,000 pages."
- **[W3]** https://docs.aws.amazon.com/general/latest/gr/textract.html. The endpoint list has no `il-central-1` and no "Israel" entry.
- **[W4]** https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html. "il-central-1 Israel (Tel Aviv)".

### A.6 Open-source OCR

- **[T1]** https://tesseract-ocr.github.io/tessdoc/Data-Files.html
  - "heb Hebrew heb.traineddata".
  - "tessdata_best (Sep 2017) best results on Google's eval data, slower, Float models."
  - "only the new LSTM-based OCR engine (–oem 1) is supported".
- **[T2]** https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html. Lists language "heb Hebrew" and script "hebr Hebrew".
- **[T3]** https://github.com/tesseract-ocr/tessdata_best. A GitHub API listing shows `heb.traineddata` at 3,704,077 bytes.
- **[T4]** https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html. "Tesseract works best on images which have a DPI of at least 300 dpi, so it may be beneficial to resize images."
- **[T5]** https://github.com/tesseract-ocr/tesseract/issues/2897 (maintainer comment, 2020-02-29). "There are some minor issues with RTL languages related to the the bidi handling in Tesseract. There is no known solution in Tesseract itself."
- **[T6]** https://github.com/tesseract-ocr/tesseract/issues/2263 (2019-02-23). "This is not the case with all RTL languages. Hebrew numbers are recognized correctly." Also: "The numbers are being recognized correctly, except for the corner case where line begins with a number (28 is recognized as 8)."
- **[T7]** https://github.com/tesseract-ocr/tesseract/issues/1102 (2018-01-04). "It turns out it was indeed a training issue. After training "heb" can get the number correctly."
- **[T8]** https://github.com/tesseract-ocr/langdata/issues/82 (opened 2017-07-27, still open). "9 nikud signs are missing." / "Also missing are the 3 unique Hebrew punctuation marks I mentioned earlier." The marks referred to are MAQAF, GERESH and GERSHAYIM.
- **[T9]** https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
  - The TSV header row is "level page_num block_num par_num line_num word_num left top width height conf text".
  - The hOCR example output includes `title='bbox 300 388 444 413; x_wconf 92'`.
  - "This creates a pdf with the image and a separate searchable text layer with the recognized text."
- **[T10]** GitHub API, latest release: Tesseract **5.5.3** (2026-07-24).
- **[P1]** https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md
  - "PP-OCRv5 offers multilingual text recognition capabilities covering 106 languages". **Hebrew is absent** from "4. Supported Languages and Abbreviations" (checked by searching the raw file).
  - Latest release v3.7.0 (2026-06-11).
- **[R1]** https://github.com/mindee/doctr/blob/main/doctr/datasets/vocabs.py
  - `VOCABS["hebrew"] = ( _BASE_VOCABS["digits"] + _BASE_VOCABS["punctuation"] + _BASE_VOCABS["hebrew_consonants"] + …`.
  - The `VOCABS["multilingual"]` definition does **not** include the Hebrew vocab.
  - Latest release v1.1.0 (2026-08-21).
- **[R2]** https://mindee.github.io/doctr/using_doctr/using_models.html
  - Example output: `'words' : [ { 'value' : 'No.' , 'confidence' : 0.914085328578949 , 'geometry' : (( 0.5478515625 , 0.06640625 ), ( 0.5810546875 , 0.0966796875 ))`.
  - Table predictor: "returns the list of detected cells, each with its geometry, its confidence score and its logical coordinates".
- **[S1]** https://github.com/datalab-to/surya (README; latest release v0.22.1, 2026-07-20)
  - "Multilingual - scores 87.2% on an internal benchmark set of 91 languages".
  - Output fields: "`polygon` - 4-corner polygon"; "`bbox` - axis-aligned `[x0, y0, x1, y1]` derived from the polygon"; "`confidence` - mean per-token probability across the block's decode (0-1)".
  - "We also ship smaller models for line-level text detection".
  - "The model weights use a modified AI Pubs Open Rail-M license (free for research, personal use, and startups under $5M funding/revenue)."
- **[S2]** https://github.com/datalab-to/surya/blob/master/static/docs/multilingual.md. "| `he` | Hebrew | 90.9% |" (vendor's internal benchmark).

### A.7 PDF text-layer tools

- **[M1]** https://pymupdf.readthedocs.io/en/latest/app1.html ("covers all versions up to 1.28.2", Last updated 03 Sep 2026)
  - WORDS output: "( x0 , y0 , x1 , y1 , "word" , block_no , line_no , word_no ) Where the first 4 items are the float coordinates of the words's bbox."
  - RAWDICT output: "the "text" items ( string ) in the spans are replaced by the list "chars" . Each "chars" entry is a character dict". Each entry has `"origin"`, `"bbox"` and `"c"`.
  - "The output may not equal an accustomed "natural" reading order. However, you can request a reordering following the scheme "top-left to bottom-right" by executing page.get_text("text", sort=True)."
- **[M2]** https://pymupdf.readthedocs.io/en/latest/vars.html
  - "TEXT_PRESERVE_LIGATURES … If set, ligatures are passed through to the application in their original form. … Default is "on" in PyMuPDF. MuPDF supports the following 7 ligatures: "ff", "fi", "fl", "ffi", "ffl", , "ft", "st"."
  - "TEXT_USE_CID_FOR_UNKNOWN_UNICODE … Use raw character codes instead of U+FFFD. This is the default for text extraction in PyMuPDF. If you want to detect when encoding information is missing or uncertain, toggle this flag and scan for the presence of U+FFFD (= chr(0xfffd) ) code points in the resulting text."
  - "TEXT_ACCURATE_BBOXES … Ignore metric values of all fonts when computing character boundary boxes".
  - "TEXT_COLLECT_STYLES … the flag bit will also cause MuPDF to detect "fake bold" text."
- **[M3]** https://pymupdf.readthedocs.io/en/latest/textpage.html. "MuPDF uses the page's top-left point as (0, 0) . In PDF, this is the bottom-left point. Therefore, the positive direction for MuPDF's y-axis is from top to bottom."
- **[M4]** https://pymupdf.readthedocs.io/en/latest/changes.html
  - 1.24.14 (2024-11-19): "Ensure that words from Page.get_text() never contain RTL/LTR char mixtures."
  - 1.28.2 (2026-08-06): "Option for reproducible/deterministic save output (omit MuPDF version banner + Producer)"; "pymupdf.Page.find_tables(): * new args use_layout…".
- **[M5]** https://pymupdf.readthedocs.io/en/latest/recipes-text.html. "If line["dir"] != (1, 0) , then the text of all its spans is rotated by (the same) angle != 0. The "bboxes" returned by the method however are rectangles only – not quads."
- **[M6]** https://pymupdf.readthedocs.io/en/latest/document.html
  - metadata: "Keys are format , encryption , title , author , subject , keywords , creator , producer , creationDate , modDate , trapped".
  - version_count: "Zero if not a PDF, otherwise the number of incremental saves plus one."
  - get_sigflags(): "-1: not a Form PDF / no signature fields recorded / no SigFlags found. 1: at least one signature field exists. 3: contains signatures that may be invalidated if the file is saved (written) in a way that alters its previous contents, as opposed to an incremental update."
  - is_repaired: "True if PDF has been repaired during open (because of major structure issues)."
- **[L1]** https://github.com/jsvine/pdfplumber (README, `stable`; latest release v0.11.10, 2026-06-15)
  - `.extract_words(… use_text_flow=False, line_dir="ttb", char_dir="ltr", … expand_ligatures=True, return_chars=False)`.
  - "valid options are "ttb" (top-to-bottom), "btt" (bottom-to-top), "ltr" (left-to-right), and "rtl" (right-to-left)."
  - use_text_flow: "(This mimics how dragging a cursor highlights text in a PDF; as with that, the order does not always appear to be logical.)"
  - "`.extract_tables(table_settings={})` | Returns the text extracted from *all* tables found on the page".

### A.8 PDF signatures and Israeli source documents

- **[H1]** https://docs.pyhanko.eu/en/latest/cli-guide/validation.html
  - "PDF files can be modified, even when signed, by appending data to the end of the previous revision. These are incremental updates."
  - "PyHanko attempts to run a difference analysis on incremental updates, and processes modifications on a reject-by-default basis … However, this feature is (very) experimental, and shouldn't be relied on too much."
  - "PyHanko currently does not offer validation of structural PAdES profile requirements".
  - "By default, pyHanko requires signer certificates to have the non-repudiation key usage extension bit set on signer certificates."
- **[H2]** https://docs.pyhanko.eu/en/latest/lib-guide/validation/general-api.html
  - Example: `vc = ValidationContext(trust_roots=[root_cert])` … `status = validate_pdf_signature(sig, vc)`.
  - "Specifying trust_roots (or a trust_manager ) is optional today: if you leave it out, the ValidationContext falls back to the operating system's trust list."
- **[H3]** https://docs.pyhanko.eu/en/latest/lib-guide/validation/diff-analysis.html
  - "PyHanko takes a reject-by-default approach".
  - "you might want to rely on the coverage property of PdfSignatureStatus instead."
- **[H4]** https://docs.pyhanko.eu/en/latest/lib-guide/validation/status.html. "if all you're interested in is a yes/no judgment, use the the bottom_line property."
- **[H5]** https://pypi.org/project/pyHanko/. Current version **0.37.0**.
- **[IL1]** https://www.gov.il/he/service/land_registration_extract/ (Land Registration and Settlement of Rights Authority). Direct fetch returned a bot-protection page, so the text below comes from the search engine's index snapshot of this official page, retrieved 2026-10-12:
  - "הנסח כולל חתימה אלקטרונית מאושרת." ("The extract includes an approved electronic signature.")
  - "הנסח רשמי ומוכר כמסמך מקורי רק בצורה דיגיטלית ולא כשהוא מודפס." ("The extract is official and recognized as an original document only in digital form, not when printed.")

### A.9 Anthropic Claude

- **[C1]** https://docs.claude.com/en/docs/build-with-claude/pdf-support
  - "Maximum request size | 32 MB (varies by platform)"; "Maximum pages per request | 600 (100 when the request's context window is under 1M tokens)".
  - "The system converts each page of the document into an image." / "The text from each page is extracted and provided alongside each page's image."
- **[C2]** https://docs.claude.com/en/docs/build-with-claude/citations
  - "For PDFs: Citations include the page number range (1-indexed)." / "Page numbers are 1-indexed with exclusive end page numbers."
  - "Citing images from PDFs is not currently supported." / "Only text citations are currently supported. Image citations are not yet possible."
  - "citations are guaranteed to contain valid pointers to the provided documents."
  - "Citations cannot be used together with structured outputs."
- **[C3]** https://docs.claude.com/en/docs/about-claude/models/overview
  - Claude API IDs: `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`; 1M-token context.
  - "All current models support text and image input, text output, multilingual capabilities, vision, and tool use."
- **[C4]** https://platform.claude.com/docs/en/build-with-claude/data-residency. "Inference geo: Only "us" and "global" are available. Workspace geo: Only "us" is currently available."
- **[C5]** https://platform.claude.com/docs/en/manage-claude/api-and-data-retention
  - "Retained data is never used for model training without your express permission."
  - "Claude Fable 5.1, Claude Mythos 5.1, Claude Fable 5, and Claude Mythos 5: These models require 30-day data retention and are not available under ZDR unless expressly authorized by Anthropic."

### A.10 OpenAI

- **[O1]** https://platform.openai.com/docs/guides/pdf-files
  - "PDF files: On models with vision capabilities, such as `gpt-4o` and later models, the API extracts both text and page images and sends both to the model."
  - "each file must be under 50 MB. The combined limit across all files in the request is 50 MB."
  - PDF `detail` can be `auto`, `low` or `high`.
- **[O2]** https://platform.openai.com/docs/guides/your-data
  - "As of March 1, 2023, data sent to the OpenAI API is not used to train or improve OpenAI models (unless you explicitly opt in to share data with us)."
  - Abuse-monitoring logs are "retained for up to 30 days".
  - Data-residency regions: United States, Europe (EEA + Switzerland), Australia, Canada, Japan, India, Singapore, South Korea, United Kingdom, United Arab Emirates. **There is no Israel region.**

### A.11 LLM-as-a-judge references

Paper abstracts were verified via the arXiv API.

- **[J1]** Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, arXiv:2306.05685, https://arxiv.org/abs/2306.05685. "We examine the usage and limitations of LLM-as-a-judge, including position, verbosity, and self-enhancement biases, as well as limited reasoning ability".
- **[J2]** Wang et al., *Large Language Models are not Fair Evaluators*, arXiv:2305.17926, https://arxiv.org/abs/2305.17926
  - "the quality ranking of candidate responses can be easily hacked by simply altering their order of appearance in the context."
  - Proposed fixes: "Multiple Evidence Calibration … Balanced Position Calibration … Human-in-the-Loop Calibration".
- **[J3]** Liu et al., *G-Eval*, arXiv:2303.16634, https://arxiv.org/abs/2303.16634
  - "a framework of using large language models with chain-of-thoughts (CoT) and a form-filling paradigm".
  - "the potential issue of LLM-based evaluators having a bias towards the LLM-generated texts."
- **[J4]** Wang et al., *Self-Consistency Improves Chain of Thought Reasoning in Language Models*, arXiv:2203.11171, https://arxiv.org/abs/2203.11171. "It first samples a diverse set of reasoning paths instead of only taking the greedy one, and then selects the most consistent answer by marginalizing out the sampled reasoning paths."
- **[J5]** Kadavath et al., *Language Models (Mostly) Know What They Know*, arXiv:2207.05221, https://arxiv.org/abs/2207.05221. "larger models are well-calibrated on diverse multiple choice and true/false questions when they are provided in the right format."
- **[J6]** Jung, Brahman, Choi, *Trust or Escalate: LLM Judges with Provable Guarantees for Human Agreement*, arXiv:2407.18370, https://arxiv.org/abs/2407.18370. "assess the confidence of judge models and selectively decide when to trust its judgement".
- **[J7]** Wen et al., *Know Your Limits: A Survey of Abstention in Large Language Models*, arXiv:2407.18418, https://arxiv.org/abs/2407.18418. "Abstention, the refusal of large language models (LLMs) to provide an answer, is increasingly recognized for its potential to mitigate hallucinations and enhance safety in LLM systems."
- **[J8]** Gu et al., *A Survey on LLM-as-a-Judge*, arXiv:2411.15594, https://arxiv.org/abs/2411.15594. "This paper provides a comprehensive survey of LLM-as-a-Judge, addressing the core question: How can reliable LLM-as-a-Judge systems be built?"
- **[J9]** Anthropic, *Create strong empirical evaluations*, https://docs.claude.com/en/docs/test-and-evaluate/develop-tests
  - "Have detailed, clear rubrics".
  - "Empirical or specific: For example, instruct the LLM to output only 'correct' or 'incorrect', or to judge from a scale of 1–5."
  - "Encourage reasoning: Use a grader model with thinking on".
  - "LLM-based grading: Fast and flexible, scalable and suitable for complex judgment. Test to ensure reliability first then scale."

### A.12 Local experiment

- **[E1]** `LOCAL TEST`, run 2026-10-12 on macOS 26.5.1 with Python 3.14.8, PyMuPDF 1.28.2 (MuPDF 1.28.2), pdfplumber 0.11.10 and python-bidi 0.6.11. One Hebrew payslip-style line was rendered by 4 PDF producers and then extracted. Results are in section C.4.

---

## B. Capability matrix

The matrix covers Hebrew mortgage documents. "IL residency" means verified in-Israel ML processing. Citation IDs refer to section A.

| Provider / tool (version as of 2026-10-12) | Hebrew printed | Hebrew handwriting | Word-level bbox | Confidence | Tables | PDF native (text layer / page images) | Data residency in Israel | Notes |
|---|---|---|---|---|---|---|---|---|
| **Gemini API** `gemini-3.8-flash` (ai.google.dev) | Hebrew is a supported language [V1]; OCR accuracy for Hebrew: NOT VERIFIED | NOT VERIFIED | No native word boxes. Prompted `box_2d` = [ymin,xmin,ymax,xmax], 0–1000, documented for **images** [G2]; on PDF input: NOT VERIFIED | None documented | Yes: "tables" [G1] | Yes: ≤50 MB / ≤1000 pages; Gemini 3 also ingests the embedded text [G1] | **No**: no region control; paid data "may be stored transiently or cached in any country" [G7] | Paid tier not used to improve products [G7]; `responseSchema` deprecated → `responseFormat` [G5]; JSON-Schema subset [G4]; PDF quality saturates at `medium` [G3] |
| **Gemini on Vertex** (Gemini Enterprise Agent Platform) `gemini-3.8-flash` | as above [V1] | NOT VERIFIED | as above | None documented | Yes | ≤50 MB and ≤3,000 pages per file [V2] | **No**: availability `global`/`us`/`eu`, ML processing `us`/`eu` [V2]; no Israel column [V5]; no Gemini model page lists `me-west1` [V3] | No training without permission [V6]; global endpoint has no residency guarantee [V4][V5]; 2.5 Pro retires 2026-10-20 [V3] |
| **Google Document AI** Enterprise Document OCR | **Yes** (`iw`, `Hebr`) [D1] | **No** ("Not Supported") [D1] | **Yes**: blocks/lines/words/symbols with `boundingPoly` [D2][D3] | **Yes**: [0,1] per token [D3] | Not in OCR. Form Parser and Layout Parser list Hebrew [D1] | **Yes**: native digital-PDF text, merged with OCR [D2] | **No**: `us`/`eu` + 7 non-IL single regions [D5] | 15 pages sync / 500 batch, 40 MB online [D4]; quality scores and rotation correction [D2]; Gemini-based Layout Parser versions use the **global** endpoint [D6]; Layout Parser boxes only on v1.0 [D7] |
| **Google Document AI** Bank Statement / Pay Slip parsers | **No** (English only) [D1] | No | (entity-level) | — | — | — | No | Not usable for Hebrew documents |
| **Azure Document Intelligence v4.0** Read / Layout | **Yes** (`he`) [A1] | **No** (not in v4.0 handwriting list) [A1] | **Yes**: word `polygon` [A2] | **Yes**: per word [A2] | **Yes** (Layout): cells, spans, `columnHeader`, rotated tables [A3] | **Yes**: ≤2,000 pages, ≤500 MB (S0); searchable-PDF output [A2] | **No**: not offered in Israel Central [A7][A8] (the region exists [A9]) | Units are inch (PDF) or pixel (image) [A10]; handwriting-style flag per line [A2]; multi-page tables need post-processing [A3] |
| **Azure prebuilt** `prebuilt-bankStatement.us`, `prebuilt-payStub.us` | **No** (en-US only) [A4][A5][A6] | No | Yes | Yes | Yes | Yes | No | US forms only. The invoice model supports `he` + ILS [A4] |
| **AWS Textract** | **No** [W1][W2] | No (English only) [W2] | Yes [W1] | Yes, 0–100 [W1] | Yes [W1] | Yes (async ≤3,000 pages) [W2] | **No** (no `il-central-1` endpoint) [W3] | Content may be used for service improvement unless opted out [W1] |
| **Tesseract 5.5.3** + `heb` (tessdata_best) [T10] | **Yes** [T1][T2][T3] | NOT VERIFIED (no Hebrew handwriting model listed) | **Yes**: TSV/hOCR word boxes [T9] | **Yes**: per-word `conf` [T9] | No | Image-only input; can emit a searchable PDF [T9] | **Yes if self-hosted** in an IL region (GCP `me-west1` [V7], Azure Israel Central [A9], AWS `il-central-1` [W4]) | ≥300 DPI advised [T4]; RTL/bidi caveats [T5][T6]; Hebrew punctuation (gershayim) gaps reported, issue still open [T8] |
| **PaddleOCR PP-OCRv5** (v3.7.0) | **No** (not among the 106 languages) [P1] | No | (n/a) | (n/a) | (n/a) | (n/a) | self-host | Not a candidate for Hebrew |
| **docTR v1.1.0** | Hebrew vocab exists [R1]; pretrained Hebrew recognizer: NOT VERIFIED | NOT VERIFIED | Yes: word `geometry` (relative) [R2] | Yes [R2] | Table predictor [R2] | Image-based | self-host | The `multilingual` vocab excludes Hebrew [R1] |
| **Surya 2** (v0.22.1) | **Yes**: 90.9% on the vendor's internal benchmark [S2] | NOT VERIFIED | **No** (block-level polygon/bbox; separate line detector) [S1] | Block-level [S1] | Yes [S1] | Accepts PDF/images [S1] | self-host | Weights license limits commercial use [S1] |
| **PyMuPDF 1.28.2** (text layer) | Depends on the PDF's text layer and ToUnicode | n/a | **Yes**: words and per-char bbox [M1] | n/a (deterministic); detect missing Unicode via U+FFFD [M2] | `find_tables()` [M4] | Yes (born-digital only) | local | Words never mix RTL/LTR [M4]; top-left origin [M3]; stream order unreliable for Hebrew (E1) |
| **pdfplumber 0.11.10** | Depends on the text layer | n/a | Yes [L1] | n/a | `extract_tables()` [L1] | Yes | local | `char_dir="rtl"` reverses digits (E1) |
| **Claude** Opus 5.5 / Sonnet 5.5 / Haiku 5.5 / Fable 5.1 | Generic "multilingual" [C3]; Hebrew-specific: NOT VERIFIED | NOT VERIFIED | **No**: citations are page ranges only [C2] | None | Yes (charts/tables) [C1] | Yes: page image + extracted text; ≤32 MB, ≤600 pages [C1] | **No** (`us`/`global`) [C4] | Citations cannot cite images and are incompatible with structured outputs [C2]; Fable 5.1 requires 30-day retention [C5] |
| **OpenAI** Responses API `input_file` | NOT VERIFIED | NOT VERIFIED | None documented | None documented | via vision | Yes: text + page images, ≤50 MB/request [O1] | **No** (no IL region) [O2] | Not used for training by default [O2] |

**How to read the matrix:**

- For **born-digital PDFs**, the text layer (PyMuPDF) provides exact characters and word boxes at zero model cost.
- For **scans and photos of printed Hebrew** with word boxes and confidence, the managed options are Azure Read/Layout and Document AI OCR. The self-hosted option is Tesseract `heb`. Surya 2 is a strong page-level reader but gives block-level boxes only.
- **Gemini, Claude and OpenAI are semantic readers and cross-checkers, not box producers.**

---

## C. Recommended layered reading strategy for Hebrew mortgage documents

### C.1 Pipeline

Text layer first, then OCR, then multimodal reading, then the judge. Each step carries its evidence (page + bbox).

**Layer 0: Intake and triage (per file, per page).** `ENGINEERING`, built on the cited APIs.

1. Open the file with PyMuPDF. Record `metadata` (Producer, Creator, creationDate, modDate), `version_count`, `get_sigflags()` and `is_repaired` [M6]. If the file is signed, run pyHanko (see section D) [H1][H2].
2. For each page, decide `has_text_layer` by testing for Hebrew code points (U+0590–U+05FF) in `get_text("words")` [M1].
3. **Detect missing ToUnicode / garbled fonts.** Re-extract with `TEXT_USE_CID_FOR_UNKNOWN_UNICODE` switched off and scan for U+FFFD [M2]. Any U+FFFD in a field region, or Latin-only output on a page that visibly holds Hebrew, routes the page to OCR (Layer 2).
4. **Detect visual-order (reversed) Hebrew.** Hebrew final forms (ך ם ן ף ץ) occur at word end in logical order. A high share of Hebrew tokens that *start* with a final form indicates reversed text. This is an `ENGINEERING` heuristic, not vendor-documented. It is motivated by E1, where pdfplumber's default output began words with final letters (e.g. "םולשת" instead of "תשלום").
5. Render each page once at a fixed DPI (e.g. 300) for OCR and multimodal reading. Keep `dpi`, `width_px`, `height_px` and the page rotation so coordinates can be converted (C.3).

**Layer 1: Text-layer extraction (born-digital PDFs).** Most precise; no OCR error.

- Use **word tokens with geometry**: `get_text("words")` returns `(x0, y0, x1, y1, word, block_no, line_no, word_no)` [M1]. Use `rawdict` when character boxes are needed [M1]. PyMuPDF words "never contain RTL/LTR char mixtures" [M4], so numbers come out as atomic LTR tokens next to Hebrew tokens. E1 confirms the numeric tokens `12,345.67`, `03/2026`, `09/04/2026` and `004512` were intact for all 4 producers.
- **Rebuild reading order from geometry, not from stream order.** `get_text("text")` follows creation order and "may not equal an accustomed natural reading order" [M1]. Group tokens into lines by vertical overlap or baseline, not by a rounded `y0`. In E1, rounding `y0` mis-grouped tokens for 3 of 4 producers because Hebrew and digit glyphs came from different fonts. Then order tokens right-to-left by `x1` for an RTL base direction, keeping each numeric token intact (`ENGINEERING`).
- Leave ligature handling at its defaults, but normalize Unicode before matching: PyMuPDF preserves ligatures [M2] and pdfplumber expands them [L1] (`ENGINEERING`).
- Rotated text: check `line["dir"]`; the bboxes remain axis-aligned rectangles [M5].
- Tables: PyMuPDF `find_tables()` [M4] or pdfplumber `extract_tables()` [L1]. Validate the result with arithmetic (row sums against stated totals).
- **Do not use pdfplumber with `char_dir="rtl"` on mixed Hebrew/number lines.** It reversed `12,345.67` into `76.543,21` in E1. Its default output is visual order (E1).

**Layer 2: OCR (scans, photos, and pages that fail Layer 0 checks).**

- **Managed, best documented for this need:**
  - Azure Read/Layout: Hebrew printed, word polygons and confidence, tables with headers and spans, rotated tables, ≤2,000 pages [A1][A2][A3].
  - Google Document AI Enterprise OCR: Hebrew printed, word/token boxes with `[0,1]` confidence, deskew, rotation correction, eight-dimension image-quality scores [D1][D2][D3].
  - Both process outside Israel only [A7][A8][D5]. Use them only if compliance permits.
- **In Israel (self-hosted):** Tesseract 5.5.3 with `heb` tessdata_best [T1][T3][T10]. It emits TSV word boxes and confidence and can produce searchable PDFs [T9]. Pre-rotate pages and deskew, and render at ≥300 DPI [T4]. Expect occasional digit or bidi defects, such as a dropped first digit when a line begins with a number [T5][T6]. Surya 2 can serve as a second reader (vendor-reported Hebrew 90.9% [S2]), but it gives block-level boxes only [S1] and has license limits [S1].
- **Not usable for Hebrew:** AWS Textract [W1][W2]; PaddleOCR PP-OCRv5 [P1].
- **Quality gates:**
  - Document AI image-quality score and defect list [D2].
  - Azure minimum text height of about 8-pt at 150 DPI (12 px on a 1024×768 image) [A2].
  - Route low-quality pages to re-capture or human review.
- **Handwriting:** Hebrew handwriting is unsupported by Document AI [D1], Azure [A1] and Textract [W2], so mark those fields `needs_human`.

**Layer 3: Multimodal reading and cross-check (semantic extraction).**

- **Model:** `gemini-3.8-flash` [G6][V2], or Claude or OpenAI as alternatives [C1][O1]. Ask for **structured output** with a JSON Schema: `response_format` with JSON Schema in the current docs; `responseSchema` is deprecated in `generateContent` [G4][G5]. Keep the schema shallow, because "very large or deeply nested schemas may be rejected" [G4]. Use `format: date` and `enum`s, then validate the values in code [G4].
- **Input choice:**
  - Gemini 3 [G1], Claude [C1] and OpenAI [O1] all feed the **embedded text plus page images** for PDFs.
  - If Layer 0 flagged the text layer as visual-order or garbled, send **rendered page images instead of the PDF**, so the model does not receive a corrupted text channel. How the models resolve a conflict between text and image is NOT VERIFIED.
  - Use `media_resolution: medium` for PDFs [G3]. Use `high` for dense small-print images; `high` is the recommended setting for images [G3].
- **Evidence:** require, per field, `{value, page, quote_he, box_2d}`. **Never accept an LLM box as evidence on its own.** Snap each value to Layer 1 or Layer 2 word boxes by normalized string match (digits stripped of separators, ₪ removed), and record which layer supplied the final bbox. Gemini's `box_2d` is image-relative 0–1000 [G2], so convert it with C.3. (`ENGINEERING`)
- Follow Gemini's best practice: "Rotate pages to the correct orientation before uploading" [G1].

**Layer 4: Verification and judge.**

- **Deterministic validators first** (`ENGINEERING`):
  - gross − deductions ≈ net on payslips;
  - opening balance + credits − debits = closing balance on bank statements;
  - date ranges, ID check digits, and consistency across documents.
- **LLM judge** (section E) with rubric-based binary verdicts [J9], position-swapped comparisons [J2], self-consistency [J4] and abstention or escalation [J6][J7].
- **Claude as an alternative judge on text-layer PDFs.** Citations return page ranges with `cited_text` "guaranteed to contain valid pointers" [C2]. They cannot cite images (useless for scans) and cannot be combined with structured outputs [C2], so run the citation pass separately from JSON extraction.

### C.2 Failure modes and mitigations

| # | Failure mode | Where it bites | Detection | Mitigation | Evidence |
|---|---|---|---|---|---|
| 1 | **RTL reversal** (text stored in visual order) | Text layer; producer-dependent | Final-letter heuristic (C.1, Layer 0); OCR vs text-layer disagreement | Word tokens + geometry. python-bidi on visual strings is a fallback only: it fixed 3 of 4 producers in E1 and failed on the fourth | E1; [M1] "may not equal … natural reading order" |
| 2 | **Digit order** (numbers reversed or truncated) | pdfplumber `char_dir="rtl"`; Tesseract RTL/bidi | Regex for numeric tokens; arithmetic cross-checks | Treat digit runs as atomic LTR tokens; never reverse them; test line-initial numbers | E1 (`76.543,21`); [T5]; [T6] "28 is recognized as 8" |
| 3 | **₪ symbol** (U+20AA) and **ש״ח** (gershayim) | OCR drops or splits the symbol; its bidi position varies (before or after the number) | Missing currency next to amount fields | Treat currency as optional context; infer ILS from the document type; normalize ״ (U+05F4) and " (U+0022) | E1 (₪ was a separate token in all producers); [T8] gershayim gap in `heb` training data (2017, open) |
| 4 | **Thousands and decimal separators** | Amounts like `12,345.67`; OCR confusing `,` and `.`; low DPI dropping dots | Parse with explicit rules, then check magnitude against totals | Store the raw string and the normalized decimal; confirm with arithmetic validators | `ENGINEERING`; E1 preserved `12,345.67` as one token. The separator convention on Israeli payslips is NOT VERIFIED (section F) |
| 5 | **Dates: DD/MM/YYYY vs MM/YYYY** (pay period) and US MM/DD confusion | Payslips (`03/2026` is a period), statements (`09/04/2026` is a day) | Day >12 → unambiguous; both ≤12 → ambiguous | Schema descriptions state DD/MM/YYYY and MM/YYYY explicitly; `format: date` output, validated in code | [G4] `format` + "always validate values"; E1 tokens `03/2026`, `09/04/2026` |
| 6 | **Rotated or skewed scans** | Photos; sideways pages | Azure page `angle` [A2]; Document AI deskew and rotation correction [D2]; PyMuPDF `dir` [M5] | Auto-rotate before OCR and LLM; record the rotation applied for bbox mapping | [G1] "Rotate pages…"; [D2]; [A3] rotated tables |
| 7 | **Low DPI / blur / glare** | Phone photos, faxes | Document AI quality score (blurry, text_too_small, glare…) [D2]; Azure minimum text height [A2] | Re-render at ≥300 DPI [T4]; request re-capture below threshold | [D2][A2][T4]; Gemini rescales pages to 768–3072 px [G1] |
| 8 | **Stamps and signatures over text** | Bank and employer stamps on payslips and approvals | OCR confidence dips; Document AI/Azure handwriting-style flags [D2][A2] | Keep the stamp region as visual evidence only; human review for occluded key fields | No vendor in scope documents stamp-text separation for Hebrew: NOT VERIFIED |
| 9 | **Handwriting** (Hebrew) | Handwritten amendments, signatures, notes | Azure `isHandwritten` style [A2]; Document AI font-style "handwriting" [D2] | Route to human; do not auto-accept | [D1] "Not Supported"; [A1]; [W2] |
| 10 | **Fonts without ToUnicode** (garbled text) | Born-digital PDFs from legacy generators | U+FFFD scan with the CID flag off [M2] | OCR the rendered page (Layer 2) | [M2] |
| 11 | **Missing spaces between Hebrew and numbers** | Text layer (LibreOffice, Chrome in E1: `לחודש03/2026`) | Tokens mixing Hebrew and digits after the join | Use word tokens (PyMuPDF splits RTL/LTR) [M4]; avoid plain `get_text("text")` for parsing | E1; [M4] |
| 12 | **Multi-page tables** | Bank statements | Header repeated on the next page | Merge in post-processing; re-check running balances | [A3]; [D6] |
| 13 | **Text-layer vs image conflict in LLM input** | Gemini 3, Claude and OpenAI all ingest both | Disagreement between LLM output and the text layer | Send images only when Layer 0 flags the text layer | [G1][C1][O1]; conflict resolution NOT VERIFIED |

### C.3 Coordinate conventions (for page + bbox evidence)

| Source | Origin / axes | Units | Box format | Evidence |
|---|---|---|---|---|
| PyMuPDF | top-left (0,0), y increases downward | PDF points (1/72 in) | `(x0, y0, x1, y1)` | [M1][M3] |
| Raw PDF space | bottom-left | points | — | [M3] |
| Gemini | image-relative | normalized 0–1000 | `box_2d = [ymin, xmin, ymax, xmax]` | [G2] |
| Azure DI | page | **inch** for PDF, **pixel** for images | `polygon` (word, cell) | [A10][A2] |
| Document AI | page image | pixels (`vertices`) or 0–1 (`normalizedVertices`) | `boundingPoly` | [D3] |
| docTR | page | relative 0–1 | `geometry ((xmin,ymin),(xmax,ymax))` | [R2] |
| Tesseract TSV | image | pixels | `left, top, width, height` | [T9] |
| Claude citations | — | page numbers (1-indexed, exclusive end) | no bbox | [C2] |

Recommended canonical evidence format (`ENGINEERING`): `page` (1-based), `bbox_pt = [x0, y0, x1, y1]` in PyMuPDF space (top-left origin, points), `source_layer ∈ {text_layer, ocr:<engine>, llm:<model>}`, `engine_conf`, `quote`.

Conversions, for a page rendered at `dpi` into an image of size `W×H` px:

- Gemini: `x_pt = (xmin/1000)·W·72/dpi`, `y_pt = (ymin/1000)·H·72/dpi` (and the same for max). This assumes an unrotated page whose CropBox equals its MediaBox; otherwise apply the page transform.
- Azure PDF: `pt = inch × 72`.
- Document AI normalized: `pt = v × page_size_pt`.

### C.4 Local test E1: how Hebrew text layers actually extract (`LOCAL TEST`)

**Logical ground truth:** `שכר ברוטו: 12,345.67 ₪ לחודש 03/2026, תאריך תשלום 09/04/2026, מספר עובד 004512`

**Producers:**

1. PyMuPDF `insert_htmlbox` (HarfBuzz shaping; empty Producer field);
2. Chrome headless, Producer `Skia/PDF m153`;
3. LibreOffice, Producer `LibreOffice 26.2.5.2 (AARCH64)`;
4. macOS print pipeline, Producer `macOS Version 26.5.1 (Build 25F80) Quartz PDFContext`.

| Producer | PyMuPDF `get_text("text")` | pdfplumber `extract_text()` | pdfplumber `extract_words(char_dir="rtl")`, first tokens | python-bidi `get_display(pdfplumber_text, base_dir='R')` |
|---|---|---|---|---|
| PyMuPDF Story | `שכר ברוטו: 12,345.67 ₪ לחודש 03/2026 , תאריך תשלום 09/04/2026 , מספר עובד 004512` (near-logical; extra spaces) | `דבוע רפסמ ,09/04/2026 םולשת ךיראת ,03/2026 שדוחל ₪ 12,345.67 :וטורב רכש 004512` (visual; letters reversed) | `שכר`, `ברוטו:`, **`76.543,21`**, `₪` | Not equal (`004512` moved to the front) |
| Chrome (Skia) | `004512 , מספר עובד09/04/2026 , תאריך תשלום03/2026 לחודש₪ 12,345.67 :שכר ברוטו` (run order reversed; spaces lost) | visual, letters reversed | same; digits reversed | **Exact match** |
| LibreOffice | `שכר ברוטו : 12,345.67 ₪ לחודש03/2026 , תאריך תשלום09/04/2026 , מספר עובד004512` (spaces lost) | visual, letters reversed | same; digits reversed | **Exact match** |
| macOS Quartz | `004512 עובד מספר ,09/04/2026 תשלום תאריך ,03/2026 לחודש ₪ 12,345.67 :ברוטו שכר` (word order fully visual) | visual, letters reversed | same; digits reversed | **Exact match** |

**Common results:**

- PyMuPDF `get_text("words")` gave **all 7 Hebrew words letter-correct** and all numeric tokens intact for all 4 producers.
- No U+FFFD appeared, because these test fonts carried Unicode mappings.

**Conclusion:**

- **Only word tokens plus geometry are stable across producers.** Line text, run order and spacing are not.
- Bidi post-processing helps but is not guaranteed.

**Limits:**

- One synthetic line from 4 producers. Real Israeli bank and payroll generators were not tested (section F).
- Reproduce on the real corpus before relying on this.

---

## D. Tamper and authenticity signal options, and their limits

| Signal | How to compute | What it tells you | Limits | Evidence |
|---|---|---|---|---|
| **Cryptographic PDF signature** (PAdES/CMS) | pyHanko `validate_pdf_signature(sig, ValidationContext(trust_roots=[…]))`; read `bottom_line` and `coverage` | Integrity since signing, plus signer identity, if the chain reaches a trusted root | Need explicit Israeli trust roots: falling back to the OS trust list is deprecated [H2]. Non-repudiation key usage is required by default [H1]. PAdES profile conformance is not validated [H1]. A signature proves origin and integrity, **not** truth of content | [H1][H2][H3][H4][H5] |
| **Land Registry (Tabu) online extract** | Expect a signed PDF and validate it as above | gov.il: the extract "includes an approved electronic signature" and is official **only in digital form** | Printed or scanned copies lose evidential status [IL1]. Signature format, issuing CA and LTV are NOT VERIFIED | [IL1] |
| **Incremental updates after signing** | pyHanko difference analysis (reject-by-default) or the cheaper `coverage` property | Whether content was appended after the signature | Diff analysis is "(very) experimental" [H1]; legitimate form-filling and extra signatures also append revisions [H1] | [H1][H3] |
| **Incremental-save count (unsigned PDFs)** | PyMuPDF `version_count` = incremental saves + 1 | The file was re-saved incrementally (an edit, annotation or e-sign) | **Weak**: common legitimate workflows also add revisions; a full rewrite resets the count | [M6] |
| **Signature-field flags** | PyMuPDF `get_sigflags()` (−1 / 1 / 3) | Presence of signature fields | Optional property; −1 means "no conclusions can be drawn" | [M6] |
| **Metadata: Producer, Creator, CreationDate, ModDate** | PyMuPDF `metadata` | A mismatch with the expected issuer pipeline (e.g. a bank statement whose Producer is a consumer PDF editor; ModDate ≫ CreationDate) | **Weak and trivially forged or stripped**. PyMuPDF even offers an option to omit the Producer [M4]. Use only to prioritise review | [M6][M4] |
| **Structural repair** | PyMuPDF `is_repaired` | A broken or hand-edited structure | Also triggered by buggy legitimate generators | [M6] |
| **Text-layer vs image disagreement** | Compare the Layer 1 text layer with Layer 2 OCR of the rendered page, per field bbox | An overlay or edited text layer (e.g. a number replaced in the text layer but not in the image, or the reverse) | False positives from OCR errors; needs a tolerance and human review | `ENGINEERING`, using [M1][A2][D3] |
| **Font and style anomalies in numeric fields** | PyMuPDF span fonts; `TEXT_COLLECT_STYLES` ("fake bold") [M2]; Document AI font-style detection [D2] | A digit in a different font, size or weight than its neighbours | Legitimate templates mix fonts; weak alone | [M2][D2] |
| **Cross-document consistency** | Payslip net ↔ bank deposits; employer name ↔ statement description; dates | Business-level fabrication | Requires several documents; our own rules | `ENGINEERING` |
| **Image forensics** (ELA, copy-move, recompression) | — | — | Not researched here: NOT VERIFIED | — |

**Bottom line.**

- Only a **validated cryptographic signature** (e.g. a digitally delivered Tabu extract [IL1]) is a strong authenticity signal.
- Everything else (metadata, revision counts, layer disagreements) is a **risk score that routes documents to human review**, never an automatic rejection.

---

## E. LLM-as-a-judge: references and how to apply them

| Practice for our judge | Why (reference) |
|---|---|
| **Rubric per field with binary verdicts.** For example: "value appears verbatim in the cited page region", "currency is ILS", "date parsed as DD/MM". Output only `correct`/`incorrect` plus a reason; use thinking when available. | [J9] "Have detailed, clear rubrics" / "output only 'correct' or 'incorrect'" / "Encourage reasoning"; [J3] CoT + form-filling |
| **Evidence-first judging.** The judge must quote the Hebrew text and page; the quote is then verified deterministically against the text layer or OCR. Claude citations guarantee valid pointers for text PDFs. | [C2]; [J2] "Multiple Evidence Calibration" |
| **Position-bias control** when comparing two candidate extractions (e.g. OCR-derived vs LLM-derived): evaluate both orders and aggregate. | [J1] position/verbosity/self-enhancement biases; [J2] "Balanced Position Calibration" |
| **Use a different model family as judge** than the extractor, to reduce self-preference. | [J1] self-enhancement bias; [J3] "bias towards the LLM-generated texts" |
| **Self-consistency.** Sample k judge runs (or k extractions), take the majority, and use agreement as a confidence feature. | [J4] |
| **Calibration and abstention.** Estimate judge confidence (e.g. P(True)-style self-evaluation or agreement rate), calibrate on a labelled Hebrew set, and escalate below threshold to a stronger model or a human. | [J5][J6] "selectively decide when to trust its judgement"; [J7] |
| **Scale only after measuring** agreement with human labels on our document types. | [J9] "Test to ensure reliability first then scale"; [J8] survey of reliability methods |

---

## F. NOT VERIFIED list (open items to test or confirm)

1. **Gemini Hebrew OCR accuracy.** No official Hebrew OCR benchmark was found for Gemini 3.x on scanned Hebrew payslips or statements. Hebrew is only listed as a supported language [V1].
2. **Gemini Hebrew handwriting.** No official statement found.
3. **Gemini `box_2d` on PDF inputs, and word-level precision.** The documentation covers images [G2]. Behaviour when a PDF is passed directly, and localization accuracy for small Hebrew words and digits, are untested. Mitigation: send rendered images.
4. **Gemini 3 conflict handling.** How it reconciles the embedded PDF text [G1] with the page image when the text layer is visual-order or garbled. The same applies to Claude [C1] and OpenAI [O1].
5. **Gemini token accounting.** [G1] says "Each document page is equivalent to 258 tokens", while [G3] lists Gemini 3 PDF defaults of 560 tokens (and 280/560/1120 + native text). The docs are inconsistent; check `usage_metadata` empirically.
6. **Vertex `me-west1` marks.** The locations page has a "Tel Aviv (me-west1)" column, but its per-model marks are rendered client-side and could not be read [V4]. No Gemini model page lists `me-west1` [V2][V3], so treat it as not available until confirmed in the console.
7. **Gemini API paid-tier log retention.** The terms say "for a limited period of time" without a number [G7].
8. **Document AI Layout Parser word-level geometry.** Only a release note says bounding boxes exist for v1.0 [D7]. Word-level Hebrew boxes from Layout Parser are not confirmed.
9. **Azure Document Intelligence accuracy figures for Hebrew,** and whether any other Azure SKU or resource type offers Read/Layout in Israel Central. Products-by-region and pricing both indicate no [A7][A8].
10. **Tesseract Hebrew accuracy.** No official per-language accuracy figure was found. Hebrew handwriting support is also unconfirmed. The RTL issue reports [T5][T6][T7] are community threads from 2018–2020; current behaviour in 5.5.3 is untested.
11. **docTR pretrained Hebrew recognizer.** Only a vocab is defined [R1].
12. **Surya on Israeli financial documents.** Only the vendor's internal benchmark exists [S2]. Word-level boxes are not provided in Surya 2 OCR output [S1].
13. **PyMuPDF/MuPDF bidi handling.** Official docs do not specify how RTL text is ordered in extraction (only the changelog note [M4]). E1 shows it is producer-dependent. Real Israeli bank and payroll PDF producers were not tested.
14. **Separator and date conventions** on specific Israeli payslip and bank formats (e.g. `12,345.67`, MM/YYYY pay periods). These are assumed from typical layouts, not taken from an official source.
15. **Tabu extract signature details.** Signature type (PAdES level), issuing CA and trust chain, LTV status, and whether pyHanko validates it out of the box. The gov.il text was read from a search-index snapshot because direct fetch was blocked [IL1].
16. **Other digitally signed Israeli documents.** Which other documents used in mortgage files (Tax Authority, National Insurance, bank-issued statements) are digitally signed was not researched.
17. **OpenAI PDF limits and capabilities.** No page cap is stated on the page fetched (only 50 MB) [O1]. Hebrew-specific quality and any box output are undocumented.
18. **Claude Hebrew-specific quality.** Also not researched: Claude's regional availability via Vertex or Bedrock for Israeli processing (only Anthropic first-party residency was checked) [C4].
19. **Stamp/occlusion handling and image-forensics tooling** (ELA, copy-move) for scanned documents: not researched.
20. **Regulatory data-residency requirements** for Israeli banks (whether in-country ML processing is mandatory): out of scope for R5. Confirm with compliance before choosing managed services.

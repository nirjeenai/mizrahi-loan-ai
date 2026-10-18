# Sales demo machine setup — Mizrahi Tefahot × JEEN loan demo

> **You are an autonomous AI coding agent setting up an existing project on a new sales laptop. Inspect the machine, install all missing requirements, preserve the transferred configuration and database, start the application, and verify all demo functionality. Never overwrite the existing .env file or reset the database. Use the existing project data. Request human intervention only for genuinely necessary credentials or administrator permissions.**

This guide travels inside the project folder (`mizrahi-touch-ai-demo/`). Every path below is relative to that folder
unless it starts with `/` or `~`. Commands marked **[verified]** were run against this project on the source computer
(macOS, Apple Silicon) on 2026-10-15. Commands marked **[standard]** are the usual OS installation commands; they were
not executed as part of this project's checks. No fresh installation on another computer has been tested yet.

---

## 0. Rules for the setup agent

1. `backend/.env` arrives with the project and holds the credentials. **Never create, overwrite, edit, reformat or
   print it.** Never print its values. Only check that it exists.
2. `backend/data/` holds the demo state: the SQLite database, uploaded documents and page renders. **Never delete,
   reset, replace or "clean" it.** Do not set `DATA_DIR`; the default (`backend/data/`) is the transferred data.
3. Do not run any of these on the sales laptop: `./run.sh reset`, `./run.sh test`, `POST /api/cases/{id}/reset`,
   `python fixtures/generate.py`, `rm -rf backend/data`, `npm audit fix`, or any E2E suite against port 8791.
4. Do not change the source code, `run.sh` or the rubrics to make something work. Report it instead.
5. `backend/.venv/` and `frontend/node_modules/` from the source computer are machine-specific (section 3). Recreating
   them is expected and safe. They contain no data.

---

## 1. What the application is

One process serves everything:

| Part | What it is | Entry point |
|---|---|---|
| Backend | FastAPI app (Python 3.12) with in-process job workers | `backend/app/main.py` (`app.main:app`), started by `./run.sh start` |
| Frontend | React 18 + Vite 5 single-page app, **pre-built** into `frontend/dist/` and served by the backend | `frontend/src/main.tsx` → `npm run build` → `frontend/dist/` |
| Database | SQLite (WAL mode), one file | `backend/data/mortgage_case_service.sqlite3` |
| MCP server | Mortgage Case MCP (Streamable HTTP) mounted at `/mcp` in the same process | `backend/app/mcp/server.py` |
| AI provider | Google Gemini over HTTPS (`generativelanguage.googleapis.com`) | `backend/app/llm/gemini.py` |

- **Port:** `127.0.0.1:8791` (change with `PORT=<n> ./run.sh start`). Only localhost; nothing listens on the network.
- **Startup order:** there is only one service. `./run.sh start` starts uvicorn; on startup the app opens the database,
  creates missing tables, applies small migrations (`backend/app/db.py::migrate`) and starts the job workers.
- **No separate frontend process** is needed for the demo. `./run.sh dev` (Vite on :5192 + backend reload) is for
  development only.
- **Docker:** not used. No Docker, Compose, database server, Redis or system service is required.
- **Pages:**
  - `http://127.0.0.1:8791/customer`: customer app (Hebrew, RTL, mobile layout; on a desktop the phone is centred with a
    presenter panel "תרחישי הדגמה" beside it)
  - `http://127.0.0.1:8791/customer/apply`: new application in the assistant chat, including the loan simulator card
  - `http://127.0.0.1:8791/banker`: banker console (case selector, V1 review, V2 intelligence, V3 prepared case)
  - `http://127.0.0.1:8791/system`: integration matrix and Gemini usage (opening it can probe VisionTrace over the
    network when `VISIONTRACE_MCP_KEY` is set)
- **Sign-in:** demo mode (`DEMO_IDENTITY=1`, the default) gives the browser a session automatically. There are no
  passwords.

### Data directory layout (`backend/data/`)

| Path | Needed at runtime | What it is |
|---|---|---|
| `mortgage_case_service.sqlite3` | **yes** | all case state: applications, onboarding drafts, chat turns, documents' metadata, review runs, findings, banker decisions, policy versions, audit |
| `mortgage_case_service.sqlite3-wal`, `-shm` | while the server runs | SQLite write-ahead log. While the server runs, recent writes may exist only in `-wal`. On a clean stop (Ctrl+C or SIGTERM) the app checkpoints the WAL into the database file, leaving an empty `-wal` and a `-shm` that may stay beside it. Never delete them by hand |
| `uploads/<case-id>/<DOC-id>.<pdf/png/jpg>` | **yes** | the uploaded document files. The database stores them as `uploads/<case>/<file>` relative to `backend/data/` |
| `renders/` | no (cache) | PNG page previews; regenerated on demand |
| `session_secret` | no | signs browser sessions; created automatically if missing |
| `backups/` | no | database backups made on the source computer (`2026-10-15-pre-portability/` is the backup taken before the storage-path migration) |
| `actions-e2e/` | no | old test data from development; not used by the app |

State at handoff (2026-10-15 15:05, after the final checkpoint on the source computer): 17 code-defined cases
(DEMO-MTZ-2026-001…011 and the six official profiles 101…106, defined in `backend/app/bank/mock_bank.py`) plus
3 customer-created applications (`DEMO-LN-0001-7D37`, `DEMO-LN-0002-2202`, `DEMO-LN-0003-468B`); 17 uploaded documents,
16 onboarding drafts, 39 chat turns, 41 findings, 37 review runs, 8 banker decisions, 3 policy versions. If the
app was used on the source computer after that, these numbers only grow.

### Configuration (`backend/.env`, read by `backend/app/config.py`)

Variables already set in the shell environment take precedence over `backend/.env`.

| Variable | Needed for |
|---|---|
| `GEMINI_API_KEY` | **live document reviews**, the assistant and the conversational questionnaire. Without it the app still starts; the questionnaire falls back to its deterministic path, and new uploads cannot be reviewed |
| `GEMINI_MODEL_EXTRACT`, `GEMINI_MODEL_JUDGE`, `GEMINI_MODEL_AGENT` | model ids (default `gemini-3.8-flash`) |
| `GEMINI_MAX_CALLS_PER_HOUR` | hourly cap on Gemini calls (default 400) |
| `REVIEW_PROVIDER` | `gemini` (the only working value) |
| `MCP_DEMO_KEY`, `MCP_DEMO_KEY_2` | case-bound keys for the MCP server and the `/system` MCP self-test |
| `VISIONTRACE_MCP_URL`, `VISIONTRACE_MCP_KEY` | optional; VisionTrace stays BLOCKED in this demo |
| optional: `SIMULATION_DATE` (default 2026-10-12), `SESSION_TTL_MINUTES`, `DEMO_IDENTITY`, `DEMO_RESET`, `ONBOARDING_LLM`, `ONBOARDING_LLM_TIMEOUT` | demo behaviour; leave unset |

`backend/.env.example` lists the same names with empty values. `./run.sh setup` creates `backend/.env` from it **only
when `backend/.env` does not exist**, so it never touches a transferred `.env`.

---

## 2. Requirements

| Requirement | Version | Notes |
|---|---|---|
| Python | **3.12** | verified with 3.12.13. 3.13/3.14 are untested; the pinned wheels may not exist for them. Use 3.12 |
| Node.js + npm | **Node 20 or newer** (Vite 5.4 requires `^18.0.0 \|\| >=20.0.0`) | verified with Node 26.5.0 / npm 11.17.0. Node 22 LTS is a sensible choice. Only needed to (re)build `frontend/dist/` |
| OS | macOS (Apple Silicon or Intel), or Windows 10/11 **through WSL2** (Ubuntu 24.04), or Linux | `run.sh` is a bash script and uses `backend/.venv/bin/python`; it does **not** run in native Windows PowerShell/cmd |
| OS libraries | none | PyMuPDF and Pillow ship self-contained wheels; no Tesseract/OCR, Poppler, ImageMagick or database server |
| Browser | Chrome, Edge or Safari | to show the demo. Playwright/Chrome are only used by the developer E2E suites |
| Internet | during setup (pip, npm) and during the demo for Gemini | the app itself serves no external assets (fonts are bundled) |
| Docker | not used | |

Python packages (`backend/requirements.txt`, exact pins): fastapi 0.143.0, uvicorn 0.54.0, pydantic 2.14.1,
python-multipart 0.0.32, httpx 0.28.1, pymupdf 1.28.2, pillow 12.3.0. `backend/requirements-dev.txt` adds pytest 9.1.1,
playwright 1.63.0 and mcp 2.3.0 (`./run.sh setup` installs the dev file; these three are used only by the tests and
E2E suites, not by the running app).
Transitive Python dependencies are not pinned.

npm packages (`frontend/package.json`, locked by `frontend/package-lock.json`): react 18.3.1, react-dom, react-router-dom
6.30.x, @fontsource/open-sans; dev: vite 5.4.x, @vitejs/plugin-react 4.x, typescript 5.9.x.

---

## 3. What cannot be reused from the source computer

| Folder | Why it is machine-specific | What to do |
|---|---|---|
| `backend/.venv/` | its `python` is a symlink to `/opt/homebrew/opt/python@3.12/bin/python3.12` on the source Mac; compiled packages are macOS arm64 (`*-darwin.so`); console scripts have shebangs pointing at a path on the source computer | `./run.sh setup` recreates it automatically when its Python does not run. On a different OS/CPU, delete it first (step 4.3) |
| `frontend/node_modules/` | contains native binaries for macOS arm64 only (`@esbuild/darwin-arm64`, `@rollup/rollup-darwin-arm64`) | on Windows/WSL, Linux or an Intel Mac: delete it before `npm install` (step 4.3). On another Apple Silicon Mac it usually works as is |
| Homebrew Python/Node of the source Mac | not part of the folder | install them on the laptop (step 4.2) |

`frontend/dist/` (the built app) **is** portable; it is rebuilt by `./run.sh setup` anyway.

---

## 4. Installation

### 4.1 Detect the machine

```bash
uname -s          # Darwin = macOS, Linux = Linux or WSL
uname -m          # arm64 / x86_64
grep -qi microsoft /proc/version 2>/dev/null && echo "running inside WSL"
command -v python3.12 && python3.12 --version
command -v node && node --version && npm --version
```

On Windows, open PowerShell and check `wsl --status`. If WSL is not installed, go to 4.2 (Windows).

### 4.2 Install missing prerequisites  [standard]

**macOS** (needs administrator rights for Homebrew; ask the user when prompted):

```bash
xcode-select --install                                   # if Homebrew asks for the Command Line Tools
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"   # if brew is missing
brew install python@3.12 node
python3.12 --version && node --version
```

Without Homebrew: install Python 3.12 from https://www.python.org/downloads/macos/ and Node.js LTS from
https://nodejs.org/.

**Windows 10/11 → WSL2** (PowerShell as Administrator; a reboot may be required):

```powershell
wsl --install -d Ubuntu-24.04
```

Then, inside the Ubuntu terminal:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip curl lsof
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
python3.12 --version && node --version
```

Put the project **inside the Linux file system**, not under `/mnt/c` (much faster, keeps permissions):

```bash
cp -r "/mnt/c/Users/<windows-user>/Desktop/<copied folder>/mizrahi-touch-ai-demo" ~/mizrahi-touch-ai-demo
cd ~/mizrahi-touch-ai-demo
```

**Linux (Ubuntu/Debian):** same `apt` commands as WSL.

### 4.3 Open the project and check the transferred files  [verified on the source computer]

```bash
cd <path>/mizrahi-touch-ai-demo
test -f backend/.env && echo ".env present" || echo ".env MISSING - ask the user"   # never print its contents
test -f backend/data/mortgage_case_service.sqlite3 && echo "database present"
ls backend/data/uploads | head
ls -la run.sh            # must be executable; if not: chmod +x run.sh  (or run it as: bash run.sh ...)
```

If a `.env` is missing, stop and ask the user for it. Do **not** let `./run.sh setup` generate one in its place unless
the user explicitly agrees, because a generated `.env` has no `GEMINI_API_KEY`.

If the laptop is **not** an Apple Silicon Mac, remove the source computer's environments (they hold no data):

```bash
rm -rf backend/.venv frontend/node_modules
```

### 4.4 Install dependencies and build  [verified on the source computer]

```bash
PYTHON=python3.12 ./run.sh setup
```

What `setup` does (`run.sh`):
1. creates `backend/.venv` with `$PYTHON` if `backend/.venv/bin/python` does not run (a copied venv is replaced with
   `--clear`); a working venv is kept;
2. `pip install -r backend/requirements-dev.txt`;
3. `cd frontend && npm install && npm run build` (typecheck + production build into `frontend/dist/`);
4. generates the synthetic fixture PDFs only if `fixtures/out/manifest.json` is missing (it is included, so this is skipped);
5. creates `backend/.env` only if it does not exist.

It does not touch `backend/data/`.

If Node cannot be installed, the pre-built `frontend/dist/` in the folder still works. Do the Python part by hand:

```bash
python3.12 -m venv --clear backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

### 4.5 Check the database before the first start  [verified]

Run this only while the server is stopped. It reads and changes nothing. When it closes, SQLite folds any leftover
`-wal` file into the database file and removes it (the supported procedure).

```bash
cd backend
.venv/bin/python - <<'EOF'
import sqlite3, hashlib
from pathlib import Path
c = sqlite3.connect("data/mortgage_case_service.sqlite3")
print("integrity:", c.execute("pragma integrity_check").fetchone()[0])
print("customer applications:", [r[0] for r in c.execute("select case_id from demo_applications order by created_at")])
print("documents:", c.execute("select count(*) from documents").fetchone()[0])
missing = [d for d, sp, sha in c.execute("select document_id, storage_path, sha256 from documents")
           if not sp.startswith("/") and not (Path("data", sp).is_file()
              and hashlib.sha256(Path("data", sp).read_bytes()).hexdigest() == sha)]
print("absolute paths (should be 0):", c.execute("select count(*) from documents where storage_path like '/%'").fetchone()[0])
print("files missing or changed (should be []):", missing)
c.close()
EOF
cd ..
```

Expected: `integrity: ok`, the three `DEMO-LN-…` applications, 17 or more documents, 0 absolute paths, `[]`.

### 4.6 Start  [verified]

```bash
./run.sh start
```

Leave this terminal open; the server runs in the foreground and logs requests. To run it in the background instead:

```bash
nohup ./run.sh start > /tmp/mizrahi-demo.log 2>&1 &
```

The database and uploads are found automatically (`backend/data/`). A database written by an older version with absolute
document paths is migrated on this first start (see "Incorrect file paths" in section 6).

### 4.7 Health checks  [verified]

```bash
curl -s http://127.0.0.1:8791/api/health
# {"ok":true,"provider":"gemini","simulation_date":"2026-10-12","data":"main"}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8791/customer    # 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8791/banker      # 200
```

Read-only API check of the transferred demo data (uses a demo staff session):

```bash
cd backend
.venv/bin/python - <<'EOF'
import httpx, sqlite3, hashlib
B = "http://127.0.0.1:8791"
s = httpx.Client(base_url=B, timeout=60); s.post("/api/session/demo/staff", json={})
c = sqlite3.connect("file:data/mortgage_case_service.sqlite3?mode=ro", uri=True)
docs = c.execute("select document_id, sha256 from documents").fetchall()
ok = sum(1 for d, sha in docs
         if (r := s.get(f"/api/documents/{d}/file")).status_code == 200 and hashlib.sha256(r.content).hexdigest() == sha
         and s.get(f"/api/documents/{d}/pages/1.png").status_code == 200)
print(f"documents open with original bytes and a page preview: {ok}/{len(docs)}")
cases = [x["case_id"] for x in s.get("/api/session/demo/cases").json()]
print("official profiles 101-106:", all(f"DEMO-MTZ-2026-10{i}" in cases for i in range(1, 7)))
print("customer applications:", [x for x in cases if x.startswith("DEMO-LN")])
for cid in [x for x in cases if x.startswith("DEMO-LN")] + ["DEMO-MTZ-2026-101"]:
    print(cid, "banker workspace", s.get(f"/api/banker/cases/{cid}/workspace").status_code)
EOF
cd ..
```

### 4.8 Open the demo in a browser

- Customer: `http://127.0.0.1:8791/customer`. A new application with the loan simulator: `http://127.0.0.1:8791/customer/apply`
- Banker: `http://127.0.0.1:8791/banker`

Manual acceptance (in this order):
1. `/banker`: the case selector lists the six official profiles and the customer applications (most recent first);
   other prepared cases are under "תרחישי בדיקה נוספים".
2. Open `DEMO-LN-0003-468B` and `DEMO-MTZ-2026-101`: the documents list, the original document preview and the extracted
   fields are shown; "פתיחת הקובץ המקורי" opens the PDF.
3. Switch V1 / V2 / V3: V3 shows the prepared case with the "מה יקרה אם?" controls open.
4. `/customer/apply`: answer the purpose question; the loan simulator card appears, and moving the amount/term updates
   the monthly payment.
5. With a working `GEMINI_API_KEY` and internet: uploading a document in the customer app produces a review within about
   a minute. **This spends real Gemini calls and adds the document to the demo data**; do it only if the user wants it.

The text is Hebrew and right-to-left; check that the page is not mirrored the wrong way and Hebrew renders correctly.

### 4.9 Stop

- Foreground: press `Ctrl+C` in the server's terminal.
- Background or another terminal: `kill $(lsof -tiTCP:8791 -sTCP:LISTEN)` (sends SIGTERM; uvicorn shuts down cleanly).

### 4.10 Future demo days

```bash
cd <path>/mizrahi-touch-ai-demo
./run.sh start
# open http://127.0.0.1:8791/customer and http://127.0.0.1:8791/banker
```

Nothing needs reinstalling. Demo data created during a demo is kept in `backend/data/`.

Presenter panel warning: "התחל דמו חדש" in the customer app's presenter panel **wipes cases 006–011 and the six official
profiles 101–106** (their uploads, reviews and decisions) so the scenarios can be replayed. Customer-created
applications (`DEMO-LN-…`) and cases 001–005 are not touched. Use it only when the presenter wants a clean run.

### 4.11 Copying the project again later

Stop the server first (4.9), then copy the whole folder. After a clean stop the app has checkpointed the WAL, so the
database file holds every write (an empty `-wal` and a `-shm` may remain; copying them along is harmless). Copying while
the server runs can produce an inconsistent database. If the server was killed (not stopped cleanly), copy
`mortgage_case_service.sqlite3` together with its `-wal` and `-shm` files, never the database file alone. Then run
the check in 4.5 on the copy.

---

## 5. Commands reference

| Command | Effect | Safe on the sales laptop |
|---|---|---|
| `PYTHON=python3.12 ./run.sh setup` | venv, pip, npm install + build, `.env` only if missing | yes |
| `./run.sh start` | serve on :8791 | yes |
| `PORT=8792 ./run.sh start` | serve on another port | yes |
| `./run.sh dev` | Vite :5192 + backend reload (development) | yes, but not needed |
| `cd backend && .venv/bin/python -m pytest -q tests` | backend tests on a temporary data dir, Gemini off (≈5 s) | yes |
| `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` | frontend typecheck | yes |
| `./run.sh reset` | wipes cases 001 and 003 | **no** |
| `./run.sh test` | tests + browser E2E with ~37 real Gemini calls | **no** (costs money) |

---

## 6. Troubleshooting

**Missing Python / wrong Python version.** `python3.12 --version` must print 3.12.x. Install it (4.2) and run
`PYTHON=python3.12 ./run.sh setup`. If `backend/.venv` was created with another version, run
`python3.12 -m venv --clear backend/.venv` and then `./run.sh setup`. `run.sh start` always uses
`backend/.venv/bin/python -m uvicorn`; console scripts such as `.venv/bin/uvicorn` copied from the source computer do
not work.

**Missing Node.js / npm.** Install Node 20+ (4.2). `node --version` must be ≥ 20. Without Node the pre-built
`frontend/dist/` still works (4.4, Python-only path), but the UI cannot be rebuilt.

**`npm run build` fails with "Cannot find module @rollup/rollup-…" or an esbuild platform error.** `node_modules` came
from the source Mac. Run `rm -rf frontend/node_modules && (cd frontend && npm install && npm run build)`. Keep
`package-lock.json`.

**pip install fails.** Most often the Python version (no wheel for pymupdf/pydantic-core on 3.13+): use 3.12. Behind a
proxy, set `HTTPS_PROXY`. On WSL install `python3.12-venv` before creating the venv. Do not upgrade the pinned versions.

**Windows / WSL2.** Run everything inside the Ubuntu terminal, with the project under `~` (not `/mnt/c`). If
`./run.sh` says "Permission denied", use `chmod +x run.sh` or `bash run.sh start`. Open the demo in the Windows browser
at `http://127.0.0.1:8791` (WSL2 forwards localhost by default). If it does not load, check `curl` inside WSL first,
then run `wsl --shutdown` in PowerShell and start again.

**Port 8791 already in use.** `lsof -nP -iTCP:8791 -sTCP:LISTEN` shows the process. If it is an older instance of this
app, stop it (4.9). Otherwise start on another port: `PORT=8792 ./run.sh start` and use that port in the URLs.

**Database errors** (`database is locked`, `malformed`). Make sure only one server uses `backend/data/` (check with
`lsof backend/data/mortgage_case_service.sqlite3`). Run the read-only check in 4.5. If `integrity_check` is not `ok`,
stop and ask the user. A verified backup is in `backend/data/backups/2026-10-15-pre-portability/` (made on the source
computer before the path migration). Restoring it loses later demo activity, so never restore without the user's OK.
Never delete `-wal`/`-shm` files by hand.

**Missing documents / a document shows "not available".** The file API returns 404 when the document's file is not in
`backend/data/uploads/<case>/`. Run the check in 4.5: it lists missing or changed files. The cause is almost always an
incomplete copy of `backend/data/uploads/`; copy it again from the source.

**Incorrect file paths.** The database stores document paths relative to `backend/data/` (`uploads/<case>/<file>`).
A database from an older version with absolute paths (for example `/Users/<someone>/…/backend/data/uploads/…`) is
handled automatically: such paths are resolved by their `uploads/<case>/<file>` tail, and the first start rewrites them
to the relative form when the file's SHA-256 matches (`backend/app/store/files.py`, `db.migrate`). The server log then
says `made N document storage paths relative to DATA_DIR`. Paths are never resolved outside `backend/data/uploads/`.

**Backend/frontend connectivity.** In the normal setup there is one process; if `/customer` loads but data does not,
check `curl -s http://127.0.0.1:8791/api/health`. A blank page usually means `frontend/dist/` is missing: run
`(cd frontend && npm run build)`. With `./run.sh dev`, Vite (:5192) proxies `/api` to `MZ_API` (default
`http://127.0.0.1:8791`). The browser must use the same host name it got the page from (127.0.0.1 vs localhost) or the
session cookie is not sent.

**Gemini connectivity.** Symptoms: an uploaded document goes to "ניסיון חוזר" and then "הבדיקה נכשלה", or the
assistant replies with its built-in fallback text (logged as `agent fallback` in the server output). Check that the laptop has internet access to `generativelanguage.googleapis.com` (corporate firewalls often
block it), that `GEMINI_API_KEY` is set in `backend/.env` (ask the user; do not print the file), and that no empty
`GEMINI_API_KEY` is exported in the shell (the environment wins over `.env`). The Gemini call log and errors are on
`/system` and in `GET /api/system/llm` (staff session). The hourly cap is `GEMINI_MAX_CALLS_PER_HOUR`.

**Document-processing errors.** Only PDF, PNG and JPEG up to 15 MB are accepted. A failed review can be retried from
the UI (it calls `POST /api/documents/{id}/retry`). Reviews need Gemini; previews and the original file do not.
`SIMULATION_DATE` is fixed at 2026-10-12, so the expected payslip months are 2026-07, 08 and 09; do not change it.

**Hebrew looks wrong.** The fonts are bundled in `frontend/dist/assets/`; a hard refresh (Cmd/Ctrl+Shift+R) loads the
current build. No system fonts or internet fonts are needed.

"""The Mortgage Case Service workflow — durable jobs, review runs, findings lifecycle.

upload → review_document (provider: extract · verify · checks · judge) → review_case
(provider: coverage · semantic · case rubric) → reconcile findings → readiness.

Jobs live in SQLite with idempotency keys, bounded retries with backoff and startup
recovery. Document jobs run concurrently; a case review is single-flight and waits
until the case's documents are done, so it always sees the newest evidence."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .. import db
from ..bank.mock_bank import bank
from ..config import settings
from ..review import registry, rubrics
from ..review import evidence as ev
from ..review.contract import CaseReviewRequest, DesiredFinding, DocumentReviewRequest
from ..store import repo
from ..util import new_id, now_iso, sha256_bytes, stable_hash
from . import desk_state, readiness

log = logging.getLogger("workflow")
ALLOWED_MIMES = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg"}
MAX_BYTES = 15 * 1024 * 1024
MAX_ATTEMPTS = 3
WORKERS = 3


class UploadRejected(ValueError):
    pass


# ---------------------------------------------------------------- submission
def submit_document(case_id: str, filename: str, mime: str, data: bytes, borrower_id: Optional[str],
                    requirement_code: Optional[str], actor: str, channel: str) -> tuple[dict, bool]:
    case = bank.get_case(case_id)
    if borrower_id and borrower_id not in {b["borrower_id"] for b in case["borrowers"]}:
        raise UploadRejected("borrower does not belong to this case")
    if mime not in ALLOWED_MIMES:
        raise UploadRejected(f"unsupported file type {mime}; upload a PDF, PNG or JPEG")
    if not data or len(data) > MAX_BYTES:
        raise UploadRejected("file is empty or larger than 15 MB")
    if mime == "application/pdf" and not data.startswith(b"%PDF"):
        raise UploadRejected("the file is not a valid PDF")
    sha = sha256_bytes(data)
    existing = repo.document_by_sha(case_id, sha)
    if existing:
        repo.audit(case_id, actor, "document_upload_duplicate_file", existing["document_id"],
                   {"filename": filename, "sha256": sha})
        return existing, False
    document_id = new_id("DOC")
    folder = settings.uploads_dir / case_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{document_id}.{ALLOWED_MIMES[mime]}"
    path.write_bytes(data)
    try:
        info = ev.inspect(str(path), mime)
    except Exception as exc:                          # corrupt / protected file
        path.unlink(missing_ok=True)
        raise UploadRejected(f"the file could not be opened ({type(exc).__name__})") from None
    requirement_code = requirement_code or (f"PAYSLIPS:{borrower_id}" if borrower_id else None)
    row = {"document_id": document_id, "case_id": case_id, "borrower_id": borrower_id, "requirement_code": requirement_code,
           "filename": Path(filename).name[:120], "mime": mime, "sha256": sha, "bytes": len(data), "pages": info["pages"],
           "text_layer_chars": info["text_layer_chars"], "storage_path": str(path), "uploaded_at": now_iso(),
           "uploaded_by": actor, "channel": channel, "status": "queued", "stage": "queued"}
    repo.insert_document(row)
    repo.audit(case_id, actor, "document_uploaded", document_id,
               {"filename": row["filename"], "borrower_id": borrower_id, "sha256": sha, "pages": info["pages"],
                "text_layer": info["text_layer_chars"] > 0})
    enqueue("review_document", case_id, document_id, f"review_document:{document_id}:1")
    return repo.document(document_id), True


def retry_document(document_id: str, actor: str) -> None:
    doc = repo.document(document_id)
    if not doc:
        raise KeyError(document_id)
    repo.set_document(document_id, status="queued", stage="queued", error=None)
    repo.audit(doc["case_id"], actor, "document_review_requested", document_id, {"reason": "manual re-review"})
    enqueue("review_document", doc["case_id"], document_id, f"review_document:{document_id}:{new_id('R')}")


# ---------------------------------------------------------------- jobs
def enqueue(kind: str, case_id: str, document_id: Optional[str], idempotency_key: str, payload: Any = None) -> bool:
    now = now_iso()
    with db.tx() as c:
        cur = c.execute("INSERT OR IGNORE INTO jobs(job_id, kind, case_id, document_id, idempotency_key, status, attempts,"
                        " not_before, created_at, updated_at, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (new_id("JOB"), kind, case_id, document_id, idempotency_key, "queued", 0, now, now, now,
                         db.jdump(payload) if payload else None))
        return cur.rowcount == 1


def request_case_review(case_id: str, reason: str, actor: str = "workflow") -> bool:
    if db.one("SELECT 1 FROM jobs WHERE case_id=? AND kind='review_case' AND status='queued'", (case_id,)):
        return False                                     # one pending case review already covers the newest state
    created = enqueue("review_case", case_id, None, f"review_case:{case_id}:{new_id('C')}", {"reason": reason})
    if created:
        repo.audit(case_id, actor, "case_review_requested", case_id, {"reason": reason})
    return created


def pending_jobs(case_id: str) -> list[dict]:
    return db.query("SELECT kind, document_id, status, attempts FROM jobs WHERE case_id=? AND status IN ('queued','running')",
                    (case_id,))


def _claim() -> Optional[dict]:
    now = now_iso()
    with db.tx() as c:
        row = c.execute("SELECT * FROM jobs WHERE status='queued' AND kind='review_document' AND not_before<=? "
                        "ORDER BY created_at LIMIT 1", (now,)).fetchone()
        if row is None:
            row = c.execute("SELECT j.* FROM jobs j WHERE j.status='queued' AND j.kind='review_case' AND j.not_before<=? "
                            "AND NOT EXISTS (SELECT 1 FROM jobs d WHERE d.case_id=j.case_id AND d.kind='review_document' "
                            "AND d.status IN ('queued','running')) "
                            "AND NOT EXISTS (SELECT 1 FROM jobs r WHERE r.case_id=j.case_id AND r.kind='review_case' "
                            "AND r.status='running') ORDER BY j.created_at LIMIT 1", (now,)).fetchone()
        if row is None:
            return None
        c.execute("UPDATE jobs SET status='running', attempts=attempts+1, updated_at=? WHERE job_id=?", (now, row["job_id"]))
        job = dict(row)
        job["attempts"] += 1
        return job


def _finish(job: dict, ok: bool, error: str = "") -> None:
    now = now_iso()
    with db.tx() as c:
        if ok:
            c.execute("UPDATE jobs SET status='succeeded', updated_at=?, error=NULL WHERE job_id=?", (now, job["job_id"]))
        elif job["attempts"] < MAX_ATTEMPTS:
            delay = 4 * 2 ** (job["attempts"] - 1)
            retry_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(timespec="seconds")
            c.execute("UPDATE jobs SET status='queued', not_before=?, updated_at=?, error=? WHERE job_id=?",
                      (retry_at, now, error[:500], job["job_id"]))
        else:
            c.execute("UPDATE jobs SET status='failed', updated_at=?, error=? WHERE job_id=?", (now, error[:500], job["job_id"]))


def recover() -> None:
    with db.tx() as c:
        c.execute("UPDATE jobs SET status='queued', updated_at=? WHERE status='running'", (now_iso(),))
        c.execute("UPDATE documents SET status='queued' WHERE status='processing'")


# ---------------------------------------------------------------- execution
def _run_document(job: dict) -> None:
    doc = repo.document(job["document_id"])
    if not doc:
        return
    provider = registry.active()
    ident = provider.identity()
    rubric = rubrics.for_document(doc["requirement_code"])
    run_id = new_id("RUN")
    repo.start_run({"run_id": run_id, "case_id": doc["case_id"], "document_id": doc["document_id"], "scope": "document",
                    "provider": ident.provider, "models": db.jdump(ident.models), "rubric_id": rubric["rubric_id"],
                    "rubric_version": rubric["version"], "prompt_version": ident.prompt_version, "status": "running",
                    "stage": "intake", "started_at": now_iso(), "input_hash": doc["sha256"],
                    "trigger": f"job {job['job_id']} attempt {job['attempts']}"})
    repo.set_document(doc["document_id"], status="processing", stage="intake", current_run_id=run_id, error=None)

    def progress(stage: str) -> None:
        repo.update_run(run_id, stage=stage)
        repo.set_document(doc["document_id"], stage=stage)

    req = DocumentReviewRequest(case_id=doc["case_id"], document_id=doc["document_id"], filename=doc["filename"],
                                mime=doc["mime"], storage_path=doc["storage_path"], assigned_borrower_id=doc["borrower_id"],
                                requirement_code=doc["requirement_code"], case_context=bank.case_context(doc["case_id"]),
                                rubric=rubric, run_id=run_id)
    try:
        handle = provider.start_document_review(req, progress)
        deadline = time.monotonic() + 600
        while (status := provider.get_status(handle)).state in ("queued", "running"):
            if time.monotonic() > deadline:
                raise TimeoutError("review provider did not finish in time")
            time.sleep(2)
        if status.state != "succeeded":
            raise RuntimeError(status.detail or "review failed")
        result = provider.get_document_result(handle)
    except Exception as exc:
        if not repo.document(doc["document_id"]):
            log.info("document %s was removed (case reset) while under review; nothing recorded", doc["document_id"])
            return
        repo.update_run(run_id, status="failed", stage="failed", finished_at=now_iso(), error=f"{type(exc).__name__}: {exc}"[:500])
        final = job["attempts"] >= MAX_ATTEMPTS
        repo.set_document(doc["document_id"], status="failed" if final else "queued", stage="failed" if final else "retrying",
                          error=f"{type(exc).__name__}: {exc}"[:300])
        repo.audit(doc["case_id"], "workflow", "document_review_failed", doc["document_id"],
                   {"run_id": run_id, "error": str(exc)[:300], "attempt": job["attempts"], "final": final})
        if final:
            request_case_review(doc["case_id"], f"document {doc['document_id']} failed review")
        raise
    if not repo.document(doc["document_id"]):
        # the case was reset while the provider worked: writing now would leave a ghost review in an empty case
        log.info("document %s was removed (case reset) while under review; result discarded", doc["document_id"])
        return
    repo.update_run(run_id, status="succeeded", stage="done", finished_at=now_iso(), result=db.jdump(result.model_dump()))
    repo.set_document(doc["document_id"], status="reviewed", stage="done", error=None)
    repo.audit(doc["case_id"], f"provider:{ident.provider}", "document_reviewed", doc["document_id"],
               {"run_id": run_id, "verdict": result.verdict, "reasons": result.verdict_reason_codes,
                "rubric": f"{rubric['rubric_id']}@{rubric['version']}", "doc_type": result.doc_type,
                "period": result.period, "usage": result.usage})
    request_case_review(doc["case_id"], f"document {doc['document_id']} reviewed")


def _run_case(job: dict) -> None:
    case_id = job["case_id"]
    provider = registry.active()
    ident = provider.identity()
    rubric = rubrics.for_case()
    docs = []
    # a payslip the customer replaced (at the banker's request or after the AI sent it back) no longer counts toward the set
    replaced = set(desk_state.replacements(repo.customer_requests(case_id), case_id))
    for d in repo.documents(case_id):
        if d["document_id"] in replaced:
            continue
        docs.append({**{k: d[k] for k in ("document_id", "filename", "borrower_id", "status", "uploaded_at", "requirement_code")},
                     "review": repo.latest_document_result(d["document_id"]) if d["status"] == "reviewed" else None})
    open_by_id = {f["finding_id"]: f for f in repo.findings(case_id)}
    stmts = [{**s, "borrower_id": (open_by_id.get(s["finding_id"]) or {}).get("borrower_id")} for s in repo.statements(case_id)]
    input_hash = stable_hash(db.jdump([[d["document_id"], (d["review"] or {}).get("run_id")] for d in docs] +
                                      [s["statement_id"] for s in stmts]))
    run_id = new_id("CRUN")
    repo.start_run({"run_id": run_id, "case_id": case_id, "document_id": None, "scope": "case", "provider": ident.provider,
                    "models": db.jdump(ident.models), "rubric_id": rubric["rubric_id"], "rubric_version": rubric["version"],
                    "prompt_version": ident.prompt_version, "status": "running", "stage": "case_coverage",
                    "started_at": now_iso(), "input_hash": input_hash, "trigger": (db.jload(job.get("payload")) or {}).get("reason")})
    req = CaseReviewRequest(case_id=case_id, run_id=run_id, case_context=bank.case_context(case_id), documents=docs,
                            statements=stmts, rubric=rubric)
    try:
        result = provider.review_case(req, lambda stage: repo.update_run(run_id, stage=stage))
    except Exception as exc:
        if not repo.run(run_id):
            return                                       # the case was reset meanwhile; nothing to record
        repo.update_run(run_id, status="failed", stage="failed", finished_at=now_iso(), error=f"{type(exc).__name__}: {exc}"[:500])
        repo.audit(case_id, "workflow", "case_review_failed", case_id, {"run_id": run_id, "error": str(exc)[:300]})
        raise
    if not repo.run(run_id):
        log.info("case %s was reset during its review (run %s); findings not written", case_id, run_id)
        return
    repo.update_run(run_id, status="succeeded", stage="done", finished_at=now_iso(), result=db.jdump(result.model_dump()))
    changes = reconcile_findings(case_id, result.findings, run_id)
    state = readiness.compute(case_id, ignore_job_id=job["job_id"])
    repo.save_case_state(case_id, state, run_id)
    repo.audit(case_id, f"provider:{ident.provider}", "case_reviewed", case_id,
               {"run_id": run_id, "rubric": f"{rubric['rubric_id']}@{rubric['version']}", "findings": changes,
                "readiness": state["state"]})


COVERAGE_CODES = ("REQUIRED_PERIOD_MISSING", "DUPLICATE_PERIOD")
BANKER_RULINGS = ("accepted_by_banker", "resolved_by_banker", "dismissed_by_banker", "correction_requested_by_banker")


def reconcile_findings(case_id: str, desired: list[DesiredFinding], run_id: str) -> dict:
    """Open what is new, update what changed, resolve customer findings the evidence no longer
    supports — and never close a banker-review finding on the AI's own authority.

    A banker ruling on a finding holds until its evidence changes: a document's file never changes,
    and a case-level finding re-opens only when its computed message (the figures) differs. Coverage
    facts (a missing or duplicate month) are never suppressed. A document the banker sent back for
    correction is superseded once the customer's replacement has been reviewed."""
    now = now_iso()
    current = repo.findings(case_id)
    open_by_key = {f["key"]: f for f in current if f["status"] == "open"}
    ruled = {f["key"]: f for f in current if f["status"] != "open" and f.get("resolution") in BANKER_RULINGS}
    links = {old: r for old, r in desk_state.replacements(repo.customer_requests(case_id), case_id).items()
             if (repo.document(r["responded_document_id"]) or {}).get("status") == "reviewed"}
    replaced = {old: r["responded_document_id"] for old, r in links.items()}
    wanted = {d.key: d for d in desired if d.document_id not in replaced}
    stats = {"opened": 0, "updated": 0, "resolved": 0, "kept_for_banker": 0, "superseded": 0}
    for key, f in list(open_by_key.items()):
        if f["document_id"] in replaced:
            by_customer = links[f["document_id"]]["kind"] == "customer_replacement"
            if by_customer and f["review_state"] == "NEEDS_BANKER_REVIEW":
                continue                                 # the customer's own replacement never closes a banker finding
            history = f["history"] + [{"at": now, "run_id": run_id, "event": "superseded_by_replacement",
                                       "note": f"הלקוח העלה מסמך חלופי ({replaced[f['document_id']]}) "
                                               + ("אחרי שבדיקת ה-AI החזירה את המסמך" if by_customer else "לבקשת הבנקאי")}]
            repo.upsert_finding({**f, "status": "superseded", "resolution": "replaced_by_customer_upload",
                                 "superseded_by": replaced[f["document_id"]], "resolved_run_id": run_id, "resolved_at": now,
                                 "updated_at": now, "history": history})
            del open_by_key[key]
            stats["superseded"] += 1
    for key, d in wanted.items():
        payload = {"code": d.code, "severity": d.severity, "review_state": d.review_state, "borrower_id": d.borrower_id,
                   "document_id": d.document_id, "period": d.period, "title_he": d.title_he, "message_he": d.message_he,
                   "detail": d.detail, "evidence": [e.model_dump() for e in d.evidence]}
        if key in open_by_key:
            f = open_by_key[key]
            changed = [k for k in ("review_state", "message_he", "severity") if f[k] != payload[k]]
            if changed:
                history = f["history"] + [{"at": now, "run_id": run_id, "event": "updated",
                                           "changes": {k: [f[k], payload[k]] for k in changed}}]
                repo.upsert_finding({**f, **payload, "updated_at": now, "history": history})
                stats["updated"] += 1
            elif f["evidence"] != payload["evidence"] or f["detail"] != payload["detail"]:
                repo.upsert_finding({**f, **payload, "updated_at": now})
            continue
        prior = ruled.get(key)
        if prior and d.code not in COVERAGE_CODES and (prior["document_id"] or prior["message_he"] == d.message_he):
            continue
        opened = {"at": now, "run_id": run_id, "event": "opened"}
        if prior and d.code not in COVERAGE_CODES:
            opened.update({"after_banker_ruling": prior["finding_id"], "prior_resolution": prior.get("resolution"),
                           "note": "נפתח מחדש כי הנתונים השתנו מאז ההכרעה הקודמת של הבנקאי"})
        repo.upsert_finding({"finding_id": new_id("F"), "case_id": case_id, "key": key, "status": "open", **payload,
                             "created_run_id": run_id, "created_at": now, "updated_at": now, "resolved_run_id": None,
                             "resolved_at": None, "resolution": None, "resolution_note": None, "superseded_by": None,
                             "history": [opened]})
        stats["opened"] += 1
    for key, f in open_by_key.items():
        if key in wanted:
            continue
        if f["review_state"] == "NEEDS_BANKER_REVIEW":
            if not f["detail"].get("not_reproduced_by"):
                history = f["history"] + [{"at": now, "run_id": run_id, "event": "not_reproduced",
                                           "note": "הבדיקה האחרונה אינה משחזרת ממצא זה — נדרש אישור בנקאי לסגירה"}]
                repo.upsert_finding({**f, "detail": {**f["detail"], "not_reproduced_by": run_id}, "updated_at": now,
                                     "history": history})
            stats["kept_for_banker"] += 1
            continue
        history = f["history"] + [{"at": now, "run_id": run_id, "event": "resolved_by_new_evidence"}]
        repo.upsert_finding({**f, "status": "resolved", "resolution": "resolved_by_new_evidence", "resolved_run_id": run_id,
                             "resolved_at": now, "updated_at": now, "history": history})
        stats["resolved"] += 1
    return stats


# ---------------------------------------------------------------- worker threads
_stop = threading.Event()
_threads: list[threading.Thread] = []


def _loop(n: int) -> None:
    while not _stop.is_set():
        job = None
        try:
            job = _claim()
            if job is None:
                _stop.wait(0.6)
                continue
            if job["kind"] == "review_document":
                _run_document(job)
            elif job["kind"] == "review_case":
                _run_case(job)
            _finish(job, True)
        except Exception as exc:                          # recorded on the run/job; the loop keeps serving
            log.exception("job failed")
            if job:
                _finish(job, False, f"{type(exc).__name__}: {exc}")


def start_workers() -> None:
    recover()
    if _threads:
        return
    _stop.clear()
    for i in range(WORKERS):
        t = threading.Thread(target=_loop, args=(i,), name=f"review-worker-{i}", daemon=True)
        t.start()
        _threads.append(t)


def stop_workers() -> None:
    _stop.set()

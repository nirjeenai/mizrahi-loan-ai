"""Building a personal-loan case without Gemini: stored review results shaped like the provider's, per document family."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from app.review import rubrics
from app.store import repo
from app.util import new_id, now_iso
from app.workflow import engine

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "out" / "main"
IDO = ("עידו לוי", "DEMO-ID-001")
JOURNEY = "DEMO-MTZ-2026-009"
CODES = {"id": "ID_CARD:BRW-A", "pay": "PAYSLIPS:BRW-A", "bank": "BANK_STATEMENTS:ACC-1", "purpose": "PURPOSE_PROOF"}
FAMILY = {"id": "id_document", "pay": "payslip", "bank": "bank_statement", "purpose": "purpose_proof"}
DOC_TYPE_HE = {"id_document": "תעודת זהות", "bank_statement": "דף חשבון בנק", "purpose_proof": "אסמכתה למטרה", "payslip": "תלוש שכר"}


def client_for(*cases: str) -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIES["customer"], auth.issue("customer", list(cases)))
    c.cookies.set(auth.COOKIES["staff"], auth.issue("staff", "STAFF-DANA"))
    return c


def _fact(doc_id: str, field: str, raw: str, value: Any, y: float = 100) -> dict:
    return {"field": field, "label_he": field, "value_raw": raw, "value_normalized": value, "confidence": 1.0,
            "evidence": {"evidence_id": f"{doc_id}:{field}", "document_id": doc_id, "field": field, "page": 1, "quote": raw,
                         "bbox": [400, y, 550, y + 12], "coord_space": "pdf_points", "page_size": [595.92, 842.88],
                         "witness": "text_layer_exact", "witness_detail": "test"}}


def family_review(doc_id: str, family: str, facts: dict[str, tuple[str, Any]], verdict: str = "VALID",
                  doc_type: str | None = None, **outcomes: str) -> dict:
    rubric = rubrics.for_family(family)
    criteria = []
    for c in rubric["criteria"]:
        outcome = outcomes.get(c["id"].replace("-", "_"), "PASS")
        criteria.append({"criterion_id": c["id"], "title_he": c["title_he"], "method": c["method"], "outcome": outcome,
                         "severity": c["severity"], "reason_code": c["reason_code"], "escalation": c.get("escalation"),
                         "explanation_he": "עבר" if outcome == "PASS" else f"נכשל: {c['title_he']}", "evidence_ids": [],
                         "decided_by": "code"})
    doc_type = doc_type or family
    return {"run_id": new_id("RUN"), "document_id": doc_id,
            "identity": {"provider": "gemini", "mode": "LIVE", "models": {"judge": "test"}, "prompt_version": "test"},
            "rubric_id": rubric["rubric_id"], "rubric_version": rubric["version"], "started_at": now_iso(),
            "finished_at": now_iso(), "doc_type": doc_type, "doc_type_he": DOC_TYPE_HE.get(doc_type, "מסמך"),
            "is_scanned": False, "pages": 1, "legibility": "good", "matched_borrower_id": "BRW-A", "period": None,
            "file_name_period": None,
            "facts": [_fact(doc_id, k, raw, v, 100 + 20 * i) for i, (k, (raw, v)) in enumerate(facts.items())],
            "criteria": criteria, "verdict": verdict, "verdict_reason_codes": [], "summary_he": "סיכום",
            "limitations_he": [], "uncertainty_he": [], "security_flags": [], "demo_marked": True, "payroll_lines": {},
            "usage": {}}


def store_review(doc_id: str, result: dict) -> None:
    doc = repo.document(doc_id)
    repo.start_run({"run_id": result["run_id"], "case_id": doc["case_id"], "document_id": doc_id, "scope": "document",
                    "provider": "gemini", "models": "{}", "rubric_id": result["rubric_id"],
                    "rubric_version": result["rubric_version"], "prompt_version": "test", "status": "running",
                    "stage": "judge", "started_at": now_iso(), "input_hash": doc["sha256"], "trigger": "test"})
    repo.update_run(result["run_id"], status="succeeded", stage="done", finished_at=now_iso(), result=db.jdump(result))
    repo.set_document(doc_id, status="reviewed", stage="done")


def insert(case: str, code: str, borrower: str | None, filename: str) -> str:
    doc_id = new_id("DOC")
    repo.insert_document({"document_id": doc_id, "case_id": case, "borrower_id": borrower, "requirement_code": code,
                          "filename": filename, "mime": "application/pdf", "sha256": new_id("SHA"), "bytes": 1000,
                          "pages": 1, "text_layer_chars": 500, "storage_path": str(FIX / "ido_payslip_2026-07.pdf"),
                          "uploaded_at": now_iso(), "uploaded_by": "customer", "channel": "customer_app",
                          "status": "reviewed", "stage": "done"})
    return doc_id


def id_card(case: str = JOURNEY, verdict: str = "VALID", **outcomes: str) -> str:
    did = insert(case, CODES["id"], "BRW-A", "ido_id_card.pdf")
    store_review(did, family_review(did, "id_document", {"holder_name": (IDO[0], IDO[0]), "holder_id": (IDO[1], IDO[1])},
                                    verdict, **outcomes))
    return did


def statement(case: str = JOURNEY, start: str = "2026-07-01", end: str = "2026-09-30", verdict: str = "VALID",
              name: str = "statement.pdf", **outcomes: str) -> str:
    did = insert(case, CODES["bank"], "BRW-A", name)
    store_review(did, family_review(did, "bank_statement", {"holder_name": (IDO[0], IDO[0]), "statement_from": (start, start),
                                                            "statement_to": (end, end)}, verdict, **outcomes))
    return did


def purpose(case: str = JOURNEY, verdict: str = "VALID", **outcomes: str) -> str:
    did = insert(case, CODES["purpose"], None, "car_quote.pdf")
    store_review(did, family_review(did, "purpose_proof", {"issuer_name": ("אוטו דמו בע״מ", "אוטו דמו בע״מ"),
                                                           "total_amount": ("118,000", 118000.0),
                                                           "issue_date": ("01.10.2026", "2026-10-01")}, verdict, **outcomes))
    return did


def run_case(case: str = JOURNEY) -> None:
    with db.tx() as c:
        c.execute("UPDATE jobs SET status='succeeded' WHERE case_id=?", (case,))
    engine._run_case({"job_id": new_id("JOB"), "case_id": case, "payload": None})

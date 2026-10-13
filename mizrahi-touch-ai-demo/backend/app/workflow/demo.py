"""The presenter's "start a new demo" control. It wipes only the executive demo cases (`MockBankAdapter`
`executive_demo` flag) and never another case, the Gemini usage ledger, rubrics, fixtures or the golden set.

The check for a running review and the delete happen in one write transaction, so a worker cannot claim a job of these
cases in between; a review already running makes the reset wait (DemoBusy) instead of racing it."""
from __future__ import annotations

import shutil

from .. import db
from ..bank.mock_bank import bank
from ..config import settings
from ..store import repo


class DemoBusy(Exception):
    def __init__(self, case_ids: list[str]):
        super().__init__(", ".join(case_ids))
        self.case_ids = case_ids


def reset_executive_cases(actor: str) -> dict:
    case_ids = bank.executive_demo_case_ids()
    marks = ",".join("?" * len(case_ids))
    with db.tx() as c:
        busy = sorted({r["case_id"] for r in c.execute(
            f"SELECT case_id FROM jobs WHERE status='running' AND case_id IN ({marks})", case_ids).fetchall()})
        if busy:
            raise DemoBusy(busy)
        doc_ids = [r["document_id"] for r in c.execute(f"SELECT document_id FROM documents WHERE case_id IN ({marks})",
                                                       case_ids).fetchall()]
        deleted = {}
        for table in repo.CASE_TABLES:
            deleted[table] = c.execute(f"DELETE FROM {table} WHERE case_id IN ({marks})", case_ids).rowcount
    for cid in case_ids:
        shutil.rmtree(settings.uploads_dir / cid, ignore_errors=True)
    for did in doc_ids:
        for png in settings.renders_dir.glob(f"{did}_p*.png"):
            png.unlink(missing_ok=True)
    repo.audit(None, actor, "executive_demo_reset", ",".join(case_ids), {"cases": case_ids, "deleted": deleted})
    return {"reset": case_ids, "deleted": deleted}

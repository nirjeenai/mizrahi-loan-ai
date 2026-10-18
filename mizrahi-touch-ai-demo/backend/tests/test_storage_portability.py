"""Uploaded documents survive a move of the project or its data directory to another path or computer:
`documents.storage_path` is relative to DATA_DIR, absolute paths from an earlier version are remapped to this
instance's uploads directory (and rewritten once by db.migrate), and no stored path is opened outside it."""
from __future__ import annotations

import dataclasses
import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.config import settings
from app.main import app
from app.store import files, repo
from app.util import new_id, now_iso
from app.workflow import engine

CASE = "DEMO-MTZ-2026-003"
PDF = Path(__file__).resolve().parents[2] / "fixtures" / "out" / "main" / "ido_payslip_2026-07.pdf"
OTHER_MACHINE = "/Users/someone-else/Desktop/old copy/mizrahi-touch-ai-demo/backend/data"


@pytest.fixture(autouse=True)
def clean_case():
    repo.reset_case(CASE)
    shutil.rmtree(settings.uploads_dir / CASE, ignore_errors=True)
    yield
    repo.reset_case(CASE)
    shutil.rmtree(settings.uploads_dir / CASE, ignore_errors=True)


def staff() -> TestClient:
    c = TestClient(app)
    c.cookies.set(auth.COOKIES["staff"], auth.issue("staff", "STAFF-DANA"))
    return c


def stored_upload(storage_path: str | None = None) -> tuple[str, Path]:
    """A document whose file sits in DATA_DIR/uploads/<case>/, recorded with the given storage path."""
    doc_id = new_id("DOC")
    path = settings.uploads_dir / CASE / f"{doc_id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = PDF.read_bytes() + f"\n%{doc_id}\n".encode()     # one file per document: (case, sha, requirement) is unique
    path.write_bytes(data)
    repo.insert_document({"document_id": doc_id, "case_id": CASE, "borrower_id": "BRW-A", "requirement_code": "PAYSLIPS:BRW-A",
                          "filename": "payslip.pdf", "mime": "application/pdf",
                          "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "pages": 1,
                          "text_layer_chars": 500, "storage_path": storage_path or f"uploads/{CASE}/{doc_id}.pdf",
                          "uploaded_at": now_iso(), "uploaded_by": "customer", "channel": "customer_app", "status": "stored",
                          "stage": "human_review"})
    return doc_id, path


def test_a_new_upload_is_stored_relative_to_the_data_directory():
    doc, created = engine.submit_document(CASE, "payslip.pdf", "application/pdf", PDF.read_bytes(), "BRW-A",
                                          "PAYSLIPS:BRW-A", "customer", "customer_app")
    assert created
    assert doc["storage_path"] == f"uploads/{CASE}/{doc['document_id']}.pdf"
    assert files.resolve(doc["storage_path"]) == (settings.uploads_dir / CASE / f"{doc['document_id']}.pdf").resolve()


def test_an_absolute_path_from_another_machine_resolves_to_this_uploads_directory():
    doc_id, path = stored_upload()
    legacy = f"{OTHER_MACHINE}/uploads/{CASE}/{doc_id}.pdf"
    assert files.resolve(legacy) == path.resolve()
    with db.tx() as c:
        c.execute("UPDATE documents SET storage_path=? WHERE document_id=?", (legacy, doc_id))
    r = staff().get(f"/api/documents/{doc_id}/file")
    assert r.status_code == 200
    assert hashlib.sha256(r.content).hexdigest() == repo.document(doc_id)["sha256"]
    assert staff().get(f"/api/documents/{doc_id}/pages/1.png?dpi=61").status_code == 200


@pytest.mark.parametrize("stored", ["uploads/../session_secret", "../../etc/passwd", "uploads/../../outside.pdf",
                                    "/etc/passwd", f"{OTHER_MACHINE}/uploads/../../../etc/passwd", ""])
def test_a_stored_path_never_leaves_the_uploads_directory(stored):
    with pytest.raises(files.StoredFileError):
        files.resolve(stored)


def test_a_symlink_out_of_the_uploads_directory_is_refused(tmp_path):
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"%PDF-1.4 not yours")
    link = settings.uploads_dir / CASE / "DOC-LINK.pdf"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(secret)
    with pytest.raises(files.StoredFileError):
        files.resolve(f"uploads/{CASE}/DOC-LINK.pdf")


def test_a_missing_file_is_a_404_not_a_server_error():
    doc_id, path = stored_upload()
    path.unlink()
    assert staff().get(f"/api/documents/{doc_id}/file").status_code == 404
    assert staff().get(f"/api/documents/{doc_id}/pages/1.png").status_code == 404


def test_migration_rewrites_matching_absolute_paths_once_and_leaves_the_rest():
    moved, _ = stored_upload()
    changed_file, changed_path = stored_upload()
    gone, gone_path = stored_upload()
    with db.tx() as c:
        for doc_id in (moved, changed_file, gone):
            c.execute("UPDATE documents SET storage_path=? WHERE document_id=?",
                      (f"{OTHER_MACHINE}/uploads/{CASE}/{doc_id}.pdf", doc_id))
    changed_path.write_bytes(changed_path.read_bytes() + b"%edited")     # differs from the recorded SHA-256
    gone_path.unlink()
    db.migrate(db.connect())
    assert repo.document(moved)["storage_path"] == f"uploads/{CASE}/{moved}.pdf"
    assert repo.document(changed_file)["storage_path"].startswith(OTHER_MACHINE)
    assert repo.document(gone)["storage_path"].startswith(OTHER_MACHINE)
    before = {d["document_id"]: dict(d) for d in repo.documents(CASE)}
    db.migrate(db.connect())
    assert {d["document_id"]: dict(d) for d in repo.documents(CASE)} == before


def test_documents_open_after_the_whole_data_directory_moves(tmp_path, monkeypatch):
    """Copy DATA_DIR elsewhere, take the original away, and serve the documents from the copy."""
    relative, rel_path = stored_upload()
    legacy, legacy_path = stored_upload()
    with db.tx() as c:
        c.execute("UPDATE documents SET storage_path=? WHERE document_id=?",
                  (f"{OTHER_MACHINE}/uploads/{CASE}/{legacy}.pdf", legacy))
    moved = tmp_path / "another computer" / "data"
    shutil.copytree(settings.uploads_dir / CASE, moved / "uploads" / CASE)
    away = tmp_path / "originals"
    away.mkdir()
    for p in (rel_path, legacy_path):
        p.rename(away / p.name)
    try:
        monkeypatch.setattr(files, "settings", dataclasses.replace(settings, data_dir=moved))
        for doc_id in (relative, legacy):
            assert files.resolve(repo.document(doc_id)["storage_path"]).is_relative_to(moved.resolve())
            r = staff().get(f"/api/documents/{doc_id}/file")
            assert r.status_code == 200
            assert hashlib.sha256(r.content).hexdigest() == repo.document(doc_id)["sha256"]
    finally:
        for p in (rel_path, legacy_path):
            (away / p.name).rename(p)


def test_the_shutdown_checkpoint_leaves_every_write_in_the_database_file():
    doc_id, _ = stored_upload()
    db.checkpoint()
    assert Path(f"{settings.db_path}-wal").stat().st_size == 0
    copy = sqlite3.connect(f"file:{settings.db_path}?mode=ro&immutable=1", uri=True)     # the file alone, no WAL
    assert copy.execute("SELECT 1 FROM documents WHERE document_id=?", (doc_id,)).fetchone()
    copy.close()


def test_a_copied_database_file_is_migrated_against_its_new_location(tmp_path, monkeypatch):
    """The SQLite file itself, copied to a new DATA_DIR with its uploads, comes out with relative paths."""
    doc_id, path = stored_upload()
    target = tmp_path / "data"
    (target / "uploads" / CASE).mkdir(parents=True)
    shutil.copy2(path, target / "uploads" / CASE / path.name)
    conn = sqlite3.connect(target / "copy.sqlite3")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE documents (document_id TEXT PRIMARY KEY, storage_path TEXT, sha256 TEXT)")
    conn.execute("INSERT INTO documents VALUES (?,?,?)",
                 (doc_id, f"{OTHER_MACHINE}/uploads/{CASE}/{doc_id}.pdf", repo.document(doc_id)["sha256"]))
    monkeypatch.setattr(files, "settings", dataclasses.replace(settings, data_dir=target))
    assert files.migrate_absolute_paths(conn) == 1
    assert conn.execute("SELECT storage_path FROM documents").fetchone()[0] == f"uploads/{CASE}/{doc_id}.pdf"
    assert files.migrate_absolute_paths(conn) == 0
    conn.close()

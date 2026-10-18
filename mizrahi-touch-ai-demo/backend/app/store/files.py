"""Where an uploaded document's file lives. `documents.storage_path` is stored relative to DATA_DIR
(`uploads/<case>/<document>.<ext>`), so a project or data directory copied to another path or computer keeps working.

Rows written by earlier versions hold an absolute path from the machine they were written on; `resolve` maps them to
the same `uploads/<case>/<file>` under this instance's DATA_DIR. A stored path is only ever opened inside the uploads
directory, or inside the app's synthetic fixtures (documents that tests and tools insert directly)."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path, PurePosixPath

from ..config import PROJECT_DIR, settings

FIXTURES_DIR = PROJECT_DIR / "fixtures"


class StoredFileError(Exception):
    """The stored path is missing, or points outside the directories a document may be read from."""


def stored_path(path: Path) -> str:
    """The value to keep in `documents.storage_path` for a file written under DATA_DIR/uploads."""
    path = Path(path).resolve()
    _require_inside(path, settings.uploads_dir.resolve())
    return path.relative_to(settings.data_dir.resolve()).as_posix()


def resolve(stored: str) -> Path:
    """The file for a stored path on this instance; StoredFileError when it is missing or not allowed."""
    if not stored:
        raise StoredFileError("the document has no stored file")
    uploads = settings.uploads_dir.resolve()
    raw = PurePosixPath(stored.replace("\\", "/"))
    if not raw.is_absolute():
        path = (settings.data_dir / Path(*raw.parts)).resolve()
        _require_inside(path, uploads)
        return _existing(path)
    direct = Path(stored).resolve()
    if direct.is_file() and (_inside(direct, uploads) or _inside(direct, FIXTURES_DIR.resolve())):
        return direct
    legacy = legacy_upload(stored)
    if legacy is not None:
        return _existing(legacy)
    raise StoredFileError("the stored path is outside the uploads directory")


def legacy_upload(stored: str) -> Path | None:
    """For an absolute path written on another machine or directory: the same `uploads/...` tail under this DATA_DIR."""
    parts = PurePosixPath(stored.replace("\\", "/")).parts
    if "uploads" not in parts:
        return None
    tail = parts[len(parts) - 1 - parts[::-1].index("uploads") + 1:]
    if not tail:
        return None
    uploads = settings.uploads_dir.resolve()
    path = uploads.joinpath(*tail).resolve()
    return path if _inside(path, uploads) else None


def migrate_absolute_paths(conn: sqlite3.Connection) -> int:
    """Rewrite absolute upload paths to the relative form when the file is under this DATA_DIR with the recorded
    SHA-256. Rows whose file is not found, or differs, are left as they are. Repeatable: relative rows are skipped."""
    rows = conn.execute("SELECT document_id, storage_path, sha256 FROM documents WHERE storage_path LIKE '/%'").fetchall()
    changed = 0
    for row in rows:
        path = legacy_upload(row["storage_path"])
        if path is None or not path.is_file():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            continue
        conn.execute("UPDATE documents SET storage_path=? WHERE document_id=? AND storage_path=?",
                     (stored_path(path), row["document_id"], row["storage_path"]))
        changed += 1
    return changed


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _require_inside(path: Path, root: Path) -> None:
    if not _inside(path, root):
        raise StoredFileError("the stored path is outside the uploads directory")


def _existing(path: Path) -> Path:
    if not path.is_file():
        raise StoredFileError("the document's file is missing from the uploads directory")
    return path

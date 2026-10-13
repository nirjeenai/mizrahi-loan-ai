"""Evidence utilities — file inspection, page rendering and verification of every
extracted value against the ORIGINAL file.

Born-digital PDFs: a value is `text_layer_exact` only when the PDF text layer prints
it; its box is the union of the printed words (PDF points). Scans and photos have no
text layer: the model's box is cropped and re-read independently; agreement makes it
`vision_reread_confirmed`, anything else stays `vision_unverified`. No box is invented."""
from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from typing import Optional

import pymupdf
from PIL import Image

from ..config import settings
from . import deterministic as det

IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
_BIDI = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def inspect(path: str, mime: str) -> dict:
    if mime in IMAGE_MIMES:
        with Image.open(path) as im:
            return {"pages": 1, "text_layer_chars": 0, "is_image": True, "page_sizes": [[im.width, im.height]]}
    doc = pymupdf.open(path)
    try:
        chars = sum(len(p.get_text().strip()) for p in doc)
        return {"pages": doc.page_count, "text_layer_chars": chars, "is_image": False,
                "page_sizes": [[round(p.rect.width, 2), round(p.rect.height, 2)] for p in doc]}
    finally:
        doc.close()


def render_page(document_id: str, path: str, mime: str, page_no: int, dpi: int = 144) -> bytes:
    """PNG of one page (1-based), cached on disk."""
    cache = settings.renders_dir / f"{document_id}_p{page_no}_{dpi}.png"
    if cache.exists():
        return cache.read_bytes()
    if mime in IMAGE_MIMES:
        with Image.open(path) as im:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="PNG")
            data = buf.getvalue()
    else:
        doc = pymupdf.open(path)
        try:
            data = doc[page_no - 1].get_pixmap(dpi=dpi).tobytes("png")
        finally:
            doc.close()
    cache.write_bytes(data)
    return data


def _norm_token(text: str) -> str:
    s = _BIDI.sub("", unicodedata.normalize("NFKC", text or ""))
    return s.replace("₪", "").strip(" :,;()[]")


def _tokens(text: str) -> list[str]:
    return [t for t in (_norm_token(x) for x in str(text or "").split()) if t]


def _same_token(word: str, target: str) -> bool:
    if not word or not target:
        return False
    a, b = det.parse_amount(word), det.parse_amount(target)
    if re.fullmatch(r"[\d.,]+", word) and re.fullmatch(r"[\d.,]+", target):
        return a is not None and b is not None and abs(a - b) < 0.005
    return det.name_key(word) == det.name_key(target) or word == target


def text_layer_locate(path: str, page_no: int, value: Optional[str], quote: Optional[str]) -> Optional[dict]:
    """Find a printed value on the page's text layer. Returns {bbox, page_size, found_text, occurrences}."""
    targets = _tokens(quote or "") or _tokens(value or "")
    if not targets:
        return None
    doc = pymupdf.open(path)
    try:
        if page_no < 1 or page_no > doc.page_count:
            return None
        page = doc[page_no - 1]
        words = [(w[0], w[1], w[2], w[3], _norm_token(w[4]), (w[5], w[6])) for w in page.get_text("words")]
        size = [round(page.rect.width, 2), round(page.rect.height, 2)]
    finally:
        doc.close()
    lines: dict[tuple, list] = {}
    for w in words:
        lines.setdefault(w[5], []).append(w)
    matches = []
    for line_words in lines.values():
        used, boxes = set(), []
        for t in targets:
            hit = next((i for i, w in enumerate(line_words) if i not in used and _same_token(w[4], t)), None)
            if hit is None:
                break
            used.add(hit)
            boxes.append(line_words[hit])
        else:
            x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
            x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
            matches.append({"bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                            "found_text": " ".join(b[4] for b in sorted(boxes, key=lambda b: -b[2]))})
    if not matches:
        return None
    return {**matches[0], "page_size": size, "occurrences": len(matches)}


def norm_box_to_page(box_2d: list[int], page_size: list[float]) -> list[float]:
    """[ymin, xmin, ymax, xmax] on a 0–1000 grid → [x0, y0, x1, y1] in the page's own units."""
    ymin, xmin, ymax, xmax = (max(0, min(1000, int(v))) for v in box_2d)
    w, h = page_size
    return [round(xmin / 1000 * w, 2), round(ymin / 1000 * h, 2), round(xmax / 1000 * w, 2), round(ymax / 1000 * h, 2)]


def crop_for_reread(document_id: str, path: str, mime: str, page_no: int, box_2d: list[int]) -> Optional[bytes]:
    if not box_2d or len(box_2d) != 4:
        return None
    png = render_page(document_id, path, mime, page_no, dpi=200)
    with Image.open(io.BytesIO(png)) as im:
        w, h = im.size
        ymin, xmin, ymax, xmax = (max(0, min(1000, int(v))) for v in box_2d)
        if ymax <= ymin or xmax <= xmin:
            return None
        bw, bh = (xmax - xmin) / 1000 * w, (ymax - ymin) / 1000 * h
        pad_x, pad_y = max(18, bw * 0.25), max(12, bh * 0.6)
        box = (int(max(0, xmin / 1000 * w - pad_x)), int(max(0, ymin / 1000 * h - pad_y)),
               int(min(w, xmax / 1000 * w + pad_x)), int(min(h, ymax / 1000 * h + pad_y)))
        crop = im.crop(box)
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        return buf.getvalue()


def values_agree(field: str, a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False
    if field in ("gross_pay", "net_pay", "total_deductions"):
        x, y = det.parse_amount(a), det.parse_amount(b)
        return x is not None and y is not None and abs(x - y) < 0.5
    if field == "salary_period":
        return det.parse_month(a) is not None and det.parse_month(a) == det.parse_month(b)
    if field in ("employee_id", "employer_id"):
        return det.digits(a) != "" and det.digits(a) == det.digits(b)
    if field in ("employee_name", "employer_name"):
        return det.name_relation(a, b) in ("same", "variant")
    return det.name_key(a) == det.name_key(b)


def file_bytes(path: str) -> bytes:
    return Path(path).read_bytes()

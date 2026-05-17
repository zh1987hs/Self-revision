"""Caption detection for figures and tables."""
from __future__ import annotations

import re

from .models import FigureCaption, PageData

CAPTION_RE = re.compile(r"(?P<kind>图|Fig\.|Figure|表|Table)\s*(?P<num>\d+(?:[-.]\d+)*)\s*[:：\-—]?\s*(?P<title>.*)", re.I)


def detect_captions(pages: list[PageData]) -> tuple[list[FigureCaption], list[FigureCaption]]:
    """Detect figure/table captions from page text and associate same-page images conservatively."""
    figures: list[FigureCaption] = []
    tables: list[FigureCaption] = []
    for page in pages:
        image_ids = [img.image_id for img in page.images]
        for line in page.text.splitlines():
            m = CAPTION_RE.search(line.strip())
            if not m:
                continue
            kind_raw = m.group("kind")
            is_table = kind_raw.lower().startswith("table") or kind_raw == "表"
            caption = line.strip()
            item = FigureCaption(
                figure_id=f"{'table' if is_table else 'figure'}_{page.page_number}_{len(tables if is_table else figures)+1}",
                caption=caption,
                page_number=page.page_number,
                nearby_images=[] if is_table else image_ids,
                confidence=0.6 if image_ids else 0.4,
                kind="table" if is_table else "figure",
            )
            (tables if is_table else figures).append(item)
    return figures, tables

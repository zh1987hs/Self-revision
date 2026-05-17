"""Placeholder simple table extractor for later phases."""
from __future__ import annotations

from .models import PageData


def extract_tables_from_pages(pages: list[PageData]) -> list[list[str]]:
    """Return text lines that look table-like; MVP keeps this conservative."""
    tables: list[list[str]] = []
    for page in pages:
        current: list[str] = []
        for line in page.text.splitlines():
            if line.count(" ") >= 3 or "\t" in line:
                current.append(line)
            elif current:
                if len(current) >= 2:
                    tables.append(current)
                current = []
        if len(current) >= 2:
            tables.append(current)
    return tables

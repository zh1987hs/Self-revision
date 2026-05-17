"""Text extraction from PyMuPDF pages."""
from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


def extract_page_text(page: Any) -> str:
    """Return plain text from a PyMuPDF page with a safe fallback."""
    try:
        return page.get_text("text") or ""
    except Exception as exc:  # pragma: no cover - defensive around PDF parser errors
        LOGGER.warning("Failed to extract page text: %s", exc)
        return ""

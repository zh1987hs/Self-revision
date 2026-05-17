"""PDF loading orchestration."""
from __future__ import annotations

import logging
from pathlib import Path


from .image_extractor import extract_images_from_page, save_page_screenshot
from .models import PageData
from .text_extractor import extract_page_text
from .utils import ensure_dir, safe_stem

LOGGER = logging.getLogger(__name__)


def load_pdf(pdf_path: str | Path, work_dir: str | Path, save_page_images: bool = False) -> tuple[list[PageData], int]:
    """Load a PDF and extract per-page text, dimensions, screenshots and embedded images."""
    path = Path(pdf_path)
    pdf_name = path.name
    base_dir = ensure_dir(Path(work_dir) / safe_stem(pdf_name))
    image_dir = ensure_dir(base_dir / "images")
    page_dir = ensure_dir(base_dir / "pages")
    pages: list[PageData] = []

    try:
        import fitz
        doc = fitz.open(path.as_posix())
    except Exception as exc:
        raise RuntimeError(f"无法打开 PDF：{path}。原因：{exc}") from exc

    with doc:
        for i, page in enumerate(doc, start=1):
            rect = page.rect
            text = extract_page_text(page)
            screenshot_path = None
            if save_page_images:
                try:
                    screenshot_path = save_page_screenshot(page, page_dir, pdf_name, i)
                except Exception as exc:
                    LOGGER.warning("Failed to save screenshot for %s page %s: %s", pdf_name, i, exc)
            images = extract_images_from_page(doc, page, image_dir, pdf_name, i)
            pages.append(
                PageData(
                    pdf_name=pdf_name,
                    page_number=i,
                    text=text,
                    width=float(rect.width),
                    height=float(rect.height),
                    screenshot_path=screenshot_path,
                    images=images,
                )
            )
    return pages, len(pages)

"""Optional OCR support for page screenshots and embedded images."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .models import PageData

LOGGER = logging.getLogger(__name__)


@dataclass
class OcrAvailability:
    """Result of checking whether pytesseract and the Tesseract binary are usable."""

    available: bool
    message: str
    version: str | None = None


@dataclass
class OcrRunSummary:
    """Structured summary of an OCR run."""

    enabled: bool
    available: bool
    language: str
    message: str
    page_images_processed: int = 0
    embedded_images_processed: int = 0
    errors: list[str] = field(default_factory=list)


def check_ocr_availability() -> OcrAvailability:
    """Check pytesseract package and the system tesseract executable without raising."""
    try:
        import pytesseract
    except Exception:
        return OcrAvailability(False, "未安装 pytesseract Python 包；已跳过 OCR。")

    try:
        version = str(pytesseract.get_tesseract_version())
    except Exception:
        return OcrAvailability(False, "未检测到 tesseract 可执行程序；已跳过 OCR。请安装 Tesseract OCR 并配置 PATH。")
    return OcrAvailability(True, "OCR 可用。", version)


def _ocr_image(image_path: str | Path, lang: str) -> str:
    """Run OCR for one image path and return stripped text."""
    from PIL import Image
    import pytesseract

    with Image.open(image_path) as img:
        return (pytesseract.image_to_string(img, lang=lang) or "").strip()


def run_ocr_on_pages(pages: list[PageData], lang: str = "chi_sim+eng") -> OcrRunSummary:
    """Run OCR on saved page screenshots and embedded images, storing text on models.

    Page screenshots are used to recover text from scanned PDFs; embedded-image OCR helps
    extract figure labels and image text. Errors are collected in the summary instead of
    aborting the whole audit.
    """
    availability = check_ocr_availability()
    summary = OcrRunSummary(True, availability.available, lang, availability.message)
    if not availability.available:
        LOGGER.warning(availability.message)
        return summary

    for page in pages:
        if page.screenshot_path:
            try:
                page.ocr_text = _ocr_image(page.screenshot_path, lang)
                if page.ocr_text:
                    summary.page_images_processed += 1
            except Exception as exc:  # pragma: no cover - depends on local OCR/language data
                msg = f"第 {page.page_number} 页截图 OCR 失败：{exc}"
                LOGGER.warning(msg)
                summary.errors.append(msg)
        for image in page.images:
            try:
                image.ocr_text = _ocr_image(image.file_path, lang)
                if image.ocr_text:
                    image.nearby_text = f"{image.nearby_text}\n{image.ocr_text}".strip()
                    summary.embedded_images_processed += 1
            except Exception as exc:  # pragma: no cover - depends on local OCR/language data
                msg = f"图片 {image.image_id} OCR 失败：{exc}"
                LOGGER.warning(msg)
                summary.errors.append(msg)
    return summary

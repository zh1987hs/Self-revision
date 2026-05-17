"""Image extraction helpers using PyMuPDF and Pillow."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any


from .models import ExtractedImage
from .utils import ensure_dir, sha256_bytes, sha256_file

LOGGER = logging.getLogger(__name__)


def save_page_screenshot(page: Any, out_dir: Path, pdf_name: str, page_number: int, zoom: float = 1.5) -> str:
    """Render and save a page screenshot."""
    import fitz

    ensure_dir(out_dir)
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    path = out_dir / f"{Path(pdf_name).stem}_page_{page_number:04d}.png"
    pix.save(path.as_posix())
    return path.as_posix()


def _find_image_bbox(page: Any, xref: int) -> tuple[float, float, float, float] | None:
    try:
        rects = page.get_image_rects(xref)
        if rects:
            r = rects[0]
            return (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
    except Exception:
        return None
    return None


def _save_image_bytes(image_bytes: bytes, image_format: str, path: Path) -> tuple[int, int, str]:
    ensure_dir(path.parent)
    suffix = (image_format or "png").lower()
    if suffix == "jpeg":
        suffix = "jpg"
    final = path.with_suffix(f".{suffix}")
    try:
        from PIL import Image
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            img.save(final)
            fmt = (img.format or image_format or suffix).lower()
    except Exception:
        final.write_bytes(image_bytes)
        width, height, fmt = 0, 0, image_format or suffix
    return width, height, final.as_posix()


def extract_images_from_page(doc: Any, page: Any, out_dir: str | Path, pdf_name: str, page_number: int) -> list[ExtractedImage]:
    """Extract embedded images from one page and return image metadata."""
    images: list[ExtractedImage] = []
    out_path = ensure_dir(out_dir)
    try:
        page_images = page.get_images(full=True)
    except Exception as exc:
        LOGGER.warning("Failed to enumerate images on page %s: %s", page_number, exc)
        return images

    for idx, info in enumerate(page_images, start=1):
        xref = int(info[0]) if info else None
        if xref is None:
            continue
        try:
            extracted = doc.extract_image(xref)
            data = extracted.get("image", b"")
            ext = extracted.get("ext", "png")
            base = out_path / f"{Path(pdf_name).stem}_p{page_number:04d}_img{idx:03d}_xref{xref}"
            width, height, file_path = _save_image_bytes(data, ext, base)
            file_hash = sha256_file(file_path) if Path(file_path).exists() else sha256_bytes(data)
            images.append(
                ExtractedImage(
                    image_id=f"{Path(pdf_name).stem}_p{page_number:04d}_img{idx:03d}_xref{xref}",
                    pdf_name=pdf_name,
                    page_number=page_number,
                    xref=xref,
                    width=width or int(extracted.get("width", 0) or 0),
                    height=height or int(extracted.get("height", 0) or 0),
                    file_path=file_path,
                    image_format=ext,
                    file_hash=file_hash,
                    bbox=_find_image_bbox(page, xref),
                )
            )
        except Exception as exc:  # pragma: no cover - depends on damaged PDFs
            LOGGER.warning("Failed to extract image xref=%s on page %s: %s", xref, page_number, exc)
    return images

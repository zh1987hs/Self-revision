"""Image duplicate and perceptual similarity checks."""
from __future__ import annotations

import itertools
import logging
from collections import Counter
from pathlib import Path


from .models import ExtractedImage, ImageDuplicateFinding
from .utils import ensure_dir

LOGGER = logging.getLogger(__name__)

DECORATION_KEYWORDS = ("logo", "校徽", "二维码", "qr", "page header", "页眉", "页脚")


def compute_phash(image_path: str | Path) -> str | None:
    """Compute perceptual hash for an image path."""
    try:
        import imagehash
        from PIL import Image

        with Image.open(image_path) as img:
            return str(imagehash.phash(img.convert("RGB")))
    except Exception as exc:
        LOGGER.warning("Failed to compute perceptual hash for %s: %s", image_path, exc)
        return None


def hamming_distance(hash_a: str | None, hash_b: str | None) -> int | None:
    """Return perceptual hash Hamming distance."""
    if not hash_a or not hash_b:
        return None
    try:
        import imagehash
        return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)
    except Exception:
        return None


def _is_small_or_extreme(img: ExtractedImage, min_image_size: int) -> bool:
    if img.width < min_image_size or img.height < min_image_size:
        img.decoration_reason = f"image smaller than {min_image_size}px"
        return True
    if img.width <= 0 or img.height <= 0:
        img.decoration_reason = "invalid image dimensions"
        return True
    ratio = max(img.width / img.height, img.height / img.width)
    if ratio > 8:
        img.decoration_reason = "extreme aspect ratio"
        return True
    if any(k.lower() in img.nearby_text.lower() for k in DECORATION_KEYWORDS):
        img.decoration_reason = "nearby decoration keyword"
    return False


def _risk_for_pair(a: ExtractedImage, b: ExtractedImage, similarity_type: str, distance: int | None) -> str:
    if a.decoration_reason or b.decoration_reason:
        return "low"
    area = min(a.width * a.height, b.width * b.height)
    if similarity_type in {"exact_duplicate", "reused_pdf_image_object"}:
        return "high" if a.page_number != b.page_number and area >= 80_000 else "medium"
    if similarity_type == "possible_partial_duplicate":
        return "high" if area >= 80_000 else "medium"
    if distance is not None and distance <= 4:
        return "medium"
    return "low"


def _make_preview(a: ExtractedImage, b: ExtractedImage, out_dir: Path, pair_id: str) -> str | None:
    try:
        ensure_dir(out_dir)
        from PIL import Image, ImageDraw
        with Image.open(a.file_path) as ia, Image.open(b.file_path) as ib:
            ia.thumbnail((240, 240))
            ib.thumbnail((240, 240))
            w = ia.width + ib.width + 30
            h = max(ia.height, ib.height) + 40
            canvas = Image.new("RGB", (w, h), "white")
            canvas.paste(ia.convert("RGB"), (10, 30))
            canvas.paste(ib.convert("RGB"), (ia.width + 20, 30))
            draw = ImageDraw.Draw(canvas)
            draw.text((10, 8), f"{a.image_id}  vs  {b.image_id}", fill="black")
            path = out_dir / f"{pair_id}.jpg"
            canvas.save(path, quality=88)
            return path.as_posix()
    except Exception as exc:
        LOGGER.warning("Failed to create duplicate preview: %s", exc)
        return None


def _tile_hashes(image_path: str | Path, grid: int = 3) -> list[str]:
    hashes: list[str] = []
    try:
        import imagehash
        from PIL import Image
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            w, h = img.size
            for y in range(grid):
                for x in range(grid):
                    crop = img.crop((x * w // grid, y * h // grid, (x + 1) * w // grid, (y + 1) * h // grid))
                    hashes.append(str(imagehash.phash(crop)))
    except Exception:
        return []
    return hashes


def _partial_distance(a: ExtractedImage, b: ExtractedImage) -> int | None:
    if min(a.width, a.height, b.width, b.height) < 160:
        return None
    ha = _tile_hashes(a.file_path)
    hb = _tile_hashes(b.file_path)
    if not ha or not hb:
        return None
    import imagehash
    distances = [imagehash.hex_to_hash(x) - imagehash.hex_to_hash(y) for x in ha for y in hb]
    return min(distances) if distances else None


def find_duplicate_images(
    images: list[ExtractedImage],
    preview_dir: str | Path,
    threshold: int = 8,
    min_image_size: int = 80,
    partial_threshold: int = 3,
) -> list[ImageDuplicateFinding]:
    """Detect exact, reused xref, visual and possible partial duplicate images."""
    preview_path = ensure_dir(preview_dir)
    for img in images:
        if not img.perceptual_hash:
            img.perceptual_hash = compute_phash(img.file_path)
        _is_small_or_extreme(img, min_image_size)

    skipped_ids = {img.image_id for img in images if img.decoration_reason and "smaller" in img.decoration_reason}
    candidates = [img for img in images if img.image_id not in skipped_ids]
    hash_counts = Counter(img.file_hash for img in candidates)
    for img in candidates:
        if hash_counts[img.file_hash] >= 5 and (img.width * img.height) < 30_000:
            img.decoration_reason = "frequent small repeated image, likely_decoration"

    findings: list[ImageDuplicateFinding] = []
    seen: set[tuple[str, str, str]] = set()

    for idx, (a, b) in enumerate(itertools.combinations(candidates, 2), start=1):
        sim_type = None
        dist = hamming_distance(a.perceptual_hash, b.perceptual_hash)
        if a.xref is not None and a.xref == b.xref and (a.page_number != b.page_number or a.image_id != b.image_id):
            sim_type = "reused_pdf_image_object"
            dist = 0 if dist is None else dist
        elif a.file_hash == b.file_hash:
            sim_type = "exact_duplicate"
            dist = 0 if dist is None else dist
        elif dist is not None and dist <= threshold:
            sim_type = "visually_similar"
        else:
            pd = _partial_distance(a, b)
            if pd is not None and pd <= partial_threshold:
                sim_type = "possible_partial_duplicate"
                dist = pd
        if not sim_type:
            continue
        key = tuple(sorted([a.image_id, b.image_id]) + [sim_type])
        if key in seen:
            continue
        seen.add(key)
        pair_id = f"pair_{len(findings)+1:04d}"
        preview = _make_preview(a, b, preview_path, pair_id)
        risk = _risk_for_pair(a, b, sim_type, dist)
        explanation = {
            "exact_duplicate": "两张图片文件字节 hash 完全一致，提示疑似重复，需复核是否为合理复用。",
            "reused_pdf_image_object": "PDF 中同一个图片对象 xref 被多处引用，需复核是否为模板/装饰或同一实验图像复用。",
            "visually_similar": "两张图片感知哈希距离低于阈值，视觉上高度相似，需人工复核。",
            "possible_partial_duplicate": "可能是局部重复或复用实验图像区域，需人工核对。",
        }[sim_type]
        if a.decoration_reason or b.decoration_reason:
            explanation += " 由于图片尺寸/上下文呈现装饰性特征，风险等级已降低。"
        findings.append(ImageDuplicateFinding(pair_id, a, b, sim_type, dist, risk, explanation, preview))
    return findings

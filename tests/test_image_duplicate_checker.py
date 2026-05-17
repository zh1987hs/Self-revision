from pathlib import Path

import pytest

pytest.importorskip("PIL")
pytest.importorskip("imagehash")

from PIL import Image, ImageDraw

from thesis_audit.image_duplicate_checker import find_duplicate_images
from thesis_audit.models import ExtractedImage
from thesis_audit.utils import sha256_file


def _make_img(path: Path, color="white", mark=True):
    img = Image.new("RGB", (160, 160), color)
    draw = ImageDraw.Draw(img)
    if mark:
        draw.rectangle((30, 30, 130, 130), outline="black", width=4)
        draw.line((30, 130, 130, 30), fill="red", width=3)
    img.save(path)
    return path


def _meta(path: Path, image_id: str, page: int, xref: int):
    return ExtractedImage(image_id, "demo.pdf", page, xref, 160, 160, path.as_posix(), "png", sha256_file(path))


def test_image_hash_duplicate(tmp_path):
    a = _make_img(tmp_path / "a.png")
    b = tmp_path / "b.png"
    b.write_bytes(a.read_bytes())
    findings = find_duplicate_images([_meta(a, "a", 1, 1), _meta(b, "b", 2, 2)], tmp_path / "previews")
    assert any(f.similarity_type == "exact_duplicate" for f in findings)


def test_image_hash_similar(tmp_path):
    a = _make_img(tmp_path / "a.png")
    img = Image.open(a).resize((158, 158)).resize((160, 160))
    b = tmp_path / "b.jpg"
    img.save(b, quality=90)
    findings = find_duplicate_images([_meta(a, "a", 1, 1), _meta(b, "b", 2, 2)], tmp_path / "previews", threshold=10)
    assert any(f.similarity_type in {"visually_similar", "exact_duplicate"} for f in findings)

from thesis_audit.data_consistency_checker import extract_numbers
from thesis_audit.models import ExtractedImage, PageData
from thesis_audit.ocr import check_ocr_availability, run_ocr_on_pages


def test_check_ocr_availability_never_raises():
    availability = check_ocr_availability()
    assert isinstance(availability.available, bool)
    assert availability.message


def test_ocr_text_is_used_by_numeric_extraction():
    page = PageData("scan.pdf", 1, "", 595.0, 842.0, ocr_text="p = 1.2\nR²=1.5")
    nums = extract_numbers([page])
    assert {n.type for n in nums} >= {"p_value", "r2"}


def test_run_ocr_disabled_gracefully_when_unavailable(monkeypatch):
    import thesis_audit.ocr as ocr_module

    monkeypatch.setattr(ocr_module, "check_ocr_availability", lambda: ocr_module.OcrAvailability(False, "missing"))
    summary = run_ocr_on_pages([PageData("x.pdf", 1, "", 1.0, 1.0)], lang="eng")
    assert summary.enabled is True
    assert summary.available is False
    assert summary.message == "missing"


def test_embedded_image_ocr_text_is_used_by_numeric_extraction(tmp_path):
    image = ExtractedImage(
        image_id="img1",
        pdf_name="scan.pdf",
        page_number=1,
        xref=1,
        width=100,
        height=100,
        file_path=(tmp_path / "img.png").as_posix(),
        image_format="png",
        file_hash="abc",
        ocr_text="p = 1.3",
    )
    page = PageData("scan.pdf", 1, "", 595.0, 842.0, images=[image])
    nums = extract_numbers([page])
    assert any(n.type == "p_value" and n.value == 1.3 for n in nums)

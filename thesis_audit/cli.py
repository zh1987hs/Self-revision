"""Command line entry point."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .data_consistency_checker import run_data_checks
from .figure_detector import detect_captions
from .image_duplicate_checker import find_duplicate_images
from .models import AuditResult
from .ocr import OcrRunSummary, check_ocr_availability, run_ocr_on_pages
from .pdf_loader import load_pdf
from .report_generator import generate_reports
from .statistics_checker import check_statistical_expressions
from .table_extractor import extract_tables_from_pages
from .utils import ensure_dir, safe_stem

LOGGER = logging.getLogger("thesis_audit")


def _discover_pdfs(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"输入文件不是 PDF：{input_path}")
        return [input_path]
    if input_path.is_dir():
        pattern = "**/*.pdf" if recursive else "*.pdf"
        return sorted(input_path.glob(pattern))
    raise FileNotFoundError(f"输入路径不存在：{input_path}")


def _try_ocr_enabled(enabled: bool, lang: str) -> bool:
    """Log OCR availability and return whether OCR can run."""
    if not enabled:
        return False
    availability = check_ocr_availability()
    if availability.available:
        LOGGER.info("OCR is available with language setting: %s; tesseract=%s", lang, availability.version)
    else:
        LOGGER.warning(availability.message)
    return availability.available


def audit_pdf(pdf: Path, out_dir: Path, args: argparse.Namespace) -> tuple[str, str]:
    """Run MVP audit for one PDF."""
    work_dir = ensure_dir(out_dir / "assets")
    pages, page_count = load_pdf(pdf, work_dir, save_page_images=args.save_page_images or args.ocr)
    ocr_summary = OcrRunSummary(False, False, args.ocr_lang, "OCR 未启用。")
    if args.ocr:
        ocr_summary = run_ocr_on_pages(pages, lang=args.ocr_lang)
    images = [img for page in pages for img in page.images]
    dup_findings = find_duplicate_images(images, out_dir / "previews" / safe_stem(pdf.name), threshold=args.image_threshold, min_image_size=args.min_image_size)
    numbers, data_findings = run_data_checks(pdf.name, pages)
    stat_findings = check_statistical_expressions(pdf.name, numbers)
    figures, tables = detect_captions(pages)
    extracted_tables = extract_tables_from_pages(pages)
    findings = [d.to_risk() for d in dup_findings] + data_findings + stat_findings
    result = AuditResult(
        pdf.name,
        page_count,
        pages,
        images,
        findings,
        figures,
        tables,
        len(extracted_tables),
        ocr_enabled=ocr_summary.enabled,
        ocr_available=ocr_summary.available,
        ocr_language=ocr_summary.language,
        ocr_message=ocr_summary.message,
        ocr_page_images_processed=ocr_summary.page_images_processed,
        ocr_embedded_images_processed=ocr_summary.embedded_images_processed,
        ocr_errors=ocr_summary.errors,
    )
    return generate_reports(result, out_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="学位论文 PDF 学术规范自检系统 MVP")
    parser.add_argument("input", help="PDF 文件或 PDF 文件夹")
    parser.add_argument("--out", required=True, help="输出目录")
    parser.add_argument("--ocr", action="store_true", help="启用 OCR，识别页面截图和内嵌图片文字")
    parser.add_argument("--ocr-lang", default="chi_sim+eng", help="OCR 语言，默认 chi_sim+eng")
    parser.add_argument("--image-threshold", type=int, default=8, help="感知哈希汉明距离阈值，默认 8")
    parser.add_argument("--min-image-size", type=int, default=80, help="小于该尺寸的图片跳过重复检测，默认 80")
    parser.add_argument("--recursive", action="store_true", help="递归处理文件夹")
    parser.add_argument("--save-page-images", action="store_true", help="保存每一页截图")
    parser.add_argument("--debug", action="store_true", help="输出调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    _try_ocr_enabled(args.ocr, args.ocr_lang)
    out_dir = ensure_dir(args.out)
    try:
        pdfs = _discover_pdfs(Path(args.input), args.recursive)
    except Exception as exc:
        LOGGER.error("输入错误：%s", exc)
        return 2
    if not pdfs:
        LOGGER.error("未找到 PDF 文件：%s", args.input)
        return 2
    for pdf in pdfs:
        try:
            html_path, json_path = audit_pdf(pdf, out_dir, args)
            LOGGER.info("完成：%s", pdf)
            LOGGER.info("HTML 报告：%s", html_path)
            LOGGER.info("JSON 结果：%s", json_path)
        except Exception as exc:
            LOGGER.exception("处理失败：%s。原因：%s", pdf, exc)
            return 1
    return 0

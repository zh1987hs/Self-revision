"""Core dataclasses for thesis_audit."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExtractedImage:
    image_id: str
    pdf_name: str
    page_number: int
    xref: int | None
    width: int
    height: int
    file_path: str
    image_format: str
    file_hash: str
    perceptual_hash: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    nearby_text: str = ""
    decoration_reason: str | None = None
    ocr_text: str = ""


@dataclass
class PageData:
    pdf_name: str
    page_number: int
    text: str
    width: float
    height: float
    screenshot_path: str | None = None
    images: list[ExtractedImage] = field(default_factory=list)
    ocr_text: str = ""


@dataclass
class NumberObservation:
    value: float
    unit: str | None
    context: str
    page_number: int
    line_text: str
    type: str
    raw: str
    comparator: str | None = None
    secondary_value: float | None = None


@dataclass
class RiskFinding:
    pdf_name: str
    page_number: int
    issue_type: str
    risk_level: str
    trigger_rule: str
    evidence_summary: str
    review_suggestion: str
    preview_path: str | None = None
    context: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageDuplicateFinding:
    pair_id: str
    image_a: ExtractedImage
    image_b: ExtractedImage
    similarity_type: str
    hash_distance: int | None
    risk_level: str
    explanation: str
    preview_path: str | None

    def to_risk(self) -> RiskFinding:
        page = self.image_a.page_number
        return RiskFinding(
            pdf_name=self.image_a.pdf_name,
            page_number=page,
            issue_type=self.similarity_type,
            risk_level=self.risk_level,
            trigger_rule=f"image duplicate rule: {self.similarity_type}",
            evidence_summary=(
                f"图片 {self.image_a.image_id}（第{self.image_a.page_number}页）与 "
                f"{self.image_b.image_id}（第{self.image_b.page_number}页）疑似重复；"
                f"hash 距离={self.hash_distance}。"
            ),
            review_suggestion="请人工核对两处图片是否为合理复用（如 logo/示意图）或可能存在异常复用。",
            preview_path=self.preview_path,
            extra={"image_a": asdict(self.image_a), "image_b": asdict(self.image_b)},
        )


@dataclass
class FigureCaption:
    figure_id: str
    caption: str
    page_number: int
    nearby_images: list[str] = field(default_factory=list)
    confidence: float = 0.5
    kind: str = "figure"


@dataclass
class AuditResult:
    pdf_name: str
    page_count: int
    pages: list[PageData]
    images: list[ExtractedImage]
    findings: list[RiskFinding]
    figures: list[FigureCaption] = field(default_factory=list)
    tables: list[FigureCaption] = field(default_factory=list)
    extracted_table_count: int = 0
    ocr_enabled: bool = False
    ocr_available: bool = False
    ocr_language: str | None = None
    ocr_message: str = ""
    ocr_page_images_processed: int = 0
    ocr_embedded_images_processed: int = 0
    ocr_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def path_to_posix(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return Path(path).as_posix()

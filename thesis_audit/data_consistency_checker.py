"""Rule-based numeric extraction and data consistency checks."""
from __future__ import annotations

import math
import re
from typing import Iterable

from .models import NumberObservation, PageData, RiskFinding

NUM = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
SCI = r"[-+]?\d+(?:\.\d+)?\s*[×x]\s*10\s*\^?\s*[-+]?\d+"
NUM_TOKEN = rf"(?:{SCI}|{NUM})"


def _to_float(raw: str) -> float:
    s = raw.replace("，", "").replace(",", "").strip()
    sci = re.match(r"([-+]?\d+(?:\.\d+)?)\s*[×x]\s*10\s*\^?\s*([-+]?\d+)", s)
    if sci:
        return float(sci.group(1)) * (10 ** int(sci.group(2)))
    return float(s)


def _context(line: str, start: int, end: int, radius: int = 45) -> str:
    return line[max(0, start - radius): min(len(line), end + radius)].strip()


def extract_numbers_from_text(text: str, page_number: int) -> list[NumberObservation]:
    """Extract structured numeric observations from text lines."""
    observations: list[NumberObservation] = []

    def add(match: re.Match[str], typ: str, value_group: int | str, unit: str | None = None, comparator: str | None = None, secondary: float | None = None) -> None:
        raw_value = match.group(value_group)
        try:
            value = _to_float(raw_value)
        except ValueError:
            return
        observations.append(NumberObservation(value, unit, _context(line, match.start(), match.end()), page_number, line.strip(), typ, match.group(0), comparator, secondary))
        occupied.append((match.start(), match.end(), typ))

    for line in text.splitlines():
        occupied: list[tuple[int, int, str]] = []
        # mean ± SD first so the SD can be validated explicitly.
        for m in re.finditer(rf"(?P<mean>{NUM_TOKEN})\s*[±＋]\s*(?P<sd>{NUM_TOKEN})", line):
            try:
                mean = _to_float(m.group("mean"))
                sd = _to_float(m.group("sd"))
            except ValueError:
                continue
            observations.append(NumberObservation(mean, None, _context(line, m.start(), m.end()), page_number, line.strip(), "mean_sd", m.group(0), None, sd))
            occupied.append((m.start(), m.end(), "mean_sd"))

        for m in re.finditer(rf"\b[pP]\s*(?P<op>[<>=≤≥≦≧＞＜])\s*(?P<value>{NUM_TOKEN})", line):
            add(m, "p_value", "value", comparator=m.group("op"))

        for m in re.finditer(rf"\bR(?:\^?2|²)\s*(?P<op>[=<>≤≥≦≧＞＜])\s*(?P<value>{NUM_TOKEN})", line, flags=re.I):
            add(m, "r2", "value", comparator=m.group("op"))

        for m in re.finditer(rf"(?:Pearson\s+)?\br\s*(?P<op>[=<>≤≥≦≧＞＜])\s*(?P<value>{NUM_TOKEN})", line, flags=re.I):
            add(m, "correlation", "value", comparator=m.group("op"))

        for m in re.finditer(rf"(?P<value>{NUM_TOKEN})\s*%", line):
            add(m, "percentage", "value", unit="%")

        for m in re.finditer(rf"(?<![\w.])(?P<value>{NUM_TOKEN})(?![\w.])", line):
            if any(m.start() >= s and m.end() <= e for s, e, _ in occupied):
                continue
            add(m, "general", "value")
    return observations


def page_combined_text(page: PageData) -> str:
    """Return native PDF text plus OCR text from page screenshot and embedded images."""
    parts = [page.text]
    if page.ocr_text:
        parts.append(page.ocr_text)
    parts.extend(image.ocr_text for image in page.images if image.ocr_text)
    return "\n".join(part for part in parts if part)


def extract_numbers(pages: Iterable[PageData]) -> list[NumberObservation]:
    """Extract numeric observations from all pages."""
    nums: list[NumberObservation] = []
    for page in pages:
        nums.extend(extract_numbers_from_text(page_combined_text(page), page.page_number))
    return nums


def check_invalid_ranges(pdf_name: str, observations: Iterable[NumberObservation]) -> list[RiskFinding]:
    """Check mathematically impossible or suspicious numeric ranges."""
    findings: list[RiskFinding] = []
    for obs in observations:
        finding: RiskFinding | None = None
        if obs.type == "percentage" and (obs.value < 0 or obs.value > 100):
            finding = RiskFinding(pdf_name, obs.page_number, "invalid_percentage_range", "medium", "percentage must be between 0 and 100", f"发现百分比 {obs.raw} 超出 0-100 范围。", "请核对原文、表格或 PDF 抽取结果，确认是否为单位/解析问题或数据异常。", context=obs.context)
        elif obs.type == "p_value" and (obs.value < 0 or obs.value > 1):
            finding = RiskFinding(pdf_name, obs.page_number, "invalid_p_value_range", "high", "p value must be between 0 and 1", f"发现 p 值表达 {obs.raw} 超出 0-1 范围。", "请复核统计检验输出和论文中的 p 值录入。", context=obs.context)
        elif obs.type == "r2" and (obs.value < 0 or obs.value > 1):
            finding = RiskFinding(pdf_name, obs.page_number, "invalid_r2_range", "high", "R² must be between 0 and 1", f"发现 R² 表达 {obs.raw} 超出 0-1 范围。", "请复核模型拟合指标及排版转换是否正确。", context=obs.context)
        elif obs.type == "correlation" and (obs.value < -1 or obs.value > 1):
            finding = RiskFinding(pdf_name, obs.page_number, "invalid_correlation_range", "high", "correlation r must be between -1 and 1", f"发现相关系数 {obs.raw} 超出 -1 到 1 范围。", "请复核相关分析结果及数值录入。", context=obs.context)
        elif obs.type == "mean_sd" and obs.secondary_value is not None and obs.secondary_value < 0:
            finding = RiskFinding(pdf_name, obs.page_number, "negative_standard_deviation", "high", "standard deviation cannot be negative", f"发现均值±标准差表达 {obs.raw} 中 SD 为负。", "请复核均值±标准差格式及数据来源。", context=obs.context)
        if finding:
            findings.append(finding)
    return findings


def check_sum_lines(pdf_name: str, text: str, page_number: int, tolerance_ratio: float = 0.05) -> list[RiskFinding]:
    """Simple text-line sum/total consistency check for MVP."""
    findings: list[RiskFinding] = []
    for line in text.splitlines():
        if not re.search(r"总计|合计|Total|Sum", line, flags=re.I):
            continue
        values = [_to_float(m.group(0)) for m in re.finditer(NUM, line)]
        if len(values) < 3:
            continue
        parts, total = values[:-1], values[-1]
        expected = sum(parts)
        tolerance = max(1e-9, abs(total) * tolerance_ratio)
        if math.fabs(expected - total) > tolerance:
            risk = "high" if math.fabs(expected - total) > abs(total) * 0.05 else "low"
            findings.append(RiskFinding(pdf_name, page_number, "sum_total_mismatch", risk, "total should equal sum of preceding values within 5% tolerance", f"疑似合计不一致：分项和={expected:g}，标注合计={total:g}。", "请人工复核该行是否为真正表格合计，以及是否存在 PDF 文本抽取错位。", context=line.strip()))
    return findings


def run_data_checks(pdf_name: str, pages: list[PageData]) -> tuple[list[NumberObservation], list[RiskFinding]]:
    """Run MVP numeric extraction and range checks."""
    nums = extract_numbers(pages)
    findings = check_invalid_ranges(pdf_name, nums)
    for page in pages:
        findings.extend(check_sum_lines(pdf_name, page_combined_text(page), page.page_number))
    return nums, findings

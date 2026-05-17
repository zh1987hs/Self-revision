"""HTML and JSON report generation."""
from __future__ import annotations

import html
from collections import Counter
from pathlib import Path

from .models import AuditResult, RiskFinding
from .utils import ensure_dir, write_json


def _rel(path: str | None, base: Path) -> str:
    if not path:
        return ""
    try:
        return Path(path).resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return Path(path).as_posix()


def _risk_counts(findings: list[RiskFinding]) -> Counter[str]:
    return Counter(f.risk_level for f in findings)


def generate_reports(result: AuditResult, out_dir: str | Path) -> tuple[str, str]:
    """Write JSON and HTML reports for an audit result."""
    out = ensure_dir(out_dir)
    json_path = out / f"{Path(result.pdf_name).stem}_audit.json"
    html_path = out / f"{Path(result.pdf_name).stem}_audit.html"
    write_json(json_path, result.to_dict())
    counts = _risk_counts(result.findings)

    rows = []
    for f in result.findings:
        img = f"<a href='{html.escape(_rel(f.preview_path, out))}'><img src='{html.escape(_rel(f.preview_path, out))}' class='thumb'></a>" if f.preview_path else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(f.pdf_name)}</td><td>{f.page_number}</td>"
            f"<td>{html.escape(f.issue_type)}</td><td class='risk {html.escape(f.risk_level)}'>{html.escape(f.risk_level)}</td>"
            f"<td>{html.escape(f.trigger_rule)}</td><td>{html.escape(f.evidence_summary)}</td>"
            f"<td>{html.escape(f.review_suggestion)}</td><td>{html.escape(f.context or '')}</td><td>{img}</td>"
            "</tr>"
        )

    image_rows = []
    for img in result.images:
        rel = _rel(img.file_path, out)
        image_rows.append(
            "<tr>"
            f"<td>{html.escape(img.image_id)}</td><td>{img.page_number}</td><td>{img.xref}</td>"
            f"<td>{img.width}×{img.height}</td><td>{html.escape(img.file_hash[:16])}</td>"
            f"<td><a href='{html.escape(rel)}'><img src='{html.escape(rel)}' class='thumb'></a></td>"
            "</tr>"
        )

    figure_rows = [f"<tr><td>{html.escape(c.figure_id)}</td><td>{c.page_number}</td><td>{html.escape(c.caption)}</td><td>{html.escape(', '.join(c.nearby_images))}</td><td>{c.confidence:.2f}</td></tr>" for c in result.figures]
    table_rows = [f"<tr><td>{html.escape(c.figure_id)}</td><td>{c.page_number}</td><td>{html.escape(c.caption)}</td><td>{c.confidence:.2f}</td></tr>" for c in result.tables]
    ocr_rows = []
    for page in result.pages:
        if page.ocr_text:
            snippet = page.ocr_text[:500] + ("..." if len(page.ocr_text) > 500 else "")
            ocr_rows.append(f"<tr><td>页面截图</td><td>{page.page_number}</td><td>{html.escape(snippet)}</td></tr>")
        for image in page.images:
            if image.ocr_text:
                snippet = image.ocr_text[:500] + ("..." if len(image.ocr_text) > 500 else "")
                ocr_rows.append(f"<tr><td>{html.escape(image.image_id)}</td><td>{image.page_number}</td><td>{html.escape(snippet)}</td></tr>")

    doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Thesis Audit Report - {html.escape(result.pdf_name)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #1f2937; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
th, td {{ border: 1px solid #d1d5db; padding: 8px; vertical-align: top; font-size: 14px; }}
th {{ background: #f3f4f6; }} .thumb {{ max-width: 180px; max-height: 120px; }}
.risk.high {{ color: #b91c1c; font-weight: 700; }} .risk.medium {{ color: #b45309; font-weight: 700; }} .risk.low {{ color: #0369a1; }}
.notice {{ background: #fffbeb; border: 1px solid #f59e0b; padding: 12px; }}
</style></head><body>
<h1>学位论文 PDF 学术规范自检报告（MVP）</h1>
<p class="notice">本工具仅用于自动化初筛，报告中的“疑似”“可能存在异常”“需复核”等提示不能替代人工学术判断，也不构成学术不端结论。</p>
<h2>总览</h2>
<ul>
<li>文件名：{html.escape(result.pdf_name)}</li><li>页数：{result.page_count}</li><li>提取图片数量：{len(result.images)}</li><li>提取表格数量：{result.extracted_table_count}</li>
<li>风险问题总数：{len(result.findings)}（high: {counts.get('high',0)} / medium: {counts.get('medium',0)} / low: {counts.get('low',0)}）</li>
<li>OCR：{'已启用' if result.ocr_enabled else '未启用'}；可用性：{'可用' if result.ocr_available else '不可用/未运行'}；语言：{html.escape(result.ocr_language or '')}；页面截图 OCR 命中：{result.ocr_page_images_processed}；内嵌图片 OCR 命中：{result.ocr_embedded_images_processed}</li>
<li>OCR 状态：{html.escape(result.ocr_message)}</li>
<li>JSON 文件：{html.escape(json_path.name)}</li>
</ul>
<h2>风险提示</h2>
<table><thead><tr><th>PDF</th><th>页码</th><th>问题类型</th><th>风险</th><th>触发规则</th><th>证据摘要</th><th>复核建议</th><th>上下文</th><th>预览</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="9">未发现第一阶段规则覆盖的明显风险。</td></tr>'}</tbody></table>
<h2>OCR 文本摘录</h2><table><thead><tr><th>来源</th><th>页码</th><th>OCR 文本摘录</th></tr></thead><tbody>{''.join(ocr_rows) or '<tr><td colspan="3">无 OCR 文本或未启用 OCR。</td></tr>'}</tbody></table>
<h2>附录：图题列表</h2><table><thead><tr><th>ID</th><th>页码</th><th>题注</th><th>候选图片</th><th>置信度</th></tr></thead><tbody>{''.join(figure_rows) or '<tr><td colspan="5">无</td></tr>'}</tbody></table>
<h2>附录：表题列表</h2><table><thead><tr><th>ID</th><th>页码</th><th>题注</th><th>置信度</th></tr></thead><tbody>{''.join(table_rows) or '<tr><td colspan="4">无</td></tr>'}</tbody></table>
<h2>附录：图片清单</h2><table><thead><tr><th>ID</th><th>页码</th><th>xref</th><th>尺寸</th><th>SHA256</th><th>预览</th></tr></thead><tbody>{''.join(image_rows) or '<tr><td colspan="6">无</td></tr>'}</tbody></table>
</body></html>"""
    html_path.write_text(doc, encoding="utf-8")
    return html_path.as_posix(), json_path.as_posix()

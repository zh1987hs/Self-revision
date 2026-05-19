#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
硕士论文数据硬伤初筛工具
- 批量读取 PDF
- 提取正文、图题、表题、表格、图片
- 一致性规则初筛
- 图像相似度检测（重复/裁剪/旋转/镜像）
- 调用 GPT 生成初筛报告
- 输出 Excel 汇总 + 每篇 Markdown 报告
"""

import argparse
import base64
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import fitz  # pymupdf
import imagehash
import numpy as np
import pandas as pd
import pdfplumber
from PIL import Image
from skimage.metrics import structural_similarity as ssim


@dataclass
class Finding:
    file_name: str
    risk_level: str
    issue_type: str
    page: str
    fig_or_table_no: str
    description: str
    gpt_reason: str
    suggest_materials: str


class ThesisScreenTool:
    def __init__(self, input_dir: Path, output_dir: Path, model: str = "gpt-4.1-mini"):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.model = model
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "images").mkdir(exist_ok=True)
        (self.output_dir / "reports").mkdir(exist_ok=True)

    def run(self):
        all_findings: List[Finding] = []
        pdfs = sorted(self.input_dir.glob("*.pdf"))
        if not pdfs:
            print(f"未找到 PDF 文件：{self.input_dir}")
            return

        for pdf_path in pdfs:
            print(f"处理中: {pdf_path.name}")
            paper = self.extract_paper_data(pdf_path)
            local_findings = self.rule_check(paper)
            image_findings = self.detect_image_similarity(paper)
            local_findings.extend(image_findings)

            gpt_findings = self.call_gpt_for_report(paper, local_findings)
            final_findings = gpt_findings if gpt_findings else local_findings
            all_findings.extend(final_findings)

            self.write_markdown_report(pdf_path.stem, paper, final_findings)

        self.write_excel_summary(all_findings)
        print("完成。")

    def extract_paper_data(self, pdf_path: Path) -> Dict:
        text_pages, captions, table_captions, table_rows, images = [], [], [], [], []

        with fitz.open(pdf_path) as doc:
            for page_idx, page in enumerate(doc, start=1):
                txt = page.get_text("text")
                text_pages.append({"page": page_idx, "text": txt})

                for m in re.finditer(r"(图\s*\d+[\.-]?\d*[^\n]*)", txt):
                    captions.append({"page": page_idx, "caption": m.group(1).strip()})
                for m in re.finditer(r"(表\s*\d+[\.-]?\d*[^\n]*)", txt):
                    table_captions.append({"page": page_idx, "caption": m.group(1).strip()})

                for img_idx, img in enumerate(page.get_images(full=True), start=1):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    ext = base_image.get("ext", "png")
                    img_name = f"{pdf_path.stem}_p{page_idx}_{img_idx}.{ext}"
                    img_path = self.output_dir / "images" / img_name
                    with open(img_path, "wb") as f:
                        f.write(image_bytes)
                    images.append({"page": page_idx, "name": img_name, "path": str(img_path)})

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_idx, p in enumerate(pdf.pages, start=1):
                tables = p.extract_tables() or []
                for t_idx, t in enumerate(tables, start=1):
                    for r in t:
                        table_rows.append({"page": page_idx, "table_index": t_idx, "row": r})

        return {
            "file_name": pdf_path.name,
            "text_pages": text_pages,
            "figure_captions": captions,
            "table_captions": table_captions,
            "tables": table_rows,
            "images": images,
        }

    def rule_check(self, paper: Dict) -> List[Finding]:
        findings: List[Finding] = []
        num_unit_pat = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|g|kg|mL|L|%|μL|℃|°C|h|d)")
        sample_pat = re.compile(r"(?:n|N)\s*=\s*(\d+)")

        all_nums = []
        sample_ns = []
        for p in paper["text_pages"]:
            page = p["page"]
            text = p["text"]
            all_nums.extend([(page, m.group(0)) for m in num_unit_pat.finditer(text)])
            sample_ns.extend([(page, int(m.group(1))) for m in sample_pat.finditer(text)])

        # 样本量前后不一致
        distinct_n = sorted(set(v for _, v in sample_ns))
        if len(distinct_n) > 1:
            findings.append(Finding(
                file_name=paper["file_name"], risk_level="中", issue_type="样本量不一致", page=",".join(map(str, sorted(set(p for p, _ in sample_ns)))),
                fig_or_table_no="-", description=f"检测到多个样本量 n 值: {distinct_n}",
                gpt_reason="规则检测发现全文出现多个样本量定义，可能存在口径不一致。",
                suggest_materials="方法学章节、纳排标准、流程图、原始病例筛选表"
            ))

        # 图表编号连续性
        fig_nums = self._extract_caption_nums(paper["figure_captions"], prefix="图")
        tbl_nums = self._extract_caption_nums(paper["table_captions"], prefix="表")
        for typ, nums in [("图", fig_nums), ("表", tbl_nums)]:
            miss = self._find_missing(nums)
            if miss:
                findings.append(Finding(
                    file_name=paper["file_name"], risk_level="低", issue_type=f"{typ}编号疑似跳号", page="-",
                    fig_or_table_no=f"缺失: {miss}", description=f"{typ}编号序列中疑似缺失: {miss}",
                    gpt_reason="编号序列未保持连续，可能为排版遗漏或引用错误。",
                    suggest_materials=f"全文{typ}题、交叉引用列表"
                ))

        return findings

    def detect_image_similarity(self, paper: Dict) -> List[Finding]:
        findings: List[Finding] = []
        imgs = paper["images"]
        if len(imgs) < 2:
            return findings

        prepared = []
        for im in imgs:
            arr = cv2.imread(im["path"], cv2.IMREAD_GRAYSCALE)
            if arr is None:
                continue
            arr = cv2.resize(arr, (512, 512))
            pil = Image.fromarray(arr)
            prepared.append((im, arr, imagehash.phash(pil)))

        for i in range(len(prepared)):
            for j in range(i + 1, len(prepared)):
                a_meta, a_img, a_hash = prepared[i]
                b_meta, b_img, b_hash = prepared[j]
                dist = a_hash - b_hash

                # 直接重复
                if dist <= 4:
                    findings.append(self._img_finding(paper["file_name"], "高", "疑似重复图片", a_meta, b_meta, f"pHash 距离={dist}"))
                    continue

                # 旋转/镜像
                b_transforms = [
                    cv2.rotate(b_img, cv2.ROTATE_90_CLOCKWISE),
                    cv2.rotate(b_img, cv2.ROTATE_180),
                    cv2.rotate(b_img, cv2.ROTATE_90_COUNTERCLOCKWISE),
                    cv2.flip(b_img, 1),
                    cv2.flip(b_img, 0),
                ]
                if any((imagehash.phash(Image.fromarray(t)) - a_hash) <= 6 for t in b_transforms):
                    findings.append(self._img_finding(paper["file_name"], "高", "疑似旋转/镜像重复", a_meta, b_meta, "变换后 hash 相近"))
                    continue

                # 裁剪重复（用 SSIM 近似）
                crop = b_img[96:416, 96:416]
                crop = cv2.resize(crop, (512, 512))
                score = ssim(a_img, crop)
                if score > 0.85:
                    findings.append(self._img_finding(paper["file_name"], "中", "疑似裁剪重复", a_meta, b_meta, f"SSIM={score:.3f}"))

        return findings

    def call_gpt_for_report(self, paper: Dict, local_findings: List[Finding]) -> List[Finding]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return local_findings

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            summary = {
                "file_name": paper["file_name"],
                "figure_captions": paper["figure_captions"][:30],
                "table_captions": paper["table_captions"][:30],
                "rule_findings": [asdict(f) for f in local_findings],
            }
            prompt = (
                "你是科研数据一致性初筛助手。仅做风险提示，不做学术不端定性。"
                "请输出 JSON 数组，每项字段："
                "file_name,risk_level,issue_type,page,fig_or_table_no,description,gpt_reason,suggest_materials。"
            )
            resp = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(summary, ensure_ascii=False)},
                ],
                temperature=0.2,
            )
            text = resp.output_text
            data = json.loads(text)
            out = []
            for x in data:
                out.append(Finding(**x))
            return out if out else local_findings
        except Exception as e:
            print(f"GPT 调用失败，改用规则结果: {e}")
            return local_findings

    def write_markdown_report(self, stem: str, paper: Dict, findings: List[Finding]):
        md_path = self.output_dir / "reports" / f"{stem}_初筛报告.md"
        lines = [
            f"# {paper['file_name']} 数据硬伤初筛报告",
            "",
            "## 说明",
            "- 本报告仅用于初筛风险提示，不构成学术不端结论。",
            "",
            "## 提取概览",
            f"- 正文页数：{len(paper['text_pages'])}",
            f"- 图题数：{len(paper['figure_captions'])}",
            f"- 表题数：{len(paper['table_captions'])}",
            f"- 提取图片数：{len(paper['images'])}",
            f"- 表格行数：{len(paper['tables'])}",
            "",
            "## 疑点清单",
        ]
        if findings:
            for i, f in enumerate(findings, start=1):
                lines += [
                    f"### {i}. {f.issue_type}（风险：{f.risk_level}）",
                    f"- 页码：{f.page}",
                    f"- 图号/表号：{f.fig_or_table_no}",
                    f"- 疑点描述：{f.description}",
                    f"- GPT 判断理由：{f.gpt_reason}",
                    f"- 建议人工复核材料：{f.suggest_materials}",
                    "",
                ]
        else:
            lines.append("- 未检出明显风险点（仍建议人工复核）。")

        md_path.write_text("\n".join(lines), encoding="utf-8")

    def write_excel_summary(self, findings: List[Finding]):
        rows = [asdict(f) for f in findings]
        df = pd.DataFrame(rows, columns=[
            "file_name", "risk_level", "issue_type", "page", "fig_or_table_no",
            "description", "gpt_reason", "suggest_materials"
        ])
        out = self.output_dir / "初筛汇总.xlsx"
        df.to_excel(out, index=False)

    @staticmethod
    def _extract_caption_nums(caps: List[Dict], prefix: str) -> List[int]:
        nums = []
        for c in caps:
            m = re.search(rf"{prefix}\s*(\d+)", c["caption"])
            if m:
                nums.append(int(m.group(1)))
        return sorted(set(nums))

    @staticmethod
    def _find_missing(nums: List[int]) -> List[int]:
        if not nums:
            return []
        full = set(range(min(nums), max(nums) + 1))
        return sorted(list(full - set(nums)))

    @staticmethod
    def _img_finding(file_name, risk, typ, a_meta, b_meta, detail):
        return Finding(
            file_name=file_name,
            risk_level=risk,
            issue_type=typ,
            page=f"{a_meta['page']},{b_meta['page']}",
            fig_or_table_no=f"{a_meta['name']} vs {b_meta['name']}",
            description=f"疑似重复图像：{detail}",
            gpt_reason="图像相似度算法检测到高相似模式。",
            suggest_materials="原始实验图片、拍摄时间戳、图像处理流程"
        )


def main():
    parser = argparse.ArgumentParser(description="硕士论文数据硬伤初筛工具")
    parser.add_argument("--input", required=True, help="PDF 文件夹路径")
    parser.add_argument("--output", default="output", help="输出目录")
    parser.add_argument("--model", default="gpt-4.1-mini", help="OpenAI 模型")
    args = parser.parse_args()

    tool = ThesisScreenTool(Path(args.input), Path(args.output), model=args.model)
    tool.run()


if __name__ == "__main__":
    main()

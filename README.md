# 学位论文 PDF 学术规范自检系统 MVP

这是一个 Python 3.10+ 的最小可运行原型，用于对学位论文 PDF 做自动化初筛。它不会判定学术不端，只生成“疑似 / 可能存在异常 / 需复核”的风险提示，帮助人工复核者优先定位可能的数据硬伤、图片重复和统计表达问题。

## MVP 已实现范围

第一阶段能力：

- 使用 PyMuPDF 提取 PDF 页面文本、页面尺寸和内嵌图片。
- 保存内嵌图片及其 `image_id`、页码、xref、尺寸、格式、SHA256 hash、感知 hash 等信息。
- 检测图片：
  - `exact_duplicate`：文件字节 hash 完全一致。
  - `reused_pdf_image_object`：PDF 同一 xref 多处引用。
  - `visually_similar`：感知 hash 汉明距离低于阈值。
  - `possible_partial_duplicate`：简单 tile 局部 hash 高度相似。
- 对小尺寸、极端宽高比、频繁小图和含 logo/校徽/二维码等上下文的图片进行降噪或降级。
- 抽取百分比、p 值、R²、相关系数、均值 ± 标准差、科学计数法和普通数字。
- 检测 p 值、R²、相关系数、百分比、负标准差等范围异常。
- 生成 HTML 报告和 JSON 结构化结果。
- 提供基础图题/表题识别和保守的表格文本行抽取，作为后续扩展接口。

## 安装

建议使用虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

如需启用 OCR，还需要额外安装系统级 Tesseract OCR，并确保 `tesseract` 命令在 PATH 中。当前版本会对页面截图和内嵌图片执行 OCR：页面截图 OCR 可辅助扫描版 PDF 的正文数字检查，内嵌图片 OCR 会写入 JSON/HTML 报告并用于图片上下文降噪。若缺少 pytesseract 或 tesseract 可执行程序，程序会给出友好 warning 并继续执行非 OCR 流程。

## 使用方法

单个 PDF：

```bash
python thesis_audit.py input.pdf --out reports/
```

启用 OCR 识别页面截图和内嵌图片：

```bash
python thesis_audit.py input.pdf --out reports/ --ocr --ocr-lang chi_sim+eng
```

调整图片相似阈值：

```bash
python thesis_audit.py input.pdf --out reports/ --image-threshold 8 --min-image-size 80
```

处理文件夹：

```bash
python thesis_audit.py folder_with_pdfs/ --out reports/ --recursive
```

保存页面截图：

```bash
python thesis_audit.py input.pdf --out reports/ --save-page-images
```

输出目录中通常包含：

- `*_audit.html`：人工可读报告。
- `*_audit.json`：结构化结果，包含页面/图片 OCR 文本字段与 OCR 运行摘要。
- `assets/`：提取出的图片和页面截图。
- `previews/`：图片重复对比预览。

## 最小可运行示例

```bash
pip install -r requirements.txt
python examples/create_sample_pdf.py
python thesis_audit.py examples/sample_thesis.pdf --out ./reports --debug
```

然后打开 `reports/sample_thesis_audit.html` 查看结果。示例 PDF 中包含越界 p 值、越界 R² 和一个疑似合计不一致的文本行，用于验证报告链路。

## 报告字段说明

每条风险提示都会包含：

- PDF 文件名
- 页码
- 问题类型
- 风险等级：`high` / `medium` / `low`
- 触发规则
- 证据摘要
- 人工复核建议
- 截图或图片预览路径（如适用）

## 局限性

- PDF 文本和图片抽取质量取决于 PDF 内部结构；扫描版 PDF 需要安装并启用 OCR 才能从页面截图中提取正文。
- 图片重复检测会尽量过滤 logo、页眉页脚、二维码等装饰元素，但仍可能有误报或漏报。
- 数值和统计检查是规则式初筛，不理解完整实验设计、学科语境或统计模型。
- 表格抽取和正文-表格一致性目前是保守 MVP，复杂表格需后续接入更强解析器。
- 本工具只能作为初筛和人工复核辅助，不能替代导师、评审专家或学术委员会的人工判断。

## 后续扩展建议

1. 将 OCR 文本接入图片分类、坐标轴标签和图中文字识别。
2. 使用 Camelot、Tabula 或 pdfplumber 增强表格结构化抽取。
3. 将图题/表题与图片 bbox、文本块位置进行空间关联。
4. 增加正文“最高/最低/显著高于”等声明与附近表格数据的对照。
5. 增加更稳健的局部重复检测（SIFT/ORB 特征、滑窗匹配、显微图专用检测）。
6. 增加项目级汇总报告，支持批量论文横向对比和风险筛选。

## 开发与测试

```bash
pytest
```

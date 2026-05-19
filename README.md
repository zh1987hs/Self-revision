# 硕士论文数据硬伤初筛工具（Python）

> 仅做初筛，不做学术不端定性。

## 功能
- 批量读取一个文件夹中的多篇 PDF 学位论文
- 提取正文文本、图题、表题、表格内容、图片
- 按论文输出结构化 Markdown 报告
- 检查同一论文内部的：样本量、图表编号等一致性问题（可扩展）
- 图片相似度检测：疑似重复、旋转/镜像重复、疑似裁剪重复
- 可选调用 GPT API 生成/增强“数据硬伤初筛报告”
- 输出 Excel 汇总表 + 每篇论文 Markdown 报告

## Windows 安装
1. 安装 Python 3.10+（建议 3.11）
2. 打开 PowerShell，进入项目目录
3. 建议创建虚拟环境：
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
4. 安装依赖：
   ```powershell
   pip install -r requirements.txt
   ```

## 运行
```powershell
python thesis_screening_tool.py --input "D:\thesis_pdfs" --output "D:\thesis_output"
```

若需要 GPT 分析：
```powershell
$env:OPENAI_API_KEY="你的key"
python thesis_screening_tool.py --input "D:\thesis_pdfs" --output "D:\thesis_output" --model "gpt-4.1-mini"
```

## 输出结构
- `output/images/`：提取的图片
- `output/reports/*.md`：每篇论文的初筛报告
- `output/初筛汇总.xlsx`：汇总表

## 报告字段
- 论文文件名（file_name）
- 风险等级（risk_level）
- 疑点类型（issue_type）
- 页码（page）
- 图号/表号（fig_or_table_no）
- 疑点描述（description）
- GPT 判断理由（gpt_reason）
- 建议人工复核材料（suggest_materials）

## 说明
- 当前规则是“可运行的第一版”，可继续按你的学科模板扩展：
  - 数值口径不一致（均值/标准差、P 值、CI 区间）
  - 单位前后冲突（mg 与 g 混用）
  - 时间点冲突（基线/随访）
  - 组别命名不一致（对照组/实验组/干预组）
  - 图表互相引用冲突（文中说图3，实际是图4）
- `python-docx` 已加入依赖，后续可把 Markdown 自动转 Word。

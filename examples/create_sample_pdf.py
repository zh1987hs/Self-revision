"""Create a tiny sample PDF for manual MVP smoke testing.

Run after installing requirements:
    python examples/create_sample_pdf.py
    python thesis_audit.py examples/sample_thesis.pdf --out reports/ --debug
"""
from __future__ import annotations

from pathlib import Path

import fitz

OUT = Path(__file__).with_name("sample_thesis.pdf")

def main() -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Figure 1 Sample results")
    page.insert_text((72, 110), "The reported p = 1.2 and R²=1.5 should be flagged for review.")
    page.insert_text((72, 145), "Total row example: A B Total 10 20 40")
    doc.save(OUT.as_posix())
    print(f"created {OUT}")

if __name__ == "__main__":
    main()

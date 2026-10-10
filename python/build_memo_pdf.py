"""Render docs/experiment_decision_memo.md to a PDF with Playwright (Chromium).  Usage: python python/build_memo_pdf.py"""
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "docs" / "experiment_decision_memo.md"
html_path = ROOT / "docs" / "_memo_render.html"
pdf_path = ROOT / "docs" / "experiment_decision_memo.pdf"

body = markdown.markdown(src.read_text(encoding="utf8"), extensions=["tables", "sane_lists"])
css = """
@page { size: Letter; margin: 0.6in 0.7in; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; line-height: 1.4; color: #1F2937; }
h1 { font-size: 20pt; margin: 0 0 10px; color: #1D4E89; }
h2 { break-after: avoid; page-break-after: avoid; font-size: 13pt; margin: 16px 0 6px; color: #1F2937; border-bottom: 1px solid #E5E7EB; padding-bottom: 3px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9pt; page-break-inside: avoid; }
th { background: #F3F6FA; text-align: left; border-bottom: 1.5px solid #1D4E89; padding: 5px 7px; }
td { border-bottom: 1px solid #E5E7EB; padding: 5px 7px; vertical-align: top; }
a { color: #1D4E89; text-decoration: none; }
strong { color: #111827; }
"""
html_path.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>", encoding="utf8")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(html_path.as_uri())
    page.pdf(path=str(pdf_path), format="Letter", print_background=True)
    browser.close()
html_path.unlink()
print("wrote", pdf_path)

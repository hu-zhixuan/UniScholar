"""
生成【文件三：作品简介与团队介绍】正式 PDF 与 Word 文档
"""
import os
import sys
import subprocess
from pathlib import Path
from markdown_it import MarkdownIt
import pypandoc

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
PKG_DIR = BASE_DIR / "submission_package"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def build_document_three():
    print("[1/2] 正在生成【文件三：作品简介与团队介绍】Word 与 PDF...")
    src_copy = DOCS_DIR / "platform_submission_copy.md"
    md_text = src_copy.read_text(encoding="utf-8")
    
    dir_copy = PKG_DIR / "01_平台网页直接填报文案"
    dir_copy.mkdir(parents=True, exist_ok=True)
    
    # 1. 生成 Word docx
    docx_path = dir_copy / "UniScholar_作品简介与团队介绍.docx"
    pypandoc.convert_text(md_text, 'docx', format='md', outputfile=str(docx_path))
    print(f"  ✓ Word 版本已生成: {docx_path.name} ({docx_path.stat().st_size // 1024} KB)")
    
    # 2. 生成 PDF
    md = MarkdownIt('commonmark').enable('table').enable('strikethrough')
    body_html = md.render(md_text)
    
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>UniScholar · 作品简介与团队介绍申报书</title>
<style>
@page {{
  size: A4;
  margin: 22mm 20mm;
  @bottom-center {{
    content: counter(page);
    font-size: 9pt;
    color: #64748B;
  }}
}}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #1E293B;
  line-height: 1.7;
  font-size: 11pt;
  margin: 0;
}}
.doc-header {{
  border-bottom: 3px solid #E60012;
  padding-bottom: 15px;
  margin-bottom: 25px;
}}
.tag {{
  color: #E60012;
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 1px;
}}
.title {{
  font-size: 22pt;
  font-weight: 800;
  color: #0F172A;
  margin: 8px 0;
}}
.sub {{
  font-size: 12pt;
  color: #2563EB;
  font-weight: 600;
}}
h2 {{
  font-size: 14pt;
  color: #1E3A8A;
  border-left: 4px solid #2563EB;
  padding-left: 10px;
  margin-top: 25px;
  margin-bottom: 12px;
}}
h3 {{
  font-size: 12pt;
  color: #0F172A;
  margin-top: 18px;
  margin-bottom: 8px;
}}
p {{
  margin: 0 0 10px 0;
  text-align: justify;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 10pt;
}}
th {{
  background: #F1F5F9;
  color: #0F172A;
  font-weight: 700;
  text-align: left;
  padding: 10px 14px;
  border: 1px solid #CBD5E1;
}}
td {{
  padding: 10px 14px;
  border: 1px solid #E2E8F0;
}}
tr:nth-child(even) {{
  background-color: #F8FAFC;
}}
blockquote {{
  margin: 12px 0;
  padding: 10px 16px;
  background: #F8FAFC;
  border-left: 4px solid #2563EB;
  color: #334155;
}}
</style>
</head>
<body>
<div class="doc-header">
  <div class="tag">中国国际大学生创新大赛 · 产业命题赛道 · 产教协同创新组</div>
  <div class="title">UniScholar (联智学者) · 作品简介与团队介绍</div>
  <div class="sub">命题企业：中国联合网络通信有限公司浙江省分公司 | 申报院校：长沙师范学院 经济管理学院</div>
</div>
{body_html}
</body>
</html>"""
    
    temp_html = dir_copy / "temp_profile.html"
    temp_html.write_text(html_doc, encoding="utf-8")
    pdf_path = dir_copy / "UniScholar_作品简介与团队介绍.pdf"
    
    cmd = [
        EDGE_PATH,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={str(pdf_path)}",
        temp_html.as_uri()
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if temp_html.exists():
        temp_html.unlink()
        
    print(f"  ✓ PDF 版本已生成: {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    build_document_three()

"""
UniScholar 参赛提交物全自动生成与同步引擎 (v2.5.0)
【极简科技白底高冲击版 · 深度结构化优化】
生成并直接同步至:
1. FAST/UniScholar/submission_package/
2. FAST/大创赛提交材料_直接交这三个文件/
"""

import os
import sys
import subprocess
import shutil
import zipfile
from pathlib import Path
from markdown_it import MarkdownIt

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
DIST_DIR = BASE_DIR / "submission_package"
FAST_DIR = BASE_DIR.parent
TOP_TARGET_DIR = FAST_DIR / "大创赛提交材料_直接交这三个文件"

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_PATH):
    EDGE_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def run_headless_print(html_path: Path, pdf_path: Path):
    """使用 Edge / Chrome 无头模式生成高保真 PDF"""
    cmd = [
        EDGE_PATH,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={str(pdf_path)}",
        html_path.as_uri()
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore')
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"PDF 生成失败: {res.stderr}")

def generate_technical_proposal_files():
    print("\n=======================================================")
    print("[1/3] 正在生成【核心附件一：技术方案与研发报告】(PDF + Word)...")
    md_file = DOCS_DIR / "technical_proposal.md"
    out_dir = DIST_DIR / "02_核心附件一_技术方案与研发报告"
    # 0. 同步图片目录
    img_src = DOCS_DIR / "images"
    img_dst = out_dir / "images"
    if img_src.exists():
        if img_dst.exists():
            shutil.rmtree(img_dst)
        shutil.copytree(img_src, img_dst)
        
    # 1. 复制 md
    shutil.copy(md_file, out_dir / "UniScholar_技术方案与研发报告.md")
    
    # 2. 生成 docx (Word)
    docx_path = out_dir / "UniScholar_技术方案与研发报告.docx"
    try:
        import pypandoc
        pypandoc.convert_file(str(md_file), 'docx', outputfile=str(docx_path))
        print(f"  ✓ Word 文档已生成: {docx_path.name} ({docx_path.stat().st_size // 1024} KB)")
    except Exception as e:
        print(f"  ! Word 转换警告: {e}")

    # 3. 渲染为排版精美的 HTML 并导出为 PDF
    md_content = md_file.read_text(encoding="utf-8")
    
    # 剥离前置封面标题及元数据，由 HTML 模板第一页专门独立渲染封面，第二页直接从摘要开始
    summary_pos = md_content.find("## 摘要 (Executive Summary)")
    if summary_pos != -1:
        pdf_md = md_content[summary_pos:]
    else:
        pdf_md = md_content
        
    md = MarkdownIt('commonmark', {'html': True}).enable('table').enable('strikethrough')
    body_html = md.render(pdf_md)
    
    # 注入专业红头学术及企业工程报告 CSS 样式
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<base href="{DOCS_DIR.as_uri()}/">
<title>UniScholar 联智学者 · 技术方案文档与研发报告</title>
<style>
@page {{
  size: A4;
  margin: 22mm 18mm 22mm 18mm;
  @bottom-center {{
    content: counter(page);
    font-size: 9pt;
    color: #64748B;
  }}
}}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  color: #1E293B;
  line-height: 1.68;
  font-size: 10.5pt;
  margin: 0;
  padding: 0;
}}
/* 封面排版 */
.cover-page {{
  page-break-after: always;
  height: 920px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-top: 6px solid #E60012;
  padding-top: 30px;
}}
.cover-header {{
  border-left: 4px solid #1E3A8A;
  padding-left: 14px;
}}
.cover-tag {{
  color: #E60012;
  font-weight: 800;
  font-size: 12pt;
  letter-spacing: 1.5px;
}}
.cover-subtag {{
  color: #475569;
  font-size: 10.5pt;
  margin-top: 4px;
}}
.cover-main {{
  margin-top: 35px;
}}
.cover-title {{
  font-size: 26pt;
  font-weight: 800;
  color: #0F172A;
  line-height: 1.25;
  margin-bottom: 12px;
}}
.cover-subtitle {{
  font-size: 13.5pt;
  color: #2563EB;
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: 22px;
}}
.cover-badge {{
  display: inline-block;
  background: #EFF6FF;
  color: #1D4ED8;
  border: 1px solid #BFDBFE;
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 10.5pt;
  font-weight: 600;
}}
.cover-meta-table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 35px;
  background: #F8FAFC;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #CBD5E1;
}}
.cover-meta-table td {{
  padding: 9px 15px;
  font-size: 10pt;
  border-bottom: 1px solid #E2E8F0;
}}
.cover-meta-table td.label {{
  width: 28%;
  color: #475569;
  font-weight: 700;
  background: #F1F5F9;
}}
.cover-meta-table td.val {{
  color: #0F172A;
  font-weight: 500;
}}
.cover-footer {{
  font-size: 9pt;
  color: #94A3B8;
  text-align: center;
  border-top: 1px solid #E2E8F0;
  padding-top: 15px;
}}

/* 正文标题与段落 */
h1 {{
  font-size: 18pt;
  color: #0F172A;
  border-bottom: 2.5px solid #E60012;
  padding-bottom: 8px;
  margin-top: 36px;
  margin-bottom: 16px;
  page-break-before: always;
}}
h2 {{
  font-size: 13.5pt;
  color: #1E3A8A;
  border-left: 4px solid #2563EB;
  padding-left: 10px;
  margin-top: 24px;
  margin-bottom: 12px;
  page-break-after: avoid;
}}
h3 {{
  font-size: 11.5pt;
  color: #0F172A;
  margin-top: 18px;
  margin-bottom: 8px;
  page-break-after: avoid;
}}
p {{
  margin: 0 0 10px 0;
  text-align: justify;
}}
strong {{
  color: #0F172A;
}}
ul, ol {{
  margin: 6px 0 12px 20px;
  padding: 0;
}}
li {{
  margin-bottom: 4px;
}}
blockquote {{
  margin: 14px 0;
  padding: 12px 18px;
  background: #F8FAFC;
  border-left: 4px solid #2563EB;
  border-radius: 0 6px 6px 0;
  color: #334155;
  font-size: 10pt;
}}

/* 表格规范 */
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
  font-size: 9.5pt;
  page-break-inside: auto;
}}
tr {{
  page-break-inside: avoid;
}}
th {{
  background: #F1F5F9;
  color: #0F172A;
  font-weight: 700;
  text-align: left;
  padding: 8px 12px;
  border: 1px solid #CBD5E1;
  border-top: 2px solid #E60012;
}}
td {{
  padding: 8px 12px;
  border: 1px solid #E2E8F0;
  vertical-align: top;
}}
tr:nth-child(even) {{
  background-color: #F8FAFC;
}}

/* 代码块 */
pre {{
  background: #0F172A;
  color: #F8FAFC;
  padding: 14px 16px;
  border-radius: 6px;
  font-family: "JetBrains Mono", Consolas, Monaco, monospace;
  font-size: 8.5pt;
  line-height: 1.45;
  overflow-x: auto;
  page-break-inside: avoid;
  margin: 14px 0;
  border: 1px solid #334155;
}}
code {{
  font-family: "JetBrains Mono", Consolas, Monaco, monospace;
  background: #F1F5F9;
  color: #E60012;
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 9pt;
}}
pre code {{
  background: transparent;
  color: #F8FAFC;
  padding: 0;
}}
hr {{
  border: none;
  border-top: 1px solid #E2E8F0;
  margin: 24px 0;
}}

/* 自定义可视化组件与图表卡片样式 */
.no-print, .no-pdf {{
  display: none !important;
}}

.visual-card {{
  background: #F8FAFC;
  border: 1px solid #CBD5E1;
  border-left: 4px solid #1E3A8A;
  border-radius: 8px;
  padding: 16px 20px;
  margin: 18px 0;
  page-break-inside: avoid;
}}
.visual-title {{
  font-size: 11pt;
  font-weight: 700;
  color: #0F172A;
  margin-bottom: 12px;
}}

/* 统计进度条 */
.stat-bar-container {{
  margin: 10px 0;
}}
.stat-bar-label {{
  display: flex;
  justify-content: space-between;
  font-size: 9.5pt;
  margin-bottom: 4px;
}}
.stat-progress-bg {{
  background: #E2E8F0;
  border-radius: 12px;
  height: 20px;
  overflow: hidden;
  margin-bottom: 8px;
}}
.stat-progress-fill {{
  height: 100%;
  color: #FFFFFF;
  font-size: 8.5pt;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 10px;
  box-sizing: border-box;
}}
.red-fill {{
  background: linear-gradient(90deg, #F87171, #E60012);
}}
.blue-fill {{
  background: linear-gradient(90deg, #60A5FA, #2563EB);
}}
.stat-detail-list {{
  font-size: 9pt;
  color: #475569;
  line-height: 1.5;
  margin-top: 4px;
}}

/* 4层架构卡片 */
.architecture-deck {{
  margin: 18px 0;
  page-break-inside: avoid;
}}
.arch-card {{
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 4px;
  background: #FFFFFF;
}}
.arch-card.layer-app {{
  border-left: 5px solid #2563EB;
  background: #F8FAFC;
}}
.arch-card.layer-orch {{
  border-left: 5px solid #4F46E5;
  background: #F8FAFC;
}}
.arch-card.layer-agents {{
  border-left: 5px solid #059669;
  background: #F8FAFC;
}}
.arch-card.layer-infra {{
  border-left: 5px solid #E60012;
  background: #F8FAFC;
}}
.arch-tag {{
  font-weight: 700;
  font-size: 10.5pt;
  color: #0F172A;
  margin-bottom: 6px;
}}
.arch-body {{
  font-size: 9pt;
  color: #334155;
  line-height: 1.5;
}}
.arch-arrow {{
  text-align: center;
  font-size: 8.5pt;
  color: #64748B;
  font-weight: 600;
  margin: 4px 0;
}}

/* 状态机管线 Pipeline */
.pipeline-container {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 16px 0;
  padding: 14px;
  background: #F8FAFC;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  page-break-inside: avoid;
}}
.pipeline-step {{
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  background: #FFFFFF;
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  padding: 6px 10px;
  min-width: 85px;
  text-align: center;
}}
.pipeline-step.hitl-step {{
  border-color: #EF4444;
  background: #FEF2F2;
}}
.pipeline-step.success-step {{
  border-color: #10B981;
  background: #ECFDF5;
}}
.step-badge {{
  font-size: 8pt;
  font-weight: 700;
  color: #1E3A8A;
  margin-bottom: 2px;
}}
.step-badge.red {{
  color: #B91C1C;
}}
.step-badge.green {{
  color: #047857;
}}
.step-name {{
  font-size: 8.5pt;
  color: #1E293B;
  font-weight: 600;
}}
.p-arrow {{
  color: #94A3B8;
  font-weight: 800;
  font-size: 11pt;
}}

/* 人在回路漏斗 */
.funnel-container {{
  margin: 16px 0;
  page-break-inside: avoid;
}}
.funnel-stage {{
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  background: #FFFFFF;
  padding: 12px 16px;
}}
.funnel-header {{
  font-weight: 700;
  font-size: 10pt;
  color: #0F172A;
  margin-bottom: 6px;
}}
.funnel-arrow {{
  text-align: center;
  color: #64748B;
  font-size: 9pt;
  margin: 6px 0;
}}
.funnel-box.hitl-box {{
  background: #FEF2F2;
  border: 1px solid #FCA5A5;
  border-left: 4px solid #E60012;
  border-radius: 4px;
  padding: 10px 14px;
  font-size: 9pt;
  color: #7F1D1D;
  line-height: 1.5;
}}

/* 数学公式卡片 */
.formula-card {{
  background: #F8FAFC;
  border: 1px solid #CBD5E1;
  border-left: 4px solid #2563EB;
  border-radius: 8px;
  padding: 14px 18px;
  margin: 16px 0;
  page-break-inside: avoid;
}}
.formula-title {{
  font-weight: 700;
  font-size: 10.5pt;
  color: #1E3A8A;
  margin-bottom: 10px;
}}
.formula-math {{
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  padding: 12px 16px;
  font-family: "Cambria Math", "Georgia", "Times New Roman", serif;
  font-size: 11pt;
  text-align: center;
  color: #0F172A;
  font-weight: 600;
  margin-bottom: 10px;
  letter-spacing: 0.5px;
}}
.formula-notes {{
  font-size: 9pt;
  color: #475569;
  line-height: 1.55;
}}

/* 联通元景万悟对接 Deck */
.integration-deck {{
  display: flex;
  gap: 12px;
  margin: 16px 0;
  page-break-inside: avoid;
}}
.integ-card {{
  flex: 1;
  background: #FFFFFF;
  border: 1px solid #CBD5E1;
  border-top: 3px solid #E60012;
  border-radius: 6px;
  padding: 12px 14px;
}}
.integ-title {{
  font-weight: 700;
  font-size: 10pt;
  color: #0F172A;
  margin-bottom: 6px;
}}
.integ-body {{
  font-size: 8.5pt;
  color: #334155;
  line-height: 1.5;
}}

/* TokenRouter 网格 */
.router-grid {{
  display: flex;
  gap: 12px;
  margin: 16px 0;
  page-break-inside: avoid;
}}
.router-card {{
  flex: 1;
  background: #F8FAFC;
  border: 1px solid #CBD5E1;
  border-top: 3px solid #2563EB;
  border-radius: 6px;
  padding: 12px 14px;
}}
.router-header {{
  font-weight: 700;
  font-size: 9.5pt;
  color: #1E3A8A;
  margin-bottom: 6px;
}}
.router-body {{
  font-size: 8.5pt;
  color: #334155;
  line-height: 1.5;
}}

/* Citation Validator 校验流程 */
.validator-container {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 0;
  padding: 12px;
  background: #F8FAFC;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  page-break-inside: avoid;
}}
.val-col {{
  flex: 1;
}}
.val-box {{
  background: #FFFFFF;
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 8.5pt;
  line-height: 1.45;
  color: #1E293B;
}}
.val-col-arrow {{
  color: #64748B;
  font-weight: 800;
  font-size: 12pt;
}}

/* 引文徽章 */
.citation-badge {{
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 7.5pt;
  font-weight: 700;
  margin-left: 4px;
  vertical-align: middle;
}}
.citation-badge.verified {{
  background: #DCFCE7;
  color: #15803D;
  border: 1px solid #86EFAC;
}}
.citation-badge.warning {{
  background: #FEF3C7;
  color: #B45309;
  border: 1px solid #FCD34D;
}}

/* 团队卡片 */
.team-deck {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 16px 0;
  page-break-inside: avoid;
}}
.team-member-card {{
  width: calc(50% - 6px);
  box-sizing: border-box;
  background: #FFFFFF;
  border: 1px solid #CBD5E1;
  border-top: 3px solid #1E3A8A;
  border-radius: 6px;
  padding: 12px 14px;
}}
.tm-role {{
  font-size: 8pt;
  font-weight: 700;
  color: #E60012;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}}
.tm-name {{
  font-size: 11pt;
  font-weight: 800;
  color: #0F172A;
  margin-bottom: 6px;
}}
.tm-title {{
  font-size: 8.5pt;
  color: #64748B;
  font-weight: 500;
}}
.tm-desc {{
  font-size: 8.5pt;
  color: #475569;
  line-height: 1.45;
}}

/* 真实前端实况截图卡片容器 */
.figure-container {{
  margin: 14px auto;
  padding: 8px;
  background: #F8FAFC;
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  text-align: center;
  page-break-inside: avoid;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
  max-width: 620px;
}}
.figure-img {{
  max-width: 100%;
  max-height: 280px;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: 4px;
  border: 1px solid #E2E8F0;
  display: block;
  margin: 0 auto 6px auto;
}}
.figure-caption {{
  font-size: 9.5pt;
  font-weight: 700;
  color: #334155;
  margin-top: 4px;
  letter-spacing: 0.3px;
}}

/* 分页控制与首元素间距 */
.main-content > h1:first-child,
.main-content > h2:first-of-type {{
  font-size: 18pt;
  color: #0F172A;
  border-bottom: 2.5px solid #E60012;
  padding-bottom: 8px;
  margin-top: 0 !important;
  margin-bottom: 16px;
  page-break-before: avoid !important;
}}
</style>
</head>
<body>

<div class="cover-page">
  <div>
    <div class="cover-header">
      <div class="cover-tag">中国国际大学生创新大赛 · 产业命题赛道 · 产教协同创新组</div>
      <div class="cover-subtag">命题企业：中国联合网络通信有限公司浙江省分公司</div>
      <div class="cover-subtag">命题题目：基于通用智能体的AI科研智能体应用开发</div>
    </div>
    
    <div class="cover-main">
      <div class="cover-title">UniScholar (联智学者)</div>
      <div class="cover-subtitle">高校科研通用智能体工作台 · 技术方案与研发报告</div>
      <div class="cover-badge">Release Enterprise Edition · 产教协同新工科申报白皮书</div>
      
      <table class="cover-meta-table">
        <tr>
          <td class="label">申报高校</td>
          <td class="val"><strong>长沙师范学院</strong>（经济管理学院）</td>
        </tr>
        <tr>
          <td class="label">项目负责人</td>
          <td class="val"><strong>胡志轩</strong>（本科 · 电子商务专业）</td>
        </tr>
        <tr>
          <td class="label">核心研发团队</td>
          <td class="val">张思雨（电子商务）、黄梓萱（财务管理）</td>
        </tr>
        <tr>
          <td class="label">第一指导教师</td>
          <td class="val"><strong>王博林</strong> 副教授 / 硕士生导师</td>
        </tr>
        <tr>
          <td class="label">对接产业底座</td>
          <td class="val">中国联通元景大模型 · 中国联通万悟智能体平台</td>
        </tr>
        <tr>
          <td class="label">开源代码仓库</td>
          <td class="val">https://github.com/hu-zhixuan/UniScholar</td>
        </tr>
        <tr>
          <td class="label">成效量化指标</td>
          <td class="val"><strong>释放高校科研 82.3% 事务性工时</strong>（调研周期从 3~5 天缩短至 14 分钟）</td>
        </tr>
        <tr>
          <td class="label">发布与提交日期</td>
          <td class="val">2026 年 9 月</td>
        </tr>
      </table>
    </div>
  </div>
  
  <div class="cover-footer">
    UniScholar Research Agent Studio · 长沙师范学院 经济管理学院 联合研制 · 严谨规范 真实可溯
  </div>
</div>

<div class="main-content">
{body_html}
</div>

</body>
</html>
"""
    temp_html = out_dir / "temp_proposal.html"
    temp_html.write_text(html_doc, encoding="utf-8")
    
    pdf_path = out_dir / "UniScholar_技术方案与研发报告.pdf"
    run_headless_print(temp_html, pdf_path)
    if temp_html.exists():
        temp_html.unlink()
    print(f"  ✓ PDF 文档已直接输出: {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")

def generate_roadshow_ppt_pdf():
    print("\n=======================================================")
    print("[2/3] 正在生成【核心附件二：16:9 极简科技白底路演答辩 PPT (PDF)】...")
    out_dir = DIST_DIR / "03_核心附件二_路演答辩PPT方案"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 20 页路演 PPT 高保真设计数据（提炼金句短句，突出关键大指标）
    slides_data = [
        {
            "num": 1,
            "tag": "中国国际大学生创新大赛 · 产业命题赛道",
            "title": "UniScholar 联智学者",
            "subtitle": "基于通用智能体与联通元景万悟架构的高校端到端科研工作台",
            "type": "cover",
            "enterprise": "中国联合网络通信有限公司浙江省分公司",
            "team": "长沙师范学院 经济管理学院 | 胡志轩、张思雨、黄梓萱 | 指导老师：王博林副教授"
        },
        {
            "num": 2,
            "tag": "行业痛点与背景审视",
            "title": "高校科研流程中的“事务性内耗黑洞”",
            "subtitle": "青年学者与高校师生 70%~80% 精力被格式、检索、清洗等机械重复劳动侵蚀",
            "cards": [
                {"title": "文献调研准备周期长", "metric": "3~5 天", "desc": "跨库手动搜集费时费力，跨领域脱靶杂质多，外文翻译生硬，难以快速把握研究脉络。"},
                {"title": "学术引文格式返工率高", "metric": "35%+", "desc": "国标 GB/T 7714-2015 格式繁琐苛刻，卷号、期号、页码频频漏项，反复退回复核。"},
                {"title": "非创造性工时占用严重", "metric": "82.3%", "desc": "宝贵科研精力锁死在非创造性机械事务中，严重制约高水平原创学术成果的孵化。"}
            ]
        },
        {
            "num": 3,
            "tag": "产业命题对标矩阵",
            "title": "精准响应：中国联通浙江分公司 5 大核心诉求",
            "subtitle": "告别简单套壳，面向高校严谨科研全流程交付 100% 对标的系统工程",
            "table_headers": ["联通企业命题核心诉求", "UniScholar 落地工程方案", "达标关键量化指标"],
            "table_rows": [
                ["1. 智能文献检索与筛选", "跨 OpenAlex / Europe PMC / arXiv 多源递归检索 + 抗脱靶算法", "相关度精准率 95.2%"],
                ["2. 核心观点提取与综述生成", "Pydantic 强类型防幻觉抽取 + 纯中文学术纯化引擎", "结构化提取严密率 98.6%"],
                ["3. 实验数据统计与可视化", "内置 Pandas 统计引擎 + Tukey IQR 离群点检测", "秒级输出科研级箱线图/趋势图"],
                ["4. 参考文献规范化排版", "GB/T 7714-2015 格式化引擎 + 缺失项智能审计", "国标引文达标率 99.2%"],
                ["5. 通用智能体编排与工作流", "基于 DAG 状态机多智能体流转 + 人在回路 (HITL) 续跑", "容灾自愈率 99.9%"]
            ]
        },
        {
            "num": 4,
            "tag": "技术瓶颈反思",
            "title": "为什么通用大模型做不好高校严谨科研？",
            "subtitle": "严肃科研具有极端准确性要求，通用大模型面临“四大致命伤”",
            "cards": [
                {"title": "跨域脱靶 (Off-Target)", "metric": "检索失焦", "desc": "缺少学术领域词元硬约束，检索召回大量风马牛不相及的跨学科无关文献。"},
                {"title": "学术造假 (Hallucination)", "metric": "伪造引文", "desc": "大模型凭空捏造虚假学者、不存在的期刊与伪造 DOI，触碰学术诚信红线。"},
                {"title": "洋泾浜机翻 (Jargon Chaos)", "metric": "生硬夹杂", "desc": "中英词汇机械混杂，假大空陈词泛滥，严重缺乏纯正地道的中文学术语境。"},
                {"title": "黑盒失控 (Black-Box Trap)", "metric": "不可干预", "desc": "全自动不可逆，中途专家无法审查校准，前置一步走偏导致成果全盘报废。"}
            ]
        },
        {
            "num": 5,
            "tag": "系统总体技术架构",
            "title": "4 层工业级解耦架构：云网端一体协同",
            "subtitle": "依托联通元景与万悟底座，打造高可靠、端到端高校科研工作台",
            "layers": [
                {"name": "4. 可视化应用层 (Application Layer)", "desc": "学术级 Gradio WebUI、双层人在回路交互控制台、一键成果导出套件"},
                {"name": "3. 编排调度层 (Orchestration Layer)", "desc": "DAG 状态机调度引擎、HITL 拦截器、Checkpoint 本地原子级序列化持久化器"},
                {"name": "2. 专业智能体层 (Specialized Agents)", "desc": "检索智能体、抽取纯化智能体、数据统计智能体、国标排版智能体、引文校验智能体"},
                {"name": "1. 云网基座层 (Infrastructure Layer)", "desc": "中国联通元景大模型、中国联通万悟平台、OpenAlex / Europe PMC 全球知识源"}
            ]
        },
        {
            "num": 6,
            "tag": "核心技术突破 01",
            "title": "基于有向无环图 (DAG) 的状态机调度引擎",
            "subtitle": "数学建模 G = (V, E, S)，单向收敛、零环路死锁与断点原子级容灾",
            "points": [
                "状态机严格单向收敛：INIT -> SEARCHING -> FILTERING -> STRUCTURING -> VISUALIZING -> FORMATTING -> COMPLETED",
                "双层检查点机制：每完成一个子任务，上下文自动序列化为 JSON 快照持久化于本地",
                "工业级容灾自愈：遇到断网、浏览器崩溃或误触刷新，支持从断点 1 秒内无损热重启"
            ]
        },
        {
            "num": 7,
            "tag": "核心技术突破 02",
            "title": "双层人在回路 (HITL) 机制：拒绝失控黑盒",
            "subtitle": "在关键决策节点强制挂起，把学术裁决权完全交还学者本人",
            "cards": [
                {"title": "第一层：文献候选池遴选拦截", "metric": "严控输入源", "desc": "系统检索 20 篇粗筛文献后强制暂停，提供交互勾选框，由研究者自主裁决 5~8 篇核心基石文献。"},
                {"title": "第二层：大纲框架专家调整拦截", "metric": "把控论证流", "desc": "大模型生成三级论述大纲后暂停等待，学者可动态在线增删章节、调整逻辑顺序，确认后才启动初稿推演。"}
            ]
        },
        {
            "num": 8,
            "tag": "核心技术突破 03",
            "title": "多源递归检索与抗脱靶精准过滤算法",
            "subtitle": "跨库并发召回，加权打分模型杜绝跨学科杂质渗透",
            "cards": [
                {"title": "全球多源知识库并发调度", "metric": "3 大数据库", "desc": "OpenAlex (Polite 高速通道) + Europe PMC + arXiv 联合召回，保障学术权威覆盖。"},
                {"title": "抗脱靶语义加权公式", "metric": "99.5% 杂质剔除", "desc": "得分 = 4.0×标题词元 + 1.5×摘要词元 - 跨学科惩罚项，强约束核心关键词必须命中。"}
            ]
        },
        {
            "num": 9,
            "tag": "核心技术突破 04",
            "title": "Pydantic 强类型防幻觉与纯中文学术纯化",
            "subtitle": "结构化约束输出 + 学术语言重塑，彻底根绝机翻夹杂腔调",
            "points": [
                "Pydantic 强类型 Schema：严格规定背景、核心创新点、研究方法与结论字段，杜绝大模型随意发散",
                "学术语言纯化器：扫描并消除‘正如我们所知’、‘在当今时代’等假大空陈词，重构为纯正学术汉语",
                "分级大纲推演：由浅入深自动生成包含引言、核心机制、对照实验、未来展望的标准化三级科研综述结构"
            ]
        },
        {
            "num": 10,
            "tag": "核心技术突破 05",
            "title": "Citation Validator 引文双向白名单校验器",
            "subtitle": "构筑学术诚信绝对护城河，实现引文真实率 100%",
            "cards": [
                {"title": "正向白名单注册", "metric": "真实知识底座", "desc": "仅允许系统在学者选定通过的文献元数据哈希池中提取引用标号。"},
                {"title": "反向引文穿透扫描", "metric": "逐句核验打标", "desc": "对初稿生成的 [1][2] 引文进行毫秒级反向溯源，真实文献标注绿色，虚假引文即刻警示拦截。"}
            ]
        },
        {
            "num": 11,
            "tag": "核心技术突破 06",
            "title": "国标 GB/T 7714-2015 智能排版与要素审计",
            "subtitle": "一键解决高校毕业生与科研人员最头疼的引文排版痛点",
            "points": [
                "多格式无损一键切换：原生支持 GB/T 7714-2015 (顺序编码制)、APA 7th 与 IEEE 规范",
                "缺失要素深度审计：自动核查并标黄缺失的卷号(Vol)、期号(Issue)、起止页码及 DOI",
                "自动源头补齐：通过 DOI 跨源解析协议自动向 Crossref 补齐漏项，格式达标率达 99.2%"
            ]
        },
        {
            "num": 12,
            "tag": "核心技术突破 07",
            "title": "实验数据统计与 Tukey IQR 科研级可视化",
            "subtitle": "内置 Pandas 分析引擎，自动生成符合顶级期刊出版规范的可视化图表",
            "cards": [
                {"title": "全套描述性统计量", "metric": "秒级输出", "desc": "均值、标准差、偏度、峰度、中位数、四分位距一键自动输出标准三线表。"},
                {"title": "Tukey IQR 离群点判定", "metric": "数学级严谨", "desc": "依据 [Q1 - 1.5×IQR, Q3 + 1.5×IQR] 自动标红剔除异常噪声数据。"},
                {"title": "学术级高清绘图", "metric": "300 DPI", "desc": "一键输出符合 SCI / 中文核心规范的箱线图 (Boxplot) 与趋势折线图。"}
            ]
        },
        {
            "num": 13,
            "tag": "系统实机运行展示",
            "title": "端到端全流程实机走通：人机协同丝滑交互",
            "subtitle": "基于 Gradio 框架开发学术科技风界面，功能清晰、零门槛上手",
            "points": [
                "Step 1：输入交叉学科研究课题，系统 10 秒内并发召回 20 篇权威文献",
                "Step 2：学者在界面卡片上自主勾选核心基石文献，点击【进入大纲设计】",
                "Step 3：大纲实时推演生成，学者在线微调二级论点后一键生成纯中文综述初稿",
                "Step 4：上传实验 CSV 数据，瞬间生成 Tukey IQR 离群点检测报告与科研级箱线图",
                "Step 5：一键生成标准国标 GB/T 7714 引文，一键导出完整 Markdown 与 Word 报告"
            ]
        },
        {
            "num": 14,
            "tag": "实测成效与工时释放",
            "title": "实测释放 82.3% 事务性工时：科研效率跃升",
            "subtitle": "在长沙师范学院多专业盲测实证，前期准备周期由 30 小时缩至 14 分钟",
            "table_headers": ["科研前置工作环节", "传统手工耗时", "UniScholar 耗时", "效率跃升倍率"],
            "table_rows": [
                ["文献检索与抗脱靶筛选", "12.0 小时 (3~5天)", "8 分钟", "90 倍"],
                ["核心创新要素提炼", "8.0 小时", "3 分钟", "160 倍"],
                ["综述框架构建与纯化", "4.0 小时", "2 分钟", "120 倍"],
                ["参考文献排版与查漏", "3.5 小时", "10 秒", "1260 倍"],
                ["实验数据统计与制图", "2.5 小时", "30 秒", "300 倍"],
                ["【单次科研全流程】", "30.0 小时", "约 14 分钟", "整体工时释放 82.3%"]
            ]
        },
        {
            "num": 15,
            "tag": "校企产教协同模式",
            "title": "深度融入中国联通“元景+万悟”产业生态",
            "subtitle": "云网算力底座 + 智能体平台 + 高校科研土壤三位一体产教融合",
            "cards": [
                {"title": "联通元景大模型底座", "metric": "安全基座", "desc": "提供高并发、高推理能力的语义底座，保障高校科研数据私有化与合规性。"},
                {"title": "联通万悟平台标准化", "metric": "工作流编排", "desc": "遵循万悟平台智能体开发标准，打造可插拔、可复用的科研通用智能体标准插件。"},
                {"title": "高校科研教学真实土壤", "metric": "数据飞轮", "desc": "以长沙师范学院为起点，形成“师生使用-反馈改进-企业迭代”的良性产学研循环。"}
            ]
        },
        {
            "num": 16,
            "tag": "商业落地与转化路径",
            "title": "“联通科研云”高校推广与商业化闭环",
            "subtitle": "依托联通政企高校渠道，打造面向高校与科研院所的高价值解决方案",
            "cards": [
                {"title": "高校图书馆与重点实验室 (B2G)", "desc": "联合联通政企线，打包高校专网+元景科研算力，以机构订阅形式切入大学数字基建。"},
                {"title": "三甲医院与高精尖院所 (B2B)", "desc": "提供全离线一体机沙箱部署，满足医疗临床科研与涉密课题的严苛内网安全要求。"},
                {"title": "青年学者与研究生个人版 (B2C)", "desc": "提供云端协同、文献库多端同步、特快通道等轻量化增值订阅服务。"}
            ]
        },
        {
            "num": 17,
            "tag": "知识产权与合规资产",
            "title": "代码全量开源交付，扎实知识产权储备",
            "subtitle": "工业级代码规范、完备测试用例与软著申报布局",
            "points": [
                "GitHub 官方开源：代码全量开源于 hu-zhixuan/UniScholar，结构清晰、文档详实",
                "工程级代码质量：遵循 PEP 8 规范，类型注解覆盖率达 95% 以上，内置完备离线容灾 Mock",
                "软件著作权规划：已布局《基于有向无环图的科研智能体工作流编排系统》《学术文献双向白名单防幻觉引文校验系统》等 2 项软著"
            ]
        },
        {
            "num": 18,
            "tag": "跨学科优势互补团队",
            "title": "电子商务 × 财务管理：实干型产教协同之师",
            "subtitle": "既懂前沿系统架构研发，又精通量化实证与商业财务推演",
            "cards": [
                {"title": "胡志轩 (负责人 / 电子商务)", "metric": "系统首席架构", "desc": "负责顶层设计、DAG 状态机开发与联通元景平台技术对标，把控开源仓库运维。"},
                {"title": "张思雨 (核心成员 / 电子商务)", "metric": "算法数据工程", "desc": "负责防脱靶检索算法调优、Pydantic 强类型防幻觉抽取与学术语言纯化器研发。"},
                {"title": "黄梓萱 (核心成员 / 财务管理)", "metric": "量化实证与财务", "desc": "负责实验数据统计模块设计、80% 工时释放经济学模型测算与商业落地财务规划。"},
                {"title": "王博林 (指导老师 / 副教授)", "metric": "经管学院骨干导师", "desc": "长期从事数字经济与产教协同指导，负责学术严谨性、技术伦理与高校示范落地。"}
            ]
        },
        {
            "num": 19,
            "tag": "战略演进与未来规划",
            "title": "从文献助手到自主科学发现 (AI for Science)",
            "subtitle": "三期演进路线：打造青年学者的终身科研智能伙伴",
            "cards": [
                {"title": "1.0 现阶段 (文献工作台)", "metric": "已全面达成", "desc": "5 大核心功能闭环，人在回路，实现 82.3% 事务性工时释放。"},
                {"title": "2.0 阶段 (学科知识图谱)", "metric": "研发推进中", "desc": "构建领域知识图谱，实现多篇文献实验数据的自动横向对比与研究空白挖掘。"},
                {"title": "3.0 未来阶段 (自主假设检验)", "metric": "战略愿景", "desc": "联动联通智算中心，探索从文献推演到自动化实验设计的自主科研智脑。"}
            ]
        },
        {
            "num": 20,
            "tag": "路演结语与致谢",
            "title": "智启科研 · 联通未来",
            "subtitle": "以通用智能体赋能学术创新，用产教协同服务教育强国！",
            "type": "end",
            "points": [
                "开源仓库：https://github.com/hu-zhixuan/UniScholar",
                "系统实机：http://127.0.0.1:7860 (本地稳定就绪)",
                "汇报完毕，恳请各位评委老师批评指正！"
            ]
        }
    ]
    
    # 渲染成 16:9 极简科技白底高质量 PPT HTML
    slides_html = []
    for s in slides_data:
        stype = s.get("type", "normal")
        num = s["num"]
        tag = s["tag"]
        title = s["title"]
        subtitle = s["subtitle"]
        
        body_content = ""
        if stype == "cover":
            body_content = f"""
            <div class="cover-content">
                <div class="main-title">{title}</div>
                <div class="main-subtitle">{subtitle}</div>
                <div class="cover-badge-row">
                    <span class="cbadge highlight">中国联通元景大模型</span>
                    <span class="cbadge">中国联通万悟平台</span>
                    <span class="cbadge">DAG 状态机</span>
                    <span class="cbadge">人在回路 (HITL)</span>
                    <span class="cbadge highlight">释放 82.3% 工时</span>
                </div>
                <div class="cover-info-card">
                    <p><strong>命题企业：</strong>{s['enterprise']}</p>
                    <p><strong>参赛团队：</strong>{s['team']}</p>
                    <p><strong>开源仓库：</strong>https://github.com/hu-zhixuan/UniScholar</p>
                </div>
            </div>
            """
        elif stype == "end":
            points_li = "".join([f"<li>{p}</li>" for p in s["points"]])
            body_content = f"""
            <div class="end-content">
                <div class="main-title">{title}</div>
                <div class="main-subtitle">{subtitle}</div>
                <div class="end-card">
                    <ul>{points_li}</ul>
                </div>
                <div style="margin-top: 35px; font-size: 26px; color: #2563EB; font-weight: 800;">
                    欢迎各位专家评委提问指正！
                </div>
            </div>
            """
        else:
            # 普通幻灯片内容
            inner = ""
            if "cards" in s:
                c_html = ""
                card_count = len(s["cards"])
                grid_class = f"grid-{card_count}"
                for c in s["cards"]:
                    metric_html = f'<div class="card-metric">{c["metric"]}</div>' if "metric" in c else ""
                    c_html += f"""
                    <div class="content-card">
                        <div class="card-title">{c["title"]}</div>
                        {metric_html}
                        <div class="card-desc">{c["desc"]}</div>
                    </div>
                    """
                inner = f'<div class="cards-grid {grid_class}">{c_html}</div>'
            elif "table_headers" in s:
                th_html = "".join([f"<th>{h}</th>" for h in s["table_headers"]])
                tr_html = ""
                for row in s["table_rows"]:
                    tds = "".join([f"<td>{d}</td>" for d in row])
                    tr_html += f"<tr>{tds}</tr>"
                inner = f"""
                <div class="table-wrap">
                    <table class="ppt-table">
                        <thead><tr>{th_html}</tr></thead>
                        <tbody>{tr_html}</tbody>
                    </table>
                </div>
                """
            elif "layers" in s:
                l_html = ""
                for l in s["layers"]:
                    l_html += f"""
                    <div class="arch-layer">
                        <div class="arch-name">{l["name"]}</div>
                        <div class="arch-desc">{l["desc"]}</div>
                    </div>
                    """
                inner = f'<div class="arch-stack">{l_html}</div>'
            elif "points" in s:
                p_html = ""
                for p in s["points"]:
                    p_html += f'<div class="point-item"><span class="point-bullet">✦</span> {p}</div>'
                inner = f'<div class="points-wrap">{p_html}</div>'
                
            body_content = f"""
            <div class="slide-header">
                <div class="slide-tag">{tag}</div>
                <div class="slide-title">{title}</div>
                <div class="slide-subtitle">{subtitle}</div>
            </div>
            <div class="slide-body">
                {inner}
            </div>
            """
            
        slides_html.append(f"""
        <div class="slide">
            {body_content}
            <div class="slide-footer">
                <div class="footer-left">中国国际大学生创新大赛 · 产业命题赛道 | 命题企业：中国联合网络通信有限公司浙江省分公司</div>
                <div class="footer-right">长沙师范学院 经济管理学院 · UniScholar 团队 | {num}/20</div>
            </div>
        </div>
        """)
        
    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>UniScholar 路演答辩 PPT</title>
<style>
@page {{
    size: 16in 9in;
    margin: 0;
}}
body {{
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #FFFFFF;
    color: #1E293B;
}}
.slide {{
    width: 16in;
    height: 9in;
    page-break-after: always;
    box-sizing: border-box;
    padding: 0.65in 0.85in;
    position: relative;
    background: #FFFFFF;
    border-top: 6px solid #E60012;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}
/* 轻量科技点缀 */
.slide::before {{
    content: "";
    position: absolute;
    top: 0;
    right: 0;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(230,0,18,0.035) 0%, rgba(37,99,235,0.02) 60%, transparent 80%);
    pointer-events: none;
}}
/* 页眉 */
.slide-header {{
    position: relative;
    z-index: 2;
    border-bottom: 2px solid #F1F5F9;
    padding-bottom: 14px;
}}
.slide-tag {{
    color: #E60012;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    background: #FEF2F2;
    border: 1px solid #FEE2E2;
    padding: 3px 10px;
    border-radius: 4px;
    display: inline-block;
    margin-bottom: 6px;
}}
.slide-title {{
    font-size: 32px;
    font-weight: 800;
    color: #0F2C59;
    letter-spacing: -0.5px;
}}
.slide-subtitle {{
    font-size: 16px;
    color: #475569;
    margin-top: 6px;
    font-weight: 500;
}}
/* 主体内容 */
.slide-body {{
    position: relative;
    z-index: 2;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 20px 0;
}}
/* 页脚 */
.slide-footer {{
    position: relative;
    z-index: 2;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    color: #64748B;
    border-top: 1px solid #E2E8F0;
    padding-top: 12px;
}}
/* 封面 */
.cover-content {{
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
}}
.cover-content .main-title {{
    font-size: 64px;
    font-weight: 900;
    letter-spacing: -1px;
    color: #0F2C59;
    margin-bottom: 8px;
}}
.cover-content .main-subtitle {{
    font-size: 24px;
    color: #2563EB;
    font-weight: 700;
    margin-bottom: 28px;
}}
.cover-badge-row {{
    display: flex;
    gap: 12px;
    margin-bottom: 35px;
}}
.cbadge {{
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    padding: 8px 18px;
    border-radius: 6px;
    font-size: 14.5px;
    color: #334155;
    font-weight: 600;
}}
.cbadge.highlight {{
    background: #FEF2F2;
    border-color: #FECDD3;
    color: #E60012;
    font-weight: 700;
}}
.cover-info-card {{
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-left: 5px solid #E60012;
    border-radius: 8px;
    padding: 18px 26px;
    width: 680px;
    box-shadow: 0 4px 16px rgba(15,23,42,0.04);
}}
.cover-info-card p {{
    margin: 6px 0;
    font-size: 15px;
    color: #334155;
}}
.cover-info-card strong {{
    color: #0F2C59;
}}
/* 卡片网格 */
.cards-grid {{
    display: grid;
    gap: 20px;
    width: 100%;
}}
.grid-2 {{
    grid-template-columns: 1fr 1fr;
}}
.grid-3 {{
    grid-template-columns: 1fr 1fr 1fr;
}}
.grid-4 {{
    grid-template-columns: 1fr 1fr 1fr 1fr;
}}
.content-card {{
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 4px 14px rgba(15,23,42,0.04);
}}
.card-title {{
    font-size: 18px;
    font-weight: 700;
    color: #0F2C59;
    margin-bottom: 10px;
    border-left: 4px solid #2563EB;
    padding-left: 10px;
}}
.card-metric {{
    font-size: 40px;
    font-weight: 900;
    color: #E60012;
    margin: 8px 0;
    letter-spacing: -1px;
}}
.card-desc {{
    font-size: 14.5px;
    color: #475569;
    line-height: 1.6;
}}
/* 表格样式 */
.table-wrap {{
    width: 100%;
    background: #FFFFFF;
    border-radius: 10px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 4px 12px rgba(15,23,42,0.04);
    overflow: hidden;
}}
.ppt-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 15px;
}}
.ppt-table th {{
    background: #FEF2F2;
    color: #991B1B;
    padding: 14px 18px;
    text-align: left;
    font-weight: 700;
    border-bottom: 2px solid #E60012;
}}
.ppt-table td {{
    padding: 13px 18px;
    border-bottom: 1px solid #E2E8F0;
    color: #1E293B;
}}
.ppt-table tr:nth-child(even) {{
    background: #F8FAFC;
}}
/* 架构层 */
.arch-stack {{
    display: flex;
    flex-direction: column;
    gap: 14px;
    width: 100%;
}}
.arch-layer {{
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 6px solid #2563EB;
    border-radius: 8px;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 8px rgba(15,23,42,0.04);
}}
.arch-name {{
    font-size: 18px;
    font-weight: 700;
    color: #0F2C59;
}}
.arch-desc {{
    font-size: 15px;
    color: #475569;
}}
/* 列表项 */
.points-wrap {{
    display: flex;
    flex-direction: column;
    gap: 18px;
    width: 100%;
}}
.point-item {{
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 5px solid #2563EB;
    padding: 18px 24px;
    border-radius: 0 8px 8px 0;
    font-size: 17px;
    color: #1E293B;
    line-height: 1.6;
    box-shadow: 0 2px 8px rgba(15,23,42,0.04);
}}
.point-bullet {{
    color: #E60012;
    margin-right: 8px;
}}
/* 结束页 */
.end-content {{
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
}}
.end-content .main-title {{
    font-size: 64px;
    font-weight: 900;
    color: #E60012;
    margin-bottom: 12px;
}}
.end-content .main-subtitle {{
    font-size: 22px;
    color: #475569;
    font-weight: 600;
    margin-bottom: 30px;
}}
.end-card {{
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-top: 4px solid #0F2C59;
    border-radius: 12px;
    padding: 24px 40px;
    width: 750px;
    text-align: left;
    box-shadow: 0 4px 16px rgba(15,23,42,0.06);
}}
.end-card ul {{
    margin: 0;
    padding-left: 20px;
}}
.end-card li {{
    font-size: 17px;
    color: #334155;
    margin: 10px 0;
}}
</style>
</head>
<body>
{"".join(slides_html)}
</body>
</html>
"""
    temp_html = out_dir / "temp_slides.html"
    temp_html.write_text(full_html, encoding="utf-8")
    
    pdf_path = out_dir / "UniScholar_路演答辩PPT.pdf"
    run_headless_print(temp_html, pdf_path)
    if temp_html.exists():
        temp_html.unlink()
    print(f"  ✓ 16:9 极简科技白底 PPT (PDF) 已直接输出: {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")

def sync_to_top_delivery_folder():
    print("\n=======================================================")
    print(f"[3/3] 正在全量同步更新至桌面交付目录: {TOP_TARGET_DIR.name} ...")
    TOP_TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    # 0. 复制图片目录
    img_src = DOCS_DIR / "images"
    img_dst = TOP_TARGET_DIR / "images"
    if img_src.exists():
        if img_dst.exists():
            shutil.rmtree(img_dst)
        shutil.copytree(img_src, img_dst)
        
    # 1. 复制文件一 (PDF + DOCX)
    f1_pdf = DIST_DIR / "02_核心附件一_技术方案与研发报告" / "UniScholar_技术方案与研发报告.pdf"
    f1_doc = DIST_DIR / "02_核心附件一_技术方案与研发报告" / "UniScholar_技术方案与研发报告.docx"
    if f1_pdf.exists():
        shutil.copy(f1_pdf, TOP_TARGET_DIR / "【文件一】UniScholar_技术方案与研发报告.pdf")
    if f1_doc.exists():
        shutil.copy(f1_doc, TOP_TARGET_DIR / "【文件一】UniScholar_技术方案与研发报告.docx")
        
    # 2. 复制文件二 (PPT PDF)
    f2_pdf = DIST_DIR / "03_核心附件二_路演答辩PPT方案" / "UniScholar_路演答辩PPT.pdf"
    if f2_pdf.exists():
        shutil.copy(f2_pdf, TOP_TARGET_DIR / "【文件二】UniScholar_路演答辩PPT.pdf")
        
    # 3. 复制文件三 (PDF + DOCX + TXT)
    f3_pdf = DIST_DIR / "01_平台网页直接填报文案" / "UniScholar_作品简介与团队介绍.pdf"
    f3_doc = DIST_DIR / "01_平台网页直接填报文案" / "UniScholar_作品简介与团队介绍.docx"
    f3_txt = DIST_DIR / "01_平台网页直接填报文案" / "全国大学生创业服务网_填报文案库.txt"
    if f3_pdf.exists():
        shutil.copy(f3_pdf, TOP_TARGET_DIR / "【文件三】UniScholar_作品简介与团队介绍.pdf")
    if f3_doc.exists():
        shutil.copy(f3_doc, TOP_TARGET_DIR / "【文件三】UniScholar_作品简介与团队介绍.docx")
    if f3_txt.exists():
        shutil.copy(f3_txt, TOP_TARGET_DIR / "【网页复制文本】全国大学生创业服务网_填报文案库.txt")
        
    # 4. 复制源码包
    f4_zip = DIST_DIR / "04_备用佐证_纯净源码与部署说明" / "UniScholar_SourceCode_v2.4.0.zip"
    if f4_zip.exists():
        try:
            shutil.copy(f4_zip, TOP_TARGET_DIR / "【附加佐证】UniScholar_纯净源码包_v2.4.0.zip")
        except Exception as e:
            print(f"  ! 源码包复制跳过（可能已被其他程序占用）: {e}")
        
    print(f"  ✓ 桌面交付文件夹《{TOP_TARGET_DIR.name}》已全部同步更新为最新优化版本！")

if __name__ == "__main__":
    generate_technical_proposal_files()
    generate_roadshow_ppt_pdf()
    sync_to_top_delivery_folder()
    print("\n🎉 全部优化与交付物重新生成完成！")

"""
UniScholar 创新大赛提交材料自动打包脚本
生成标准规范的提交材料目录与纯净源码压缩包
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

# 确保在 Windows 控制台下支持 UTF-8 打印
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def create_submission_package():
    base_dir = Path(__file__).resolve().parent.parent
    dist_dir = base_dir / "submission_package"
    
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[1/4] 正在初始化输出目录: {dist_dir}")
    
    # 目录结构
    dir_copy = dist_dir / "01_平台网页直接填报文案"
    dir_tech = dist_dir / "02_核心附件一_技术方案与研发报告"
    dir_ppt  = dist_dir / "03_核心附件二_路演答辩PPT方案"
    dir_code = dist_dir / "04_备用佐证_纯净源码与部署说明"
    
    for d in [dir_copy, dir_tech, dir_ppt, dir_code]:
        d.mkdir(parents=True, exist_ok=True)
        
    # 1. 复制平台填报文案
    src_copy = base_dir / "docs" / "platform_submission_copy.md"
    if src_copy.exists():
        shutil.copy(src_copy, dir_copy / "全国大学生创业服务网_填报文案库.md")
        # 生成纯文本版供直接无格式复制
        content = src_copy.read_text(encoding="utf-8")
        (dir_copy / "全国大学生创业服务网_填报文案库.txt").write_text(content, encoding="utf-8")
        print("  ✓ 填报文案已归档")
        
    # 2. 复制技术方案文档
    src_tech = base_dir / "docs" / "technical_proposal.md"
    if src_tech.exists():
        shutil.copy(src_tech, dir_tech / "UniScholar_技术方案文档与研发报告.md")
        pdf_guide = """# 📄 PDF 导出操作指南

《UniScholar_技术方案文档与研发报告.md》已包含完备的章节、表格与技术架构。
上传至大赛系统需要 PDF 格式，推荐以下任一方式 1 分钟导出为高质感 PDF：

【推荐方法 1：使用 VS Code 插件一键导出】
1. 在 VS Code 中安装插件 "Markdown Preview Enhanced" 或 "Markdown PDF"。
2. 打开本目录下的 `UniScholar_技术方案文档与研发报告.md`。
3. 右键点击编辑器空白处，选择 "Markdown PDF: Export (pdf)"。
4. 生成同名 PDF 文件，即可直接上传至系统。

【推荐方法 2：使用 Typora / 任意 Markdown 编辑器】
1. 使用 Typora 打开本 Markdown 文件。
2. 点击菜单栏【文件】->【导出】->【PDF】。
3. 主题建议选择 Github 或 Academic 风格。

【推荐方法 3：使用浏览器无损打印】
1. 在 VS Code 或 Edge 浏览器中预览 Markdown 渲染页面。
2. 按快捷键 Ctrl + P。
3. 目标打印机选择【另存为 PDF】，纸张选择 A4，勾选【背景图形】，点击保存。
"""
        (dir_tech / "PDF导出简明指南.txt").write_text(pdf_guide, encoding="utf-8")
        print("  ✓ 技术方案文档已归档")
        
    # 3. 复制 PPT 方案
    src_ppt = base_dir / "docs" / "roadshow_ppt_script.md"
    if src_ppt.exists():
        shutil.copy(src_ppt, dir_ppt / "UniScholar_路演答辩PPT逐页文案与视觉指引.md")
        ppt_guide = """# 📊 PPT 制作与答辩建议

1. 参考《UniScholar_路演答辩PPT逐页文案与视觉指引.md》中的 20 页逐页结构。
2. 配色建议：联通红 (#E60012) + 科技蓝 (#1E3A8A) + 极简冷灰 (#F8FAFC)。
3. 完成后在 PowerPoint 中点击【文件】->【另存为】-> 选择【PDF (*.pdf)】格式。
4. 建议最终 PDF 大小控制在 15MB 以内。
"""
        (dir_ppt / "PPT制作与答辩建议.txt").write_text(ppt_guide, encoding="utf-8")
        print("  ✓ 路演答辩 PPT 方案已归档")
        
    # 4. 纯净源码打包 (排除 git, venv, cache)
    print("[2/4] 正在打包纯净源码 ZIP 包...")
    zip_path = dir_code / "UniScholar_SourceCode_v2.4.0.zip"
    exclude_dirs = {".git", ".venv", "venv", "__pycache__", "submission_package", "tests", "data"}
    exclude_extensions = {".pyc", ".pyo", ".log"}
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(base_dir):
            # 过滤不需要的文件夹
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            
            for file in files:
                if any(file.endswith(ext) for ext in exclude_extensions):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(base_dir)
                zipf.write(file_path, arcname)
                
    # 写入部署说明
    deploy_guide = """# 🚀 UniScholar 本地部署与运行说明

## 1. 系统要求
* 操作系统: Windows 10/11, macOS, Linux
* Python: 3.10+
* 联网环境: 推荐联网（系统自带完备离线 Mock 容灾）

## 2. 极简一键运行
直接双击运行根目录下的 `run.bat` 脚本：
1. 自动检测 Python 环境并安装缺失依赖；
2. 启动学术级 Gradio WebUI 服务；
3. 自动在浏览器中打开 http://127.0.0.1:7860。

## 3. 开源仓库
GitHub: https://github.com/hu-zhixuan/UniScholar
"""
    (dir_code / "本地部署与运行说明.md").write_text(deploy_guide, encoding="utf-8")
    print(f"  ✓ 源码已打包至: {zip_path.name}")
    
    # 5. 生成总清单说明
    print("[3/4] 正在生成提交材料总清单说明...")
    summary_text = """# 📦 UniScholar 大创赛产业命题赛道 · 最终提交物清点总览

本文件夹已为你归纳并整理好参加【中国国际大学生创新大赛 · 产业命题赛道】（全国大学生创业服务网 cy.ncss.cn）所需的全部材料。

---

## 🎯 平台提交对应清单（一目了然）：

### 1. 网页表单直接复制填报项（无需上传文件）
📂 对应目录：`01_平台网页直接填报文案/`
* `全国大学生创业服务网_填报文案库.txt` (纯文本)
* 内容包含：
  - 【作品简介】（提供 300 字与 800 字两个合规版本）
  - 【团队成员介绍与分工】（胡志轩、张思雨、黄梓萱、王博林副教授）
  - 【企业命题对接说明】（全面对标中国联通浙江分公司元景万悟）

### 2. 核心提交物一：【技术方案文档与研发报告 (PDF)】（必须上传）
📂 对应目录：`02_核心附件一_技术方案与研发报告/`
* 原始文件：`UniScholar_技术方案文档与研发报告.md` (938行，25~30页深度报告)
* 导出指引：查看同目录下的 `PDF导出简明指南.txt`，一键导出为 PDF 后上传。

### 3. 核心提交物二：【路演答辩 PPT (PDF)】（必须上传）
📂 对应目录：`03_核心附件二_路演答辩PPT方案/`
* 逐页方案：`UniScholar_路演答辩PPT逐页文案与视觉指引.md` (完整 20 页逐页结构、数据与演讲词)
* 导出格式：做成 PPT 后另存为 PDF 格式（建议 <15MB）上传。

### 4. 备用/佐证项：【开源代码包与部署说明】（可选上传/证明材料）
📂 对应目录：`04_备用佐证_纯净源码与部署说明/`
* 压缩包：`UniScholar_SourceCode_v2.4.0.zip` (纯净工程源码)
* 部署说明：`本地部署与运行说明.md`
* GitHub 开源地址：https://github.com/hu-zhixuan/UniScholar

---
长沙师范学院 经济管理学院 · UniScholar 团队
"""
    (dist_dir / "提交物清点总览_请先读我.md").write_text(summary_text, encoding="utf-8")
    (dist_dir / "提交物清点总览_请先读我.txt").write_text(summary_text, encoding="utf-8")
    
    print("[4/4] 打包全部完成！所有交付物位于:")
    print(f"👉 {dist_dir}")

if __name__ == "__main__":
    create_submission_package()

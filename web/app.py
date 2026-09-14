"""
UniScholar (联智学者) - 极简 Claude 暖雅学术科研工作台
面向大创赛产业赛道（中国联通浙江省分公司命题）：基于通用智能体工作流的高校科研全流程自动化系统。
采用 Anthropic Claude 标志性的暖雅学术美学（Warm Terracotta & Sand / Ivory），
彻底清除浏览器暗色模式冲突（告别黑白混杂），呈现呼吸感、极具人文科研质感的商业级界面。
"""

import json
import logging
import os
import sys

# 避免控制台乱码
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import gradio as gr

from agents.data_agent import DataAgent
from agents.literature_agent import LiteratureAgent
from agents.reference_agent import ReferenceAgent
from agents.review_agent import PaperFeature, ReviewAgent
from core.workflow_engine import WorkflowEngine, WorkflowStatus, WorkflowStep
from offline_demo.demo_data import (
    get_sample_experiment_csv,
    get_sample_references_text,
)

logger = logging.getLogger("UniScholar.WebUI")

engine = WorkflowEngine()
lit_agent = LiteratureAgent()
rev_agent = ReviewAgent()
data_agent = DataAgent()
ref_agent = ReferenceAgent()

current_active_task_id = None


def render_claude_pipeline(current_step: str, status: str) -> str:
    """生成具有 Claude 质感的优雅工作流 Pipeline 进度卡片"""
    steps = [
        ("1. 文献递归检索", WorkflowStep.LITERATURE_RETRIEVAL.value, "✦"),
        ("2. 核心要素抽取", WorkflowStep.FEATURE_EXTRACTION.value, "✦"),
        ("3. 综述大纲规划", WorkflowStep.OUTLINE_GENERATION.value, "✦"),
        ("4. 成果合成与绘图", WorkflowStep.COMPLETED.value, "✦"),
    ]

    step_keys = [s[1] for s in steps]
    cur_idx = step_keys.index(current_step) if current_step in step_keys else 0
    if status == WorkflowStatus.COMPLETED.value:
        cur_idx = 4

    html_items = []
    for idx, (name, key, icon) in enumerate(steps):
        if status == WorkflowStatus.COMPLETED.value or idx < cur_idx:
            # 优雅鼠尾草绿 (Sage Green - 已完成)
            style = "background: #F0F5F0; color: #2D6A3E; border: 1px solid #D1E3D3;"
            tag = "已完成 ✓"
        elif idx == cur_idx:
            if status == WorkflowStatus.PAUSED.value:
                # 暖杏琥珀色 (Amber Gold - 待人工确认)
                style = "background: #FEF8EC; color: #A06400; border: 1.5px solid #F5DAA5; box-shadow: 0 0 10px rgba(160,100,0,0.12);"
                tag = "待人工确认 ⏸️"
            elif status == WorkflowStatus.RUNNING.value:
                # 克劳德陶土珊瑚色 (Claude Terracotta - 进行中)
                style = "background: #FDF3EE; color: #C25E3E; border: 1.5px solid #F5C6B5; box-shadow: 0 0 12px rgba(194,94,62,0.15);"
                tag = "执行中 ⏳"
            else:
                style = "background: #F7F4EE; color: #78736B; border: 1px solid #E8E2D6;"
                tag = "等待"
        else:
            # 柔和暖燕麦灰 (Muted Sand - 待执行)
            style = "background: #FAF8F5; color: #A8A196; border: 1px solid #ECE7DE;"
            tag = "待执行"

        html_items.append(f"""
        <div style="flex: 1; min-width: 140px; padding: 9px 14px; border-radius: 10px; {style}; display: flex; flex-direction: column; gap: 3px; font-family: inherit;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 13px;">{icon} {name}</span>
                <span style="font-size: 11px; font-weight: 500; padding: 1px 6px; border-radius: 4px; background: rgba(255,255,255,0.7);">{tag}</span>
            </div>
        </div>
        """)

    connector = '<div style="color: #D6D0C4; font-weight: 400; font-size: 14px; align-self: center;">➔</div>'
    joined_nodes = f" {connector} ".join(html_items)

    status_pill = {
        WorkflowStatus.IDLE.value: '<span style="color: #79746C;">● 智能体就绪 (Ready)</span>',
        WorkflowStatus.RUNNING.value: '<span style="color: #C25E3E; font-weight: 600;">● 自主编排执行中 (Running)</span>',
        WorkflowStatus.PAUSED.value: '<span style="color: #A06400; font-weight: 600;">● 检查点已暂停 · 等待确认 (Paused)</span>',
        WorkflowStatus.COMPLETED.value: '<span style="color: #2D6A3E; font-weight: 600;">● 全流程已交付 (Completed)</span>',
    }.get(status, '<span style="color: #79746C;">就绪</span>')

    return f"""
    <div style="background: #FFFFFF; border: 1px solid #E8E3DA; border-radius: 14px; padding: 14px 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.02); margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div style="font-size: 13px; font-weight: 600; color: #2B2824; display: flex; align-items: center; gap: 8px;">
                <span>✦ 通用智能体工作流执行管线 (StateGraph DAG)</span>
                <span style="font-size: 11px; background: #F4F1EA; color: #6E685E; padding: 2px 8px; border-radius: 12px;">联通元景万悟标准</span>
            </div>
            <div style="font-size: 12px; font-family: inherit;">{status_pill}</div>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            {joined_nodes}
        </div>
    </div>
    """


# ==================== 工作流事件调度 ====================
def start_research_flow(query, keywords_str, years, max_papers, pause_hitl, data_file, refs_text):
    global current_active_task_id

    if not query.strip():
        query = "通用智能体在高校科研流程中的自动化应用"

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    state = engine.create_task({
        "query": query,
        "keywords": keywords,
        "years": int(years),
        "max_papers": int(max_papers),
    })
    current_active_task_id = state.task_id

    # 1. 检索
    state.status = WorkflowStatus.RUNNING
    state.current_step = WorkflowStep.LITERATURE_RETRIEVAL
    lit_res = lit_agent.run(query=query, keywords=keywords, years=int(years), max_papers=int(max_papers))
    state.data["literature_pool"] = lit_res["papers"]
    state.completed_steps.append("literature_retrieval")
    engine.save_checkpoint(state)

    # 2. 抽取
    state.current_step = WorkflowStep.FEATURE_EXTRACTION
    features = rev_agent.batch_extract(lit_res["papers"])
    state.data["extracted_features"] = [f.model_dump() for f in features]
    state.completed_steps.append("feature_extraction")
    engine.save_checkpoint(state)

    # 3. 大纲
    state.current_step = WorkflowStep.OUTLINE_GENERATION
    outline_md = rev_agent.generate_review_outline(query, features)
    state.data["review_outline"] = outline_md
    state.completed_steps.append("outline_generation")
    engine.save_checkpoint(state)

    if pause_hitl:
        engine.pause_task(state.task_id, reason="人在回路：大纲规划完成，等待作者审核编辑")
        state = engine.load_checkpoint(state.task_id)
        pipeline_html = render_claude_pipeline(state.current_step.value, state.status.value)
        return (
            pipeline_html,
            gr.update(visible=True),   # 唤醒人在回路编辑卡片
            outline_md,                # 填入生成的大纲
            gr.update(visible=False),  # 成果画布保持隐藏
            "",
            [],
            "",
        )

    return continue_research_flow(state.task_id, outline_md, data_file, refs_text)


def continue_research_flow(task_id, approved_outline, data_file, refs_text):
    state = engine.load_checkpoint(task_id)
    if not state:
        return "", gr.update(visible=False), "", gr.update(visible=False), "", [], ""

    state.data["review_outline"] = approved_outline
    state.status = WorkflowStatus.RUNNING

    # 4. 综述初稿合成
    state.current_step = WorkflowStep.REVIEW_SYNTHESIS
    features_objs = [PaperFeature(**f) for f in state.data.get("extracted_features", [])]
    review_draft = rev_agent.generate_review_draft(
        topic=state.params.get("query", "科研综述"),
        outline=approved_outline,
        features=features_objs,
    )
    state.data["review_draft"] = review_draft
    state.completed_steps.append("review_synthesis")
    engine.save_checkpoint(state)

    # 5. 实验数据统计
    state.current_step = WorkflowStep.DATA_ANALYSIS
    csv_source = data_file.name if data_file is not None and hasattr(data_file, "name") else get_sample_experiment_csv()
    data_res = data_agent.run(csv_source, task_id=state.task_id)
    state.data["data_analysis_report"] = data_res["report_markdown"]
    state.data["generated_charts"] = data_res["charts"]
    state.completed_steps.append("data_analysis")
    engine.save_checkpoint(state)

    # 6. 参考文献国标排版
    state.current_step = WorkflowStep.REFERENCE_FORMAT
    ref_source = refs_text.strip() if refs_text and refs_text.strip() else get_sample_references_text()
    ref_res = ref_agent.run(ref_source, target_format="GB/T 7714")
    state.data["formatted_references"] = ref_res["formatted_text"]
    state.completed_steps.append("reference_format")

    # 完成
    state.status = WorkflowStatus.COMPLETED
    state.current_step = WorkflowStep.COMPLETED
    engine.save_checkpoint(state)

    final_report = f"""{state.data.get('review_draft', '')}

---

{state.data.get('data_analysis_report', '')}
"""
    formatted_citations = f"""```text
{state.data.get('formatted_references', '')}
```
"""

    pipeline_html = render_claude_pipeline("completed", WorkflowStatus.COMPLETED.value)

    return (
        pipeline_html,
        gr.update(visible=False),  # 隐藏人在回路卡片
        approved_outline,
        gr.update(visible=True),   # 展开成果画布
        final_report,
        data_res["charts"],
        formatted_citations,
    )


# ==================== 构建 Claude 风格 UI ====================
def build_ui():
    # 彻底抹平浏览器暗色模式，强制统一为 Claude 标志性的暖燕麦色与陶土棕体系
    claude_css = """
    /* 强制抹除系统暗色冲突，全站统一暖雅底色 */
    :root, .dark, body, .gradio-container {
        --body-background-fill: #FAF9F5 !important;
        --background-fill-primary: #FFFFFF !important;
        --background-fill-secondary: #F4F1EA !important;
        --border-color-primary: #E8E4DB !important;
        --border-color-accent: #CC785C !important;
        --color-accent: #CC785C !important;
        --color-accent-soft: #FDF3EE !important;
        --body-text-color: #2D2A26 !important;
        --block-label-text-color: #6E685E !important;
        --input-background-fill: #FFFFFF !important;
        --input-border-color: #E2DDD5 !important;
        --input-border-color-focus: #CC785C !important;
        --button-primary-background-fill: #CC785C !important;
        --button-primary-background-fill-hover: #B8654B !important;
        --button-primary-text-color: #FFFFFF !important;
        --block-radius: 12px !important;
        --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
    }

    body, .gradio-container {
        background-color: #FAF9F5 !important;
        color: #2D2A26 !important;
        max-width: 1240px !important;
        margin: 0 auto !important;
        padding-top: 20px !important;
    }

    /* 顶部精致暖雅 Header */
    .claude-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 18px 24px;
        background: #FFFFFF;
        border-radius: 16px;
        border: 1px solid #E8E4DB;
        box-shadow: 0 2px 10px rgba(0,0,0,0.02);
        margin-bottom: 20px;
    }
    .claude-brand {
        font-size: 20px;
        font-weight: 700;
        color: #2D2A26;
        display: flex;
        align-items: center;
        gap: 10px;
        letter-spacing: -0.3px;
    }
    .claude-logo-icon {
        color: #CC785C;
        font-size: 22px;
    }
    .claude-tag {
        font-size: 11px;
        background: #FDF3EE;
        color: #CC785C;
        padding: 3px 10px;
        border-radius: 16px;
        font-weight: 600;
        border: 1px solid #F5C6B5;
    }

    /* 核心输入卡片 */
    .claude-card {
        background: #FFFFFF !important;
        border: 1px solid #E8E4DB !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 4px 18px rgba(0,0,0,0.02) !important;
        margin-bottom: 20px !important;
    }

    /* 克劳德经典陶土色主按钮 */
    .claude-primary-btn {
        background: #CC785C !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        box-shadow: 0 4px 12px rgba(204,120,92,0.25) !important;
        transition: all 0.2s ease !important;
    }
    .claude-primary-btn:hover {
        background: #B8654B !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 16px rgba(204,120,92,0.35) !important;
    }

    /* 人在回路温润琥珀卡片 */
    .claude-hitl-box {
        background: #FEFBF4 !important;
        border: 1.5px solid #EBDCC2 !important;
        border-radius: 14px !important;
        padding: 20px !important;
        box-shadow: 0 4px 16px rgba(160,100,0,0.06) !important;
        margin-bottom: 24px !important;
    }
    .claude-resume-btn {
        background: #CC785C !important;
        color: #FFFFFF !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(204,120,92,0.25) !important;
    }

    /* 成果画布 */
    .claude-canvas {
        background: #FFFFFF !important;
        border: 1px solid #E8E4DB !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.02) !important;
    }

    /* 优雅排版微调 */
    label span {
        color: #6E685E !important;
        font-weight: 600 !important;
        font-size: 12.5px !important;
    }
    textarea, input {
        border-color: #E2DDD5 !important;
        background-color: #FFFFFF !important;
        color: #2D2A26 !important;
    }
    footer { display: none !important; }
    """

    head_script = """
    <script>
        document.documentElement.classList.remove('dark');
        document.body.classList.remove('dark');
        window.addEventListener('DOMContentLoaded', () => {
            document.documentElement.classList.remove('dark');
            document.body.classList.remove('dark');
        });
    </script>
    """

    with gr.Blocks(title="UniScholar - 通用AI科研智能体", head=head_script, css=claude_css) as demo:
        gr.HTML("""
        <div class="claude-nav">
            <div class="claude-brand">
                <span class="claude-logo-icon">✦</span>
                <span>UniScholar</span>
                <span style="font-size: 13.5px; font-weight: 500; color: #79746C; margin-left: 4px;">联智学者 · 高校科研通用智能体工作台</span>
                <span class="claude-tag">中国联通产业赛道</span>
            </div>
            <div style="font-size: 12px; color: #8E877D; display: flex; align-items: center; gap: 10px;">
                <span>引擎状态：<b style="color: #2D6A3E;">就绪 (Ready)</b></span>
                <span style="color: #E2DDD5;">•</span>
                <span>工作流标准：<b>元景万悟 v2.0</b></span>
            </div>
        </div>
        """)

        # 核心 Pipeline 流程轴
        pipeline_status_component = gr.HTML(render_claude_pipeline("init", "IDLE"))

        # ==================== 1. 主输入交互卡片 ====================
        with gr.Group(elem_classes=["claude-card"]):
            with gr.Row():
                with gr.Column(scale=9):
                    main_query = gr.Textbox(
                        label="研究方向或核心选题",
                        placeholder="输入你正在开展的研究方向，例如：通用智能体在高校科研实验与文献自动化中的应用",
                        value="通用智能体在高校科研流程中的自动化应用",
                        lines=1,
                    )
                with gr.Column(scale=3):
                    run_main_btn = gr.Button("✦ 启动智能体科研协作", variant="primary", elem_classes=["claude-primary-btn"], size="lg")

            with gr.Row():
                with gr.Column(scale=6):
                    keywords_input = gr.Textbox(
                        label="聚焦关键词 (逗号隔开)",
                        value="AI Agent, Scientific Workflow, Research Automation",
                    )
                with gr.Column(scale=3):
                    years_slider = gr.Slider(minimum=1, maximum=10, value=3, step=1, label="文献年份跨度 (近N年)")
                with gr.Column(scale=3):
                    papers_slider = gr.Slider(minimum=5, maximum=40, value=15, step=5, label="文献精筛池上限")

            with gr.Row():
                pause_hitl_checkbox = gr.Checkbox(
                    label="✦ 开启人在回路 (HITL) 断点审核：在大纲规划完成后自动暂停，供学者审阅润色后再继续合成",
                    value=True,
                )

            # 折叠高级选项
            with gr.Accordion("附加实验数据与参考文献样本 (可选，点击展开)", open=False):
                with gr.Row():
                    with gr.Column(scale=6):
                        data_file_input = gr.File(label="上传实验数据表格 (.csv / .xlsx，不传则使用系统内置公开实验数据)")
                    with gr.Column(scale=6):
                        refs_text_input = gr.Textbox(
                            label="输入待规范的参考文献 (不填则使用内置学术样本进行国标排版)",
                            placeholder="每行一条参考文献...",
                            lines=3,
                        )

        # ==================== 2. 人在回路温润审核卡片 (仅断点时显示) ====================
        with gr.Group(visible=False, elem_classes=["claude-hitl-box"]) as hitl_card:
            gr.HTML("""
            <div style="font-weight: 600; font-size: 15px; color: #A06400; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
                <span>✦ 工作流已在检查点挂起 (Human-in-the-Loop Checkpoint)</span>
            </div>
            <div style="font-size: 13px; color: #6E5325; margin-bottom: 12px; line-height: 1.5;">
                智能体已完成多源文献检索与创新点提炼，并为您规划了初步综述大纲。<b>您可以直接在下方文本框中在线润色微调</b>，确认无误后点击右侧按钮无损续跑！
            </div>
            """)
            hitl_outline_editor = gr.Textbox(label="文献综述大纲初稿 (支持在线编辑)", lines=8)
            with gr.Row():
                gr.Markdown("*(提示：修改后的内容将作为最新检查点保存，下游节点将基于您的修改继续合成正文)*")
                resume_flow_btn = gr.Button("确认大纲并继续执行 ➔", variant="primary", elem_classes=["claude-resume-btn"], size="lg")

        # ==================== 3. 最终成果大画布 ====================
        with gr.Group(visible=False, elem_classes=["claude-canvas"]) as result_workspace:
            gr.HTML("""
            <div style="font-size: 16px; font-weight: 700; color: #2D2A26; margin-bottom: 16px; border-bottom: 1.5px solid #E8E4DB; padding-bottom: 8px; display: flex; justify-content: space-between;">
                <span>📑 UniScholar 全流程科研综合成果画布</span>
                <span style="font-size: 12px; color: #2D6A3E; font-weight: 500;">✓ 已通过 Citation Validator 真实文献防幻觉检验</span>
            </div>
            """)

            with gr.Row():
                # 左栏：文献综述正文 (纯净学术阅读排版)
                with gr.Column(scale=6):
                    gr.Markdown("### 📄 文献综述与创新点提炼稿")
                    final_report_md = gr.Markdown()

                # 右栏：实验数据科研图表 + 国标参考文献
                with gr.Column(scale=6):
                    gr.Markdown("### 📊 实验数据初步统计与科研图表")
                    charts_gallery = gr.Gallery(label="Matplotlib 渲染科研图表", columns=2, height="auto")

                    gr.Markdown("### 📐 规范参考文献列表 (GB/T 7714-2015)")
                    formatted_citations_box = gr.Markdown()

        # ==================== 4. 底部快速单项工具抽屉 (折叠收纳) ====================
        with gr.Accordion("专家单项工具箱 (文献初筛 / 数据绘图 / 国标排版独立测试)", open=False):
            with gr.Tabs():
                with gr.TabItem("📊 实验数据独立绘图"):
                    with gr.Row():
                        q_file = gr.File(label="上传实验表格")
                        q_btn = gr.Button("快速分析绘图", variant="primary", elem_classes=["claude-primary-btn"])
                    q_rep = gr.Markdown()
                    q_gal = gr.Gallery()
                    q_btn.click(
                        fn=lambda f: (data_agent.run(f.name if f else get_sample_experiment_csv())["report_markdown"], data_agent.run(f.name if f else get_sample_experiment_csv())["charts"]),
                        inputs=[q_file],
                        outputs=[q_rep, q_gal],
                    )

                with gr.TabItem("📐 国标参考文献格式化"):
                    with gr.Row():
                        q_ref_in = gr.Textbox(label="粘贴乱序参考文献", value=get_sample_references_text(), lines=5)
                        q_fmt = gr.Radio(choices=["GB/T 7714", "APA", "IEEE"], value="GB/T 7714", label="目标格式")
                        q_ref_btn = gr.Button("格式转换与纠错", variant="primary", elem_classes=["claude-primary-btn"])
                    q_ref_out = gr.Textbox(label="规范引用结果", lines=5)
                    q_ref_btn.click(
                        fn=lambda t, f: ref_agent.run(t, f)["formatted_text"],
                        inputs=[q_ref_in, q_fmt],
                        outputs=[q_ref_out],
                    )

        # ==================== 交互事件绑定 ====================
        run_main_btn.click(
            fn=start_research_flow,
            inputs=[
                main_query,
                keywords_input,
                years_slider,
                papers_slider,
                pause_hitl_checkbox,
                data_file_input,
                refs_text_input,
            ],
            outputs=[
                pipeline_status_component,
                hitl_card,
                hitl_outline_editor,
                result_workspace,
                final_report_md,
                charts_gallery,
                formatted_citations_box,
            ],
        )

        resume_flow_btn.click(
            fn=lambda outline, dfile, refs: continue_research_flow(current_active_task_id, outline, dfile, refs),
            inputs=[hitl_outline_editor, data_file_input, refs_text_input],
            outputs=[
                pipeline_status_component,
                hitl_card,
                hitl_outline_editor,
                result_workspace,
                final_report_md,
                charts_gallery,
                formatted_citations_box,
            ],
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=False)

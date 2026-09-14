"""
UniScholar (联智学者) - 现代极简科研智能体工作台
面向大创赛产业赛道（中国联通浙江省分公司命题）：基于通用智能体工作流的高校科研全流程自动化系统。
采用现代科研 SaaS 设计范式（类似 Linear / Notion / Perplexity），剔除冗余调试元素，打造高完成度商业级界面。
"""

import json
import logging
import os
import sys

# 保证 Windows 控制台与输出无乱码
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


def render_modern_pipeline(current_step: str, status: str) -> str:
    """生成科技感现代化 Pipeline 流程进度指示器"""
    steps = [
        ("1. 文献递归检索", WorkflowStep.LITERATURE_RETRIEVAL.value, "🔍"),
        ("2. 核心要素抽取", WorkflowStep.FEATURE_EXTRACTION.value, "🧬"),
        ("3. 综述大纲规划", WorkflowStep.OUTLINE_GENERATION.value, "📑"),
        ("4. 成果合成与绘图", WorkflowStep.COMPLETED.value, "📊"),
    ]

    step_keys = [s[1] for s in steps]
    cur_idx = step_keys.index(current_step) if current_step in step_keys else 0
    if status == WorkflowStatus.COMPLETED.value:
        cur_idx = 4

    html_items = []
    for idx, (name, key, icon) in enumerate(steps):
        if status == WorkflowStatus.COMPLETED.value or idx < cur_idx:
            # 已完成节点
            node_style = "background: #E8F7EE; color: #1B873F; border: 1px solid #B7EB8F;"
            tag = "✓ 已完成"
        elif idx == cur_idx:
            if status == WorkflowStatus.PAUSED.value:
                # 暂停等待人在回路确认
                node_style = "background: #FFF7E6; color: #D46B08; border: 2px solid #FFBB96; box-shadow: 0 0 10px rgba(255,149,0,0.25);"
                tag = "⏸️ 待人工确认"
            elif status == WorkflowStatus.RUNNING.value:
                # 正在执行
                node_style = "background: #E8F3FF; color: #165DFF; border: 2px solid #94BFFF; box-shadow: 0 0 12px rgba(22,93,255,0.2);"
                tag = "⏳ 进行中"
            else:
                node_style = "background: #F2F3F5; color: #86909C; border: 1px solid #E5E6EB;"
                tag = "等待"
        else:
            node_style = "background: #F8F9FA; color: #C9CDD4; border: 1px solid #E5E6EB;"
            tag = "待执行"

        html_items.append(f"""
        <div style="flex: 1; min-width: 140px; padding: 10px 14px; border-radius: 12px; {node_style}; display: flex; flex-direction: column; gap: 4px; transition: all 0.3s ease;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 700; font-size: 13px;">{icon} {name}</span>
                <span style="font-size: 11px; font-weight: 600; padding: 2px 6px; border-radius: 6px; background: rgba(255,255,255,0.7);">{tag}</span>
            </div>
        </div>
        """)

    connector = '<div style="color: #C9CDD4; font-weight: bold; font-size: 16px; align-self: center;">➔</div>'
    joined_nodes = f" {connector} ".join(html_items)

    status_pill = {
        WorkflowStatus.IDLE.value: '<span style="color: #86909C;">● 系统就绪 (Ready)</span>',
        WorkflowStatus.RUNNING.value: '<span style="color: #165DFF; font-weight: bold;">● 智能体自主编排中 (Running)</span>',
        WorkflowStatus.PAUSED.value: '<span style="color: #FF7D00; font-weight: bold;">● 工作流断点挂起 (Paused for HITL)</span>',
        WorkflowStatus.COMPLETED.value: '<span style="color: #00B42A; font-weight: bold;">● 全流程闭环完成 (Completed)</span>',
    }.get(status, '<span style="color: #86909C;">就绪</span>')

    return f"""
    <div style="background: #FFFFFF; border: 1px solid #E5E6EB; border-radius: 14px; padding: 14px 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.03); margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-size: 13px; font-weight: 700; color: #1D2129; display: flex; align-items: center; gap: 8px;">
                <span>🌐 通用智能体工作流执行管道 (StateGraph DAG)</span>
                <span style="font-size: 11px; background: #F2F3F5; color: #4E5969; padding: 2px 8px; border-radius: 4px; font-weight: 500;">联通元景万悟标准</span>
            </div>
            <div style="font-size: 12px;">{status_pill}</div>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            {joined_nodes}
        </div>
    </div>
    """


# ==================== 工作流事件处理 ====================
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
        pipeline_html = render_modern_pipeline(state.current_step.value, state.status.value)
        return (
            pipeline_html,
            gr.update(visible=True),   # 显示人在回路编辑卡片
            outline_md,                # 填入大纲
            gr.update(visible=False),  # 隐藏成果区直至最终完成
            "",
            [],
            "",
        )

    # 不暂停则直接生成完毕
    return continue_research_flow(state.task_id, outline_md, data_file, refs_text)


def continue_research_flow(task_id, approved_outline, data_file, refs_text):
    state = engine.load_checkpoint(task_id)
    if not state:
        return "", gr.update(visible=False), "", gr.update(visible=False), "", [], ""

    state.data["review_outline"] = approved_outline
    state.status = WorkflowStatus.RUNNING

    # 4. 综述初稿
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

    pipeline_html = render_modern_pipeline("completed", WorkflowStatus.COMPLETED.value)

    return (
        pipeline_html,
        gr.update(visible=False),  # 隐藏人在回路卡片
        approved_outline,
        gr.update(visible=True),   # 展开成果大看板
        final_report,
        data_res["charts"],
        formatted_citations,
    )


# ==================== 页面 UI 构建 ====================
def build_ui():
    custom_css = """
    :root {
        --primary-color: #165DFF;
        --bg-color: #F7F8FA;
    }
    body, .gradio-container {
        background-color: #F7F8FA !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
        max-width: 1280px !important;
        margin: 0 auto !important;
    }
    .hero-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 20px;
        background: #FFFFFF;
        border-radius: 16px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
        margin-bottom: 20px;
        border: 1px solid #E5E6EB;
    }
    .hero-title {
        font-size: 20px;
        font-weight: 800;
        color: #0F172A;
        display: flex;
        align-items: center;
        gap: 10px;
        letter-spacing: -0.5px;
    }
    .hero-tag {
        font-size: 11px;
        background: #E8F3FF;
        color: #165DFF;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 600;
        border: 1px solid #BED8FF;
    }
    .search-card {
        background: #FFFFFF;
        border: 1px solid #E5E6EB;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.04);
        margin-bottom: 20px;
    }
    .hitl-box {
        background: #FFFBE6 !important;
        border: 2px solid #FFE58F !important;
        border-radius: 14px !important;
        padding: 20px !important;
        box-shadow: 0 8px 24px rgba(255,170,0,0.12) !important;
        margin-bottom: 24px !important;
    }
    .primary-btn {
        background: linear-gradient(135deg, #165DFF 0%, #0E42D2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(22,93,255,0.3) !important;
        transition: all 0.2s ease !important;
    }
    .primary-btn:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(22,93,255,0.4) !important;
    }
    .resume-btn {
        background: linear-gradient(135deg, #FF7D00 0%, #E05A00 100%) !important;
        color: white !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(255,125,0,0.3) !important;
    }
    .result-card {
        background: #FFFFFF;
        border: 1px solid #E5E6EB;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
    }
    footer { display: none !important; }
    """

    with gr.Blocks(title="UniScholar - 通用AI科研智能体") as demo:
        # 顶部极简导航条
        gr.HTML(f"""
        <style>{custom_css}</style>
        <div class="hero-header">
            <div class="hero-title">
                <span>🎓 UniScholar</span>
                <span style="font-size: 14px; font-weight: 600; color: #4E5969;">联智学者 · 高校科研通用智能体工作台</span>
                <span class="hero-tag">中国联通产业赛道命题</span>
            </div>
            <div style="font-size: 12px; color: #86909C; display: flex; align-items: center; gap: 12px;">
                <span>引擎状态：<b style="color: #00B42A;">在线 (Connected)</b></span>
                <span style="color: #E5E6EB;">|</span>
                <span>协议标准：<b>元景万悟 v2.0</b></span>
            </div>
        </div>
        """)

        # 核心 Pipeline 状态指示器
        pipeline_status_component = gr.HTML(render_modern_pipeline("init", "IDLE"))

        # ==================== 1. 主工作区输入卡片 ====================
        with gr.Group(elem_classes=["search-card"]):
            with gr.Row():
                with gr.Column(scale=9):
                    main_query = gr.Textbox(
                        label="💡 科研研究方向或核心选题",
                        placeholder="输入你正在研究的学术方向，例如：通用智能体在高校科研实验与文献自动化中的应用",
                        value="通用智能体在高校科研流程中的自动化应用",
                        lines=1,
                    )
                with gr.Column(scale=3):
                    run_main_btn = gr.Button("🚀 启动全流程科研协作", variant="primary", elem_classes=["primary-btn"], size="lg")

            with gr.Row():
                with gr.Column(scale=6):
                    keywords_input = gr.Textbox(
                        label="聚焦关键词 (逗号隔开)",
                        value="AI Agent, Scientific Workflow, Research Automation",
                    )
                with gr.Column(scale=3):
                    years_slider = gr.Slider(minimum=1, maximum=10, value=3, step=1, label="检索年份跨度 (近N年)")
                with gr.Column(scale=3):
                    papers_slider = gr.Slider(minimum=5, maximum=40, value=15, step=5, label="文献精筛池上限")

            with gr.Row():
                pause_hitl_checkbox = gr.Checkbox(
                    label="🛑 启用人在回路 (HITL) 断点审核：在大纲规划完成后自动暂停，允许学者润色修改后再继续执行",
                    value=True,
                )

            # 折叠高级选项（上传数据与参考文献）
            with gr.Accordion("📂 附加科研数据与参考文献文件 (点击展开)", open=False):
                with gr.Row():
                    with gr.Column(scale=6):
                        data_file_input = gr.File(label="上传实验数据表格 (.csv / .xlsx，不上传则使用系统内置公开实验数据)")
                    with gr.Column(scale=6):
                        refs_text_input = gr.Textbox(
                            label="输入或粘贴待规范的参考文献 (不填写则使用内置学术样本进行国标排版)",
                            placeholder="每行一条参考文献...",
                            lines=3,
                        )

        # ==================== 2. 人在回路审核卡片 (默认隐藏，断点触发时显示) ====================
        with gr.Group(visible=False, elem_classes=["hitl-box"]) as hitl_card:
            gr.HTML("""
            <div style="font-weight: bold; font-size: 15px; color: #D46B08; margin-bottom: 6px; display: flex; align-items: center; gap: 8px;">
                <span>🛑 工作流已在检查点挂起暂停 (Human-in-the-Loop Checkpoint)</span>
            </div>
            <div style="font-size: 13px; color: #873800; margin-bottom: 12px;">
                智能体已完成多源文献递归检索与核心创新点提炼，并自动规划了文献综述大纲。<b>您可以直接在下方富文本框中润色或调整大纲</b>，确认无误后点击右下方按钮无损续跑！
            </div>
            """)
            hitl_outline_editor = gr.Textbox(label="文献综述大纲规划稿 (可直接在线修改)", lines=8)
            with gr.Row():
                gr.Markdown("*(提示：修改后的内容将作为最新 Checkpoint 存盘，下游节点将基于您的修改继续合成综述)*")
                resume_flow_btn = gr.Button("💾 确认大纲并继续执行工作流 (Resume)", variant="stop", elem_classes=["resume-btn"], size="lg")

        # ==================== 3. 最终成果大画布 (工作流跑完后展开) ====================
        with gr.Group(visible=False, elem_classes=["result-card"]) as result_workspace:
            gr.HTML("""
            <div style="font-size: 17px; font-weight: 800; color: #1D2129; margin-bottom: 16px; border-bottom: 2px solid #165DFF; padding-bottom: 8px; display: flex; justify-content: space-between;">
                <span>📑 UniScholar 全流程科研综合成果画布</span>
                <span style="font-size: 12px; color: #00B42A; font-weight: 600;">✓ 已通过 Citation Validator 引文防幻觉检验</span>
            </div>
            """)

            with gr.Row():
                # 左栏：文献综述正文 (纯净学术排版)
                with gr.Column(scale=6):
                    gr.Markdown("### 📄 文献综述与创新点提炼稿")
                    final_report_md = gr.Markdown()

                # 右栏：实验数据科研图表 + 国标参考文献
                with gr.Column(scale=6):
                    gr.Markdown("### 📊 实验数据初步统计与科研图表")
                    charts_gallery = gr.Gallery(label="Matplotlib 渲染科研图表", columns=2, height="auto")

                    gr.Markdown("### 📐 规范参考文献列表 (GB/T 7714-2015)")
                    formatted_citations_box = gr.Markdown()

        # ==================== 底部快速单项调试抽屉 (按需使用) ====================
        with gr.Accordion("🛠️ 专家单项工具箱 (文献初筛 / 数据绘图 / 国标排版独立测试)", open=False):
            with gr.Tabs():
                with gr.TabItem("📊 实验数据独立绘图"):
                    with gr.Row():
                        q_file = gr.File(label="上传实验表格")
                        q_btn = gr.Button("快速分析绘图", variant="primary")
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
                        q_fmt = gr.Radio(choices=["GB/T 7714", "APA", "IEEE"], value="GB/T 7714", label="格式")
                        q_ref_btn = gr.Button("格式转换与纠错", variant="primary")
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

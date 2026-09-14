"""
UniScholar (联智学者) 可视化科研智能体 WebUI
面向大创赛产业赛道（中国联通命题）：基于通用智能体工作流的高校科研全流程自动化系统。
支持 DAG 流程可视化、人在回路断点干预（暂停/修改/续跑）、文件上传与四大核心功能独立演示。
"""

import io
import json
import logging
import os
import sys

# 避免控制台编码问题
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import gradio as gr
import pandas as pd

from agents.data_agent import DataAgent
from agents.literature_agent import LiteratureAgent
from agents.reference_agent import ReferenceAgent
from agents.review_agent import PaperFeature, ReviewAgent
from core.workflow_engine import WorkflowEngine, WorkflowStatus, WorkflowStep
from offline_demo.demo_data import (
    get_offline_features,
    get_offline_outline,
    get_offline_papers,
    get_offline_review_draft,
    get_sample_experiment_csv,
    get_sample_references_text,
)

logger = logging.getLogger("UniScholar.WebUI")

engine = WorkflowEngine()
lit_agent = LiteratureAgent()
rev_agent = ReviewAgent()
data_agent = DataAgent()
ref_agent = ReferenceAgent()

# 导出符合元景标准的工作流配置
engine.generate_wanwu_workflow_config()

# 全局内存中的当前任务状态
current_active_task_id = None


def get_step_status_html(current_step: str, status: str) -> str:
    """生成科技感现代 DAG 流程状态可视化组件"""
    steps = [
        ("1. 文献递归检索", WorkflowStep.LITERATURE_RETRIEVAL.value),
        ("2. 核心要素抽取", WorkflowStep.FEATURE_EXTRACTION.value),
        ("3. 综述大纲规划 (HITL)", WorkflowStep.OUTLINE_GENERATION.value),
        ("4. 综述正文合成", WorkflowStep.REVIEW_SYNTHESIS.value),
        ("5. 实验统计绘图", WorkflowStep.DATA_ANALYSIS.value),
        ("6. 参考文献国标", WorkflowStep.REFERENCE_FORMAT.value),
    ]

    badges = []
    for name, step_val in steps:
        if status == WorkflowStatus.COMPLETED.value:
            badge_class = "background: #2e7d32; color: white;"  # 完成 绿色
            icon = "✓"
        elif step_val == current_step:
            if status == WorkflowStatus.PAUSED.value:
                badge_class = "background: #ed6c02; color: white; border: 2px solid #ff9800;"  # 暂停 橙色
                icon = "⏸️"
            elif status == WorkflowStatus.RUNNING.value:
                badge_class = "background: #0288d1; color: white; animation: pulse 1.5s infinite;"  # 运行 蓝色
                icon = "⏳"
            else:
                badge_class = "background: #e0e0e0; color: #616161;"
                icon = "○"
        elif current_step in [s[1] for s in steps] and steps.index((name, step_val)) < [s[1] for s in steps].index(current_step):
            badge_class = "background: #2e7d32; color: white;"  # 已走过 绿色
            icon = "✓"
        else:
            badge_class = "background: #f5f5f5; color: #9e9e9e;"
            icon = "○"

        badges.append(
            f'<div style="padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; {badge_class}">'
            f'{icon} {name}</div>'
        )

    dag_html = f"""
    <div style="background: #ffffff; padding: 16px 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); margin-bottom: 15px;">
        <div style="font-size: 13px; font-weight: bold; color: #37474f; margin-bottom: 10px; display: flex; justify-content: space-between;">
            <span>🧭 通用智能体工作流执行拓扑图 (StateGraph DAG Trace)</span>
            <span style="color: #0288d1;">当前状态: <b>{status}</b></span>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
            {' <span style="color: #90a4ae; font-weight: bold;">➔</span> '.join(badges)}
        </div>
    </div>
    """
    return dag_html


# ==================== Tab 1: 全流程科研工作流执行与断点交互 ====================
def on_start_full_pipeline(
    query, keywords_str, years, max_papers, data_file, raw_refs, pause_at_outline
):
    global current_active_task_id

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    task_params = {
        "query": query,
        "keywords": keywords,
        "years": int(years),
        "max_papers": int(max_papers),
    }

    state = engine.create_task(task_params)
    current_active_task_id = state.task_id

    # 1. 检索
    state.status = WorkflowStatus.RUNNING
    state.current_step = WorkflowStep.LITERATURE_RETRIEVAL
    engine.log(state, "WebUI 触发: 启动节点 1 文献递归检索")
    lit_res = lit_agent.run(query=query, keywords=keywords, years=int(years), max_papers=int(max_papers))
    state.data["literature_pool"] = lit_res["papers"]
    state.completed_steps.append("literature_retrieval")
    engine.save_checkpoint(state)

    # 2. 抽取
    state.current_step = WorkflowStep.FEATURE_EXTRACTION
    engine.log(state, "启动节点 2 文献核心要素抽取")
    features = rev_agent.batch_extract(lit_res["papers"])
    state.data["extracted_features"] = [f.model_dump() for f in features]
    state.completed_steps.append("feature_extraction")
    engine.save_checkpoint(state)

    # 3. 大纲规划
    state.current_step = WorkflowStep.OUTLINE_GENERATION
    engine.log(state, "启动节点 3 综述大纲规划")
    outline_md = rev_agent.generate_review_outline(query, features)
    state.data["review_outline"] = outline_md
    state.completed_steps.append("outline_generation")
    engine.save_checkpoint(state)

    dag_html = get_step_status_html(state.current_step.value, state.status.value)

    if pause_at_outline:
        # 触发断点暂停！等待人在回路干预
        engine.pause_task(state.task_id, reason="人在回路：已生成综述大纲，等待用户审查编辑")
        state = engine.load_checkpoint(state.task_id)
        dag_html_paused = get_step_status_html(state.current_step.value, state.status.value)
        log_text = "\n".join(state.logs[-8:])
        return (
            dag_html_paused,
            gr.update(visible=True),  # 显示人工干预面板
            outline_md,               # 把大纲传给人工编辑框
            f"🛑 工作流已在节点 3 触发断点暂停！\n任务 ID: {state.task_id}\n请在下方编辑审查大纲，确认后点击【保存修改并继续执行】。",
            "",
            [],
            log_text,
        )

    # 若未勾选暂停，直接跑完后续
    return finish_pipeline_from_outline(state.task_id, outline_md, data_file, raw_refs)


def finish_pipeline_from_outline(task_id, modified_outline, data_file, raw_refs):
    """从大纲节点继续执行剩余所有步骤"""
    state = engine.load_checkpoint(task_id)
    if not state:
        return "", gr.update(visible=False), "", "任务不存在", "", [], ""

    # 保存人工修改后的大纲
    state.data["review_outline"] = modified_outline
    state.status = WorkflowStatus.RUNNING
    engine.log(state, "接收人工修改后的大纲，继续执行后续任务")

    # 4. 综述正文合成
    state.current_step = WorkflowStep.REVIEW_SYNTHESIS
    engine.log(state, "启动节点 4 综述正文合成与引文防幻觉检验")
    features_objs = [PaperFeature(**f) for f in state.data.get("extracted_features", [])]
    review_draft = rev_agent.generate_review_draft(
        topic=state.params.get("query", "科研综述"),
        outline=modified_outline,
        features=features_objs,
    )
    state.data["review_draft"] = review_draft
    state.completed_steps.append("review_synthesis")
    engine.save_checkpoint(state)

    # 5. 实验数据统计
    state.current_step = WorkflowStep.DATA_ANALYSIS
    engine.log(state, "启动节点 5 实验数据统计与科研绘图")
    if data_file is not None and hasattr(data_file, "name"):
        csv_input = data_file.name
    else:
        csv_input = get_sample_experiment_csv()

    data_res = data_agent.run(csv_input, task_id=state.task_id)
    state.data["data_analysis_report"] = data_res["report_markdown"]
    state.data["generated_charts"] = data_res["charts"]
    state.completed_steps.append("data_analysis")
    engine.save_checkpoint(state)

    # 6. 参考文献国标校对
    state.current_step = WorkflowStep.REFERENCE_FORMAT
    engine.log(state, "启动节点 6 参考文献 GB/T 7714 国标排版")
    ref_input = raw_refs.strip() if raw_refs and raw_refs.strip() else get_sample_references_text()
    ref_res = ref_agent.run(ref_input, target_format="GB/T 7714")
    state.data["formatted_references"] = ref_res["formatted_text"]
    state.completed_steps.append("reference_format")

    # 标记全部完成
    state.status = WorkflowStatus.COMPLETED
    state.current_step = WorkflowStep.COMPLETED
    engine.log(state, "🎉 全流程任务顺利完成！")
    engine.save_checkpoint(state)

    # 组装最终研报
    final_report = f"""# 📑 UniScholar 科研全流程综合成果报告
> 任务 ID: `{state.task_id}` | 状态: `COMPLETED` | 检查点已持久化存盘

{state.data.get("review_draft", "")}

---

{state.data.get("data_analysis_report", "")}

---

## 参考文献 (规范 GB/T 7714-2015 格式)
{state.data.get("formatted_references", "")}
"""

    dag_html = get_step_status_html(state.current_step.value, state.status.value)
    log_text = "\n".join(state.logs[-10:])

    return (
        dag_html,
        gr.update(visible=False),  # 隐藏人工干预面板
        modified_outline,
        f"✅ 任务 {task_id} 全流程执行完毕！",
        final_report,
        data_res["charts"],
        log_text,
    )


# ==================== 构建 Gradio 界面 ====================
def build_ui():
    custom_css = """
    .gradio-container { font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }
    .main-title { text-align: center; margin: 10px 0 5px 0; color: #1a237e; font-weight: bold; }
    .sub-title { text-align: center; color: #546e7a; font-size: 14px; margin-bottom: 15px; }
    """

    with gr.Blocks(title="UniScholar - 通用AI科研智能体应用系统", css=custom_css) as demo:
        gr.HTML("""
        <div class="main-title"><h1>🎓 UniScholar (联智学者) - 通用AI科研智能体应用系统</h1></div>
        <div class="sub-title">面向大创赛产业赛道（中国联通浙江省分公司命题）：基于通用智能体工作流的高校科研全流程自动化辅助平台</div>
        """)

        with gr.Tabs():
            # ==================== TAB 1: 全流程科研工作流 ====================
            with gr.TabItem("🌟 全流程科研工作流 (带断点续跑与人在回路)"):
                dag_box = gr.HTML(get_step_status_html("init", "IDLE"))

                with gr.Row():
                    with gr.Column(scale=4):
                        gr.Markdown("### ⚙️ 任务初始参数配置")
                        query_input = gr.Textbox(
                            label="研究方向 / 核心主题",
                            value="通用智能体在高校科研流程中的自动化应用",
                            placeholder="例如：基于深度学习的多模态文献分析",
                        )
                        keywords_input = gr.Textbox(
                            label="检索关键词 (逗号分隔)",
                            value="AI Agent, Workflow, Scientific Automation",
                        )
                        with gr.Row():
                            years_slider = gr.Slider(minimum=1, maximum=10, value=3, step=1, label="检索年份跨度 (年)")
                            papers_slider = gr.Slider(minimum=5, maximum=50, value=15, step=5, label="精选文献上限 (篇)")

                        pause_checkbox = gr.Checkbox(
                            label="🛑 开启人在回路断点 (在综述大纲生成后暂停，允许人工编辑修改)",
                            value=True,
                        )

                        with gr.Accordion("📂 实验数据与参考文献附加文件 (可选)", open=False):
                            data_file_input = gr.File(label="上传实验数据表格 (.csv / .xlsx)")
                            refs_text_input = gr.Textbox(
                                label="粘贴原始参考文献列表 (用于自动纠错排版)",
                                placeholder="每行一条参考文献...",
                                lines=4,
                            )

                        start_btn = gr.Button("🚀 启动全流程科研智能体工作流", variant="primary", size="lg")

                        # 人在回路干预面板 (默认隐藏，暂停时显示)
                        with gr.Group(visible=False) as hitl_panel:
                            gr.Markdown("### ✏️ 人在回路干预面板 (Human-in-the-Loop)")
                            gr.Markdown("> 工作流已自动在此检查点暂停。您可以直接在下方修改提炼出的大纲，确认后点击下方按钮继续。")
                            editable_outline = gr.Textbox(label="编辑文献综述大纲", lines=8)
                            resume_btn = gr.Button("💾 保存修改并继续执行工作流 (Resume)", variant="stop", size="lg")

                    with gr.Column(scale=6):
                        status_msg = gr.Markdown("### 📌 状态提示: 等待启动")
                        log_display = gr.Textbox(label="工作流状态机实时执行日志 (Execution Trace)", lines=5)

                        with gr.Tabs():
                            with gr.TabItem("📑 综合科研报告预览"):
                                report_output = gr.Markdown(label="最终成果报告")
                            with gr.TabItem("📊 自动生成的科研图表"):
                                gallery_output = gr.Gallery(label="科研可视化图表 (Matplotlib渲染)", columns=2, height="auto")

                # 事件绑定
                start_btn.click(
                    fn=on_start_full_pipeline,
                    inputs=[
                        query_input,
                        keywords_input,
                        years_slider,
                        papers_slider,
                        data_file_input,
                        refs_text_input,
                        pause_checkbox,
                    ],
                    outputs=[
                        dag_box,
                        hitl_panel,
                        editable_outline,
                        status_msg,
                        report_output,
                        gallery_output,
                        log_display,
                    ],
                )

                resume_btn.click(
                    fn=lambda outline, dfile, refs: finish_pipeline_from_outline(current_active_task_id, outline, dfile, refs),
                    inputs=[editable_outline, data_file_input, refs_text_input],
                    outputs=[
                        dag_box,
                        hitl_panel,
                        editable_outline,
                        status_msg,
                        report_output,
                        gallery_output,
                        log_display,
                    ],
                )

            # ==================== TAB 2: 文献递归检索与初筛 ====================
            with gr.TabItem("📚 文献递归检索与筛选 (功能 1 独立测试)"):
                with gr.Row():
                    with gr.Column(scale=4):
                        t2_query = gr.Textbox(label="研究方向", value="通用智能体科研自动化")
                        t2_kw = gr.Textbox(label="关键词", value="Agent, Scientific Workflow")
                        t2_btn = gr.Button("🔍 检索并递归过滤低相关文献", variant="primary")
                    with gr.Column(scale=6):
                        t2_summary = gr.Markdown("检索结果概览")
                        t2_table = gr.Dataframe(label="精准文献池", headers=["标题", "年份", "引用量", "相关度分值", "DOI"])

                def run_t2(q, kw):
                    res = lit_agent.run(query=q, keywords=[k.strip() for k in kw.split(",")])
                    summary_text = f"**抓取总数**: `{res['total_fetched']}` 篇 | **精选保留**: `{res['selected_count']}` 篇 | **过滤淘汰**: `{res['filtered_out_count']}` 篇"
                    rows = [
                        [p["title"][:50] + "...", p["publication_year"], p["cited_by_count"], p["relevance_score"], p.get("doi", "N/A")]
                        for p in res["papers"]
                    ]
                    return summary_text, rows

                t2_btn.click(fn=run_t2, inputs=[t2_query, t2_kw], outputs=[t2_summary, t2_table])

            # ==================== TAB 3: 实验数据初步统计与科研绘图 ====================
            with gr.TabItem("📊 实验数据初步统计与可视化 (功能 3 独立测试)"):
                with gr.Row():
                    with gr.Column(scale=4):
                        gr.Markdown("上传实验结果表格（CSV 或 Excel），智能体自动计算均值、方差、分位数，标出异常值并绘制科研图表。")
                        t3_file = gr.File(label="上传实验数据表格")
                        t3_use_sample_btn = gr.Button("📥 加载内置公开科研实验样本数据")
                        t3_csv_text = gr.Textbox(label="或直接粘贴 CSV 文本", lines=6, placeholder="Epoch,Train_Loss,Val_Loss,Accuracy...")
                        t3_btn = gr.Button("📈 开始统计分析与绘制科研图表", variant="primary")
                    with gr.Column(scale=6):
                        t3_report = gr.Markdown(label="统计分析与异常值报告")
                        t3_gallery = gr.Gallery(label="自动生成的科研图表", columns=2)

                t3_use_sample_btn.click(fn=lambda: get_sample_experiment_csv(), outputs=[t3_csv_text])

                def run_t3(file_obj, text_content):
                    src = file_obj.name if file_obj is not None else text_content
                    if not src:
                        src = get_sample_experiment_csv()
                    res = data_agent.run(src)
                    return res["report_markdown"], res["charts"]

                t3_btn.click(fn=run_t3, inputs=[t3_file, t3_csv_text], outputs=[t3_report, t3_gallery])

            # ==================== TAB 4: 参考文献 GB/T 7714 格式化 ====================
            with gr.TabItem("📑 参考文献国标自动格式化与校对 (功能 4 独立测试)"):
                with gr.Row():
                    with gr.Column(scale=5):
                        gr.Markdown("输入任何杂乱格式的参考文献，智能体将按照 **GB/T 7714-2015** 规范排版纠错，并支持一键切换。")
                        t4_input = gr.Textbox(label="原始参考文献文本", lines=8, value=get_sample_references_text())
                        t4_format_radio = gr.Radio(
                            choices=["GB/T 7714", "APA", "IEEE"],
                            value="GB/T 7714",
                            label="目标引用格式",
                        )
                        t4_btn = gr.Button("✨ 智能排版与质量校对", variant="primary")
                    with gr.Column(scale=5):
                        t4_output = gr.Textbox(label="规范排版结果 (可直接复制)", lines=8)
                        t4_audit = gr.Markdown(label="校对与缺项纠错报告")

                def run_t4(text, fmt):
                    res = ref_agent.run(text, target_format=fmt)
                    audit_md = f"**审计结果**: 共解析 `{res['total_items']}` 条条目，发现 `{res['audit_warnings_count']}` 处潜在规范瑕疵：\n\n"
                    if res["audit_reports"]:
                        for r in res["audit_reports"]:
                            audit_md += f"- **第 {r['index']} 条**：{', '.join(r['warnings'])}\n"
                    else:
                        audit_md += "✅ 所有参考文献条目要素完整，符合学术规范！"
                    return res["formatted_text"], audit_md

                t4_btn.click(fn=run_t4, inputs=[t4_input, t4_format_radio], outputs=[t4_output, t4_audit])

            # ==================== TAB 5: 联通元景万悟工作流配置与日志 ====================
            with gr.TabItem("📜 流程配置文件与调用日志 (赛题交付物审查)"):
                with gr.Row():
                    with gr.Column(scale=5):
                        gr.Markdown("### 📄 通用智能体流程配置文件 (workflow_config.json)")
                        gr.Markdown("此文件对标中国联通元景万悟平台通用工作流规范，记录节点拓扑与工具调用定义。")
                        cfg_text = gr.Code(language="json", lines=20, value=json.dumps(engine.generate_wanwu_workflow_config(), ensure_ascii=False, indent=2))
                    with gr.Column(scale=5):
                        gr.Markdown("### 📝 通用智能体执行日志 (workflow_execution.log)")
                        gr.Markdown("记录状态机各节点触发、Checkpoint持久化与断点续跑的真实日志轨迹。")
                        def read_log():
                            if os.path.exists(engine.execution_log_path):
                                with open(engine.execution_log_path, "r", encoding="utf-8") as f:
                                    return f.read()
                            return "暂无执行日志"
                        log_box = gr.Code(language="markdown", lines=20, value=read_log())
                        refresh_log_btn = gr.Button("🔄 刷新最新日志")
                        refresh_log_btn.click(fn=read_log, outputs=[log_box])

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=False)

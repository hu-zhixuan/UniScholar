"""
UniScholar (联智学者) - 极简 Claude 暖雅学术科研工作台
面向大创赛产业赛道（中国联通《基于通用智能体的AI科研智能体应用开发》）。
采用 Anthropic Claude 标志性的暖雅学术美学（Warm Terracotta & Sand / Ivory），
采用原生 Gradio 组件双向数据流与人在回路（HITL）交互机制，
彻底清除浏览器暗色模式冲突，呈现呼吸感、极具人文科研质感的学术工作台。
"""

import html
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# 避免控制台乱码
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"), override=True)

# 强制本地 127.0.0.1 直连，防止 Windows 系统代理拦截 Gradio 启动与内部 API
os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
os.environ["no_proxy"] = "127.0.0.1,localhost,::1"

import gradio as gr

from agents.data_agent import DataAgent
from agents.intent_agent import IntentAgent
from agents.literature_agent import LiteratureAgent
from agents.reference_agent import ReferenceAgent
from agents.review_agent import PaperFeature, ReviewAgent
from utils.llm_client import LLMClient, clean_thinking_process
from core.workflow_engine import WorkflowEngine, WorkflowStatus, WorkflowStep
from offline_demo.demo_data import (
    get_sample_experiment_csv,
    get_sample_references_text,
)

logger = logging.getLogger("UniScholar.WebUI")

engine = WorkflowEngine()
intent_agent = IntentAgent()
lit_agent = LiteratureAgent()
rev_agent = ReviewAgent()
data_agent = DataAgent()
ref_agent = ReferenceAgent()


def render_claude_pipeline(current_step: str, status: str) -> str:
    """生成具有现代学术优雅质感（Slate Minimalist）的 DAG 编排流转状态"""
    steps = [
        ("00", "意图规划", WorkflowStep.INTENT_FORMULATION.value),
        ("01", "文献初筛", WorkflowStep.LITERATURE_RETRIEVAL.value),
        ("02", "要素萃取", WorkflowStep.FEATURE_EXTRACTION.value),
        ("03", "大纲推演", WorkflowStep.OUTLINE_GENERATION.value),
        ("04", "综述合成", WorkflowStep.REVIEW_SYNTHESIS.value),
        ("05", "实证统计", WorkflowStep.DATA_ANALYSIS.value),
        ("06", "引文校对", WorkflowStep.REFERENCE_FORMAT.value),
    ]

    step_keys = [s[2] for s in steps]
    is_idle = (
        status in ["IDLE", "idle", "READY", "ready", "init", ""]
        or current_step in ["init", "idle", None, ""]
        or status is None
    )
    is_all_completed = (status == WorkflowStatus.COMPLETED.value or current_step == "completed")

    if is_all_completed:
        cur_idx = len(steps)
    elif is_idle:
        cur_idx = -1
    else:
        cur_idx = step_keys.index(current_step) if current_step in step_keys else -1

    # 状态文案与进度
    if is_all_completed:
        pct = 100
        step_desc = "全流程科研成果已交付完毕"
        status_badge = '<span style="color: #059669; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #059669;"></span>已交付 · 100%</span>'
        bar_color = "linear-gradient(90deg, #059669 0%, #10B981 100%)"
        bar_shadow = "0 1px 4px rgba(16, 185, 129, 0.3)"
        pct_color = "#059669"
    elif is_idle or cur_idx == -1:
        pct = 0
        step_desc = "通用智能体集群就绪，等待科研任务输入"
        status_badge = '<span style="color: #64748B; font-weight: 500; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #94A3B8;"></span>就绪 · Ready</span>'
        bar_color = "#CBD5E1"
        bar_shadow = "none"
        pct_color = "#64748B"
    elif current_step == WorkflowStep.INTENT_FORMULATION.value:
        pct = 15
        step_desc = "正在解耦核心学术选题并规划跨源检索词策略"
        status_badge = '<span style="color: #2563EB; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #2563EB;"></span>执行中 · 15%</span>'
        bar_color = "linear-gradient(90deg, #1E293B 0%, #2563EB 100%)"
        bar_shadow = "0 1px 4px rgba(37, 99, 235, 0.3)"
        pct_color = "#2563EB"
    elif current_step == WorkflowStep.LITERATURE_RETRIEVAL.value:
        if status == WorkflowStatus.PAUSED.value:
            pct = 30
            step_desc = "候选文献池已就绪 · 人在回路断点等待学者遴选"
            status_badge = '<span style="color: #D97706; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #D97706;"></span>人在回路断点 · 30%</span>'
            bar_color = "linear-gradient(90deg, #B45309 0%, #F59E0B 100%)"
            bar_shadow = "0 1px 4px rgba(245, 158, 11, 0.3)"
            pct_color = "#D97706"
        else:
            pct = 28
            step_desc = "正在通过 OpenAlex 与 Europe PMC 跨源检索候选文献"
            status_badge = '<span style="color: #2563EB; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #2563EB;"></span>检索中 · 28%</span>'
            bar_color = "linear-gradient(90deg, #1E293B 0%, #2563EB 100%)"
            bar_shadow = "0 1px 4px rgba(37, 99, 235, 0.3)"
            pct_color = "#2563EB"
    elif current_step == WorkflowStep.FEATURE_EXTRACTION.value:
        pct = 45
        step_desc = "正在深度萃取核心文献的研究背景、方法论与微观结论"
        status_badge = '<span style="color: #2563EB; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #2563EB;"></span>要素萃取中 · 45%</span>'
        bar_color = "linear-gradient(90deg, #1E293B 0%, #2563EB 100%)"
        bar_shadow = "0 1px 4px rgba(37, 99, 235, 0.3)"
        pct_color = "#2563EB"
    elif current_step == WorkflowStep.OUTLINE_GENERATION.value:
        pct = 60
        step_desc = "正在推演领域专属新论文综述大纲三级架构"
        status_badge = '<span style="color: #2563EB; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #2563EB;"></span>大纲推演中 · 60%</span>'
        bar_color = "linear-gradient(90deg, #1E293B 0%, #2563EB 100%)"
        bar_shadow = "0 1px 4px rgba(37, 99, 235, 0.3)"
        pct_color = "#2563EB"
    elif current_step == WorkflowStep.REVIEW_SYNTHESIS.value:
        pct = 75
        step_desc = "正在合成学术综述全文框架并进行 Citation 防幻觉交叉核验"
        status_badge = '<span style="color: #2563EB; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #2563EB;"></span>初稿合成中 · 75%</span>'
        bar_color = "linear-gradient(90deg, #1E293B 0%, #2563EB 100%)"
        bar_shadow = "0 1px 4px rgba(37, 99, 235, 0.3)"
        pct_color = "#2563EB"
    elif current_step == WorkflowStep.DATA_ANALYSIS.value:
        pct = 88
        step_desc = "正在分析实验数据收敛趋势并绘制科研统计图表"
        status_badge = '<span style="color: #2563EB; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #2563EB;"></span>实证制图中 · 88%</span>'
        bar_color = "linear-gradient(90deg, #1E293B 0%, #2563EB 100%)"
        bar_shadow = "0 1px 4px rgba(37, 99, 235, 0.3)"
        pct_color = "#2563EB"
    elif current_step == WorkflowStep.REFERENCE_FORMAT.value:
        pct = 95
        step_desc = "正在执行 GB/T 7714-2015 格式标准化校对排版"
        status_badge = '<span style="color: #2563EB; font-weight: 600; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #2563EB;"></span>排版校对中 · 95%</span>'
        bar_color = "linear-gradient(90deg, #1E293B 0%, #2563EB 100%)"
        bar_shadow = "0 1px 4px rgba(37, 99, 235, 0.3)"
        pct_color = "#2563EB"
    else:
        pct = 0
        step_desc = "通用智能体集群就绪，等待科研任务输入"
        status_badge = '<span style="color: #64748B; font-weight: 500; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;"><span style="width: 6px; height: 6px; border-radius: 50%; background: #94A3B8;"></span>就绪 · Ready</span>'
        bar_color = "#CBD5E1"
        bar_shadow = "none"
        pct_color = "#64748B"

    # 生成 7 个节点的精简里程碑条 (Milestone Stepper)
    node_items = []
    for idx, (num, name, key) in enumerate(steps):
        is_completed = (is_all_completed or (cur_idx >= 0 and idx < cur_idx))
        is_current = (cur_idx >= 0 and idx == cur_idx and not is_all_completed)
        is_paused = (is_current and status == WorkflowStatus.PAUSED.value)

        if is_completed:
            circle_bg = "#0F172A"
            circle_color = "#FFFFFF"
            circle_border = "1px solid #0F172A"
            content = "✓"
            label_color = "#0F172A"
            label_weight = "600"
            sub_tag = "已完成"
            sub_color = "#64748B"
        elif is_current:
            if is_paused:
                circle_bg = "#FFFBEB"
                circle_color = "#D97706"
                circle_border = "1.5px solid #D97706"
                content = num
                label_color = "#B45309"
                label_weight = "700"
                sub_tag = "人在回路"
                sub_color = "#D97706"
            else:
                circle_bg = "#0F172A"
                circle_color = "#FFFFFF"
                circle_border = "1px solid #0F172A"
                content = num
                label_color = "#0F172A"
                label_weight = "700"
                sub_tag = "执行中"
                sub_color = "#2563EB"
        else:
            circle_bg = "#F8FAFC"
            circle_color = "#94A3B8"
            circle_border = "1px solid #E2E8F0"
            content = num
            label_color = "#64748B"
            label_weight = "500"
            sub_tag = "待执行"
            sub_color = "#94A3B8"

        connector_html = f'<div style="flex: 1; height: 1.5px; {"background: #0F172A;" if (idx <= cur_idx or status == WorkflowStatus.COMPLETED.value) else "background: #E2E8F0;"} margin: 0 4px; align-self: flex-start; margin-top: 12px;"></div>' if idx > 0 else ""

        node_items.append(f"""{connector_html}
        <div style="display: flex; flex-direction: column; align-items: center; text-align: center; min-width: 68px;">
            <div style="width: 24px; height: 24px; border-radius: 50%; background: {circle_bg}; color: {circle_color}; border: {circle_border}; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; font-family: ui-monospace, SFMono-Regular, monospace; margin-bottom: 6px;">
                {content}
            </div>
            <div style="font-size: 12px; font-weight: {label_weight}; color: {label_color}; white-space: nowrap; line-height: 1.3;">
                {name}
            </div>
            <div style="font-size: 10px; color: {sub_color}; margin-top: 2px; white-space: nowrap;">
                {sub_tag}
            </div>
        </div>""")

    stepper_html = "".join(node_items)

    return f"""
    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 16px 20px 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 13.5px; font-weight: 700; color: #0F172A; letter-spacing: -0.2px;">工作流编排轨迹 (Workflow Pipeline)</span>
                <span style="font-size: 11px; font-weight: 500; color: #475569; background: #F1F5F9; padding: 2px 8px; border-radius: 4px; border: 1px solid #E2E8F0;">元景万悟 v2.0 DAG</span>
            </div>
            <div>{status_badge}</div>
        </div>
        <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; padding: 4px 6px;">
            {stepper_html}
        </div>
        <!-- 当前动态与醒目进度条卡片 (新增进度条条) -->
        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 9px; padding: 12px 16px;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 9px;">
                <div style="font-size: 12.5px; color: #475569; display: flex; align-items: center; gap: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    <span style="font-weight: 700; color: #0F172A; display: inline-flex; align-items: center; gap: 5px;">
                        <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: {pct_color};"></span>
                        当前动态:
                    </span>
                    <span style="color: #334155; font-weight: 500;">{step_desc}</span>
                </div>
                <div style="font-size: 13px; font-weight: 700; color: {pct_color}; font-family: ui-monospace, SFMono-Regular, monospace; white-space: nowrap;">
                    {pct}%
                </div>
            </div>
            <!-- 醒目进度条条 (Progress Bar Track & Fill) -->
            <div style="height: 8px; width: 100%; background: #E2E8F0; border-radius: 999px; overflow: hidden; position: relative; box-shadow: inset 0 1px 2px rgba(0,0,0,0.06);">
                <div style="height: 100%; width: {pct}%; background: {bar_color}; border-radius: 999px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: {bar_shadow};"></div>
            </div>
        </div>
    </div>
    """.replace('\n', ' ').strip()


# ==================== 原生 Gradio 选项与实时状态渲染 ====================
def format_paper_choices(candidate_papers: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """将候选文献池转换为排版严谨、支持自由划选复制的原生 CheckboxGroup 选项列表"""
    choices = []
    for idx, p in enumerate(candidate_papers):
        title = str(p.get("title") or f"文献 {idx+1}")
        year = p.get("publication_year") or 2024
        source = str(p.get("source") or "OpenAlex")
        score = int(float(p.get("relevance_score", 0.8)) * 100)
        summary = str(p.get("chinese_summary") or p.get("abstract") or "围绕该课题开展的学术实证研究与机理解析。").strip()
        if len(summary) > 130:
            summary = summary[:128] + "..."
        label = f"[{idx+1}] 《{title}》 ({year} · {source} · 相关度 {score}%)\n   要点摘要: {summary}"
        choices.append((label, str(idx)))
    return choices


def render_selection_badge(selected_count: int, total_count: int = 20) -> str:
    """生成简洁优雅的学术文献精选计数状态徽章"""
    if total_count == 0:
        badge_style = "background: #F8FAFC; color: #64748B; border: 1px solid #E2E8F0;"
        tip = "待候选文献检索就绪后将在此显示遴选配比"
    elif selected_count == 0:
        badge_style = "background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA;"
        tip = "未选中文献 · 请至少勾选 1 篇以支撑后续推演"
    elif 5 <= selected_count <= 8:
        badge_style = "background: #F0FDF4; color: #166534; border: 1px solid #BBF7D0;"
        tip = "已达到最佳学术论据密度配比 (建议 5~8 篇)"
    elif selected_count < 5:
        badge_style = "background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A;"
        tip = f"已选 {selected_count} 篇 · 建议 5~8 篇 (当前已可启动)"
    else:
        badge_style = "background: #F8FAFC; color: #1E293B; border: 1px solid #CBD5E1;"
        tip = f"已选 {selected_count} 篇 · 涵盖多组交叉论据 (建议 5~8 篇)"

    badge_html = (
        f'<div style="{badge_style} border-radius: 8px; padding: 6px 14px; display: inline-flex; align-items: center; gap: 8px; font-family: inherit; min-width: 260px; white-space: nowrap;">'
        f'<div style="display: flex; flex-direction: column;">'
        f'<div style="font-size: 12.5px; font-weight: 700; display: flex; align-items: baseline; gap: 4px;">'
        f'<span>已精选核心文献:</span>'
        f'<span style="font-size: 15px; font-family: ui-monospace, SFMono-Regular, monospace;">{selected_count}</span>'
        f'<span style="font-size: 11px; font-weight: normal; opacity: 0.85;">/ {total_count} 篇</span>'
        f'</div>'
        f'<div style="font-size: 10.5px; opacity: 0.85; margin-top: 1px;">{tip}</div>'
        f'</div></div>'
    )
    return badge_html.replace('\n', ' ').strip()


def parse_selected_indices(items: Any, total_count: int) -> List[int]:
    """从 Gradio CheckboxGroup 传入的各类形态（数字索引字符串、整数、[序号]标签、论文标题）中提取有效 0-based 索引"""
    if not items or total_count <= 0:
        return []
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = [x.strip() for x in items.split(",") if x.strip()]
    if not isinstance(items, (list, tuple, set)):
        items = [items]

    clean = []
    for item in items:
        # 1. 尝试直接作为数字索引转换
        try:
            val = int(item)
            if 0 <= val < total_count and val not in clean:
                clean.append(val)
                continue
        except (ValueError, TypeError):
            pass

        # 2. 尝试从 [1] 格式的标签字符串中提取 1-based 序号
        item_str = str(item).strip()
        match = re.match(r"^\[(\d+)\]", item_str)
        if match:
            val = int(match.group(1)) - 1
            if 0 <= val < total_count and val not in clean:
                clean.append(val)
                continue

    return clean


# ==================== 工具栏动作处理函数 ====================
def select_top6_action(candidate_pool: List[Dict[str, Any]]):
    pool = candidate_pool or []
    total = len(pool)
    top_n = min(6, total)
    selected = [str(i) for i in range(top_n)]
    return selected, render_selection_badge(top_n, total)


def select_all_action(candidate_pool: List[Dict[str, Any]]):
    pool = candidate_pool or []
    total = len(pool)
    selected = [str(i) for i in range(total)]
    return selected, render_selection_badge(total, total)


def clear_all_action(candidate_pool: List[Dict[str, Any]]):
    pool = candidate_pool or []
    total = len(pool)
    return [], render_selection_badge(0, total)


def invert_selection_action(current_selected: List[str], candidate_pool: List[Dict[str, Any]]):
    pool = candidate_pool or []
    total = len(pool)
    curr_indices = set(parse_selected_indices(current_selected, total))
    new_selected = [str(i) for i in range(total) if i not in curr_indices]
    return new_selected, render_selection_badge(len(new_selected), total)


def on_selection_change_action(current_selected: List[str], candidate_pool: List[Dict[str, Any]]):
    pool = candidate_pool or []
    total = len(pool)
    clean = parse_selected_indices(current_selected, total)
    return render_selection_badge(len(clean), total)


# ==================== 工作流辅助格式化 ====================
def format_literature_table(papers):
    rows = []
    for idx, p in enumerate(papers, 1):
        rows.append([
            idx,
            p.get("title", "未命名文献"),
            p.get("publication_year", 2024),
            p.get("cited_by_count", 0),
            f"{int(float(p.get('relevance_score', 0.8)) * 100)}%",
            p.get("source", "OpenAlex"),
        ])
    return rows


def format_features_markdown(features):
    if not features:
        return "*暂无抽取要素*"
    lines = []
    for idx, f in enumerate(features, 1):
        title = f.get('title') if isinstance(f, dict) else getattr(f, 'title', '未知文献')
        year = f.get('publication_year', 2024) if isinstance(f, dict) else getattr(f, 'publication_year', 2024)
        bg = f.get('background', '未注明') if isinstance(f, dict) else getattr(f, 'background', '未注明')
        inno_raw = f.get('core_innovations', []) if isinstance(f, dict) else getattr(f, 'core_innovations', [])
        inno = '；'.join(inno_raw) if isinstance(inno_raw, list) else str(inno_raw or '未注明')
        meth = f.get('methodology', '未注明') if isinstance(f, dict) else getattr(f, 'methodology', '未注明')
        conc_raw = f.get('main_conclusions', []) if isinstance(f, dict) else getattr(f, 'main_conclusions', [])
        conc = '；'.join(conc_raw) if isinstance(conc_raw, list) else str(conc_raw or '未注明')

        lines.append(f"#### 📄 核心文献 {idx}：《{title}》({year})")
        lines.append(f"- **研究背景与动机**：{bg}")
        lines.append(f"- **核心创新机制**：{inno}")
        lines.append(f"- **研究方法与技术范式**：{meth}")
        lines.append(f"- **主要实证结论**：{conc}")
        lines.append("")
    return "\n".join(lines)


# ==================== 工作流事件调度 (人在回路与全流程贯通) ====================
def start_research_flow(
    query,
    keywords_str,
    years,
    max_papers,
    data_file,
    refs_text,
    *unused_args,
    auto_run=False,
    progress=gr.Progress(track_tqdm=True),
):
    if not query.strip():
        query = "通用智能体在高校科研流程中的自动化应用"

    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    candidate_target = max(20, int(max_papers))

    state = engine.create_task({
        "query": query,
        "keywords": keywords,
        "years": int(years),
        "max_papers": candidate_target,
    })

    # Frame 0: 启动，立即推进至节点 0（意图规划 15%），前端 1234567 流程与长条动态即刻亮起响应！
    pipeline_html = render_claude_pipeline(WorkflowStep.INTENT_FORMULATION.value, WorkflowStatus.RUNNING.value)
    yield (
        pipeline_html,
        gr.update(visible=False),
        gr.update(visible=False),
        "",
        gr.update(choices=[], value=[]),
        [],
        gr.update(visible=False),
        "",
        [],
        "",
        "",
        [],
        "",
        "",
        state.task_id,
        [],
    )

    # 0. 意图理解与规划 (LLM Think First)
    progress(0.05, desc="[0/7] 学术意图规划：正在解耦核心科学选题与跨学科关键词...")
    state.status = WorkflowStatus.RUNNING
    state.current_step = WorkflowStep.INTENT_FORMULATION
    plan = intent_agent.formulate(query=query, user_keywords=keywords, years=int(years), max_papers=candidate_target)
    state.data["intent_plan"] = plan.model_dump()
    state.completed_steps.append("intent_formulation")
    engine.save_checkpoint(state)

    # Frame 1: 节点 0 完成，推进至节点 1（文献初筛 28%），动态更新下方长条进度与圆圈节点
    pipeline_html = render_claude_pipeline(WorkflowStep.LITERATURE_RETRIEVAL.value, WorkflowStatus.RUNNING.value)
    yield (
        pipeline_html,
        gr.update(visible=False),
        gr.update(visible=False),
        "",
        gr.update(choices=[], value=[]),
        [],
        gr.update(visible=False),
        "",
        [],
        "",
        "",
        [],
        "",
        "",
        state.task_id,
        [],
    )

    # 1. 跨源检索候选文献池 (~20篇)
    progress(0.18, desc="[1/7] 文献初筛：正在通过 OpenAlex 与 Europe PMC 跨源检索候选文献池 (~20篇)...")
    state.current_step = WorkflowStep.LITERATURE_RETRIEVAL
    lit_res = lit_agent.run(
        query=query,
        keywords=keywords,
        years=int(years),
        max_papers=candidate_target,
        search_queries=plan.search_queries,
        filter_keywords=plan.filter_keywords,
    )
    progress(0.28, desc="[1/7] 候选文献已检索就绪，正在生成学术中文要点索引表...")
    candidate_papers = lit_res["papers"]
    state.data["candidate_pool"] = candidate_papers
    state.data["literature_pool"] = candidate_papers
    state.completed_steps.append("literature_retrieval")
    engine.save_checkpoint(state)

    # 格式化候选文献选项列表
    default_selected_indices = [str(i) for i in range(min(6, len(candidate_papers)))]
    paper_choices = format_paper_choices(candidate_papers)
    badge_html = render_selection_badge(len(default_selected_indices), len(candidate_papers))
    candidate_table_rows = [
        [i+1, p['title'], p.get('chinese_summary', '围绕该课题开展的学术实证研究与机理解析'), p.get('publication_year', 2024), p.get('source', 'OpenAlex'), f"{int(float(p.get('relevance_score', 0.8)) * 100)}%"]
        for i, p in enumerate(candidate_papers)
    ]

    if auto_run:
        # 一键全自动闭环模式：自动选定 Top 6 文献无缝贯通执行后续全部节点，每步 stream yield
        progress(0.35, desc="[全自主模式] 自动精选 Top 6 核心文献，无缝贯通执行后续深度处理...")
        selected_papers = candidate_papers[:6] if candidate_papers else []
        state.data["selected_papers"] = selected_papers
        state.data["literature_pool"] = selected_papers
        state.status = WorkflowStatus.RUNNING
        state.pause_reason = None
        engine.save_checkpoint(state)

        # Frame 2: 节点 2 要素萃取 (45%)
        pipeline_html = render_claude_pipeline("feature_extraction", WorkflowStatus.RUNNING.value)
        yield (
            pipeline_html,
            gr.update(visible=True, open=False, label=f"⏳ 全自主模式推进中：已锁定 Top {len(selected_papers)} 篇核心文献，正在深度萃取要素..."),
            gr.update(visible=False),
            badge_html,
            gr.update(choices=paper_choices, value=default_selected_indices),
            candidate_table_rows,
            gr.update(visible=False),
            "", [], "", "", [], "", "",
            state.task_id, candidate_papers,
        )
        progress(0.42, desc=f"[2/7] 要素抽取：正在深度解析已选 {len(selected_papers)} 篇核心文献机制与实验...")
        state.current_step = WorkflowStep.FEATURE_EXTRACTION
        features = rev_agent.batch_extract(selected_papers, topic=query)
        state.data["extracted_features"] = [f.model_dump() for f in features]
        summary_md = rev_agent.generate_summary_collection(features)
        state.data["summary_collection_md"] = summary_md
        if "feature_extraction" not in state.completed_steps:
            state.completed_steps.append("feature_extraction")
        engine.save_checkpoint(state)
        features_md = format_features_markdown(state.data.get("extracted_features", []))

        # Frame 3: 节点 3 大纲推演 (60%)
        pipeline_html = render_claude_pipeline("outline_generation", WorkflowStatus.RUNNING.value)
        yield (
            pipeline_html,
            gr.update(visible=True, open=False, label=f"⏳ 全自主模式推进中：要素抽取完成，正在规划文献综述大纲..."),
            gr.update(visible=False),
            badge_html,
            gr.update(choices=paper_choices, value=default_selected_indices),
            candidate_table_rows,
            gr.update(visible=False),
            "", [], features_md, "", [], "", "",
            state.task_id, candidate_papers,
        )
        progress(0.58, desc="[3/7] 大纲规划：正在推演新论文专属文献综述大纲...")
        state.current_step = WorkflowStep.OUTLINE_GENERATION
        outline_md = rev_agent.generate_review_outline(query, features)
        state.data["review_outline"] = outline_md
        if "outline_generation" not in state.completed_steps:
            state.completed_steps.append("outline_generation")
        engine.save_checkpoint(state)

        # Frame 4: 节点 4 综述合成 (75%)
        pipeline_html = render_claude_pipeline("review_synthesis", WorkflowStatus.RUNNING.value)
        yield (
            pipeline_html,
            gr.update(visible=True, open=False, label=f"⏳ 全自主模式推进中：大纲推演完成，正在合成学术综述初稿框架长文..."),
            gr.update(visible=False),
            badge_html,
            gr.update(choices=paper_choices, value=default_selected_indices),
            candidate_table_rows,
            gr.update(visible=False),
            "", [], features_md, "", [], "", "",
            state.task_id, candidate_papers,
        )
        progress(0.72, desc="[4/7] 综述初稿：正在合成综述长文初稿并执行 Citation Validator 双向核验...")
        state.current_step = WorkflowStep.REVIEW_SYNTHESIS
        review_draft = rev_agent.generate_review_draft(topic=query, outline=outline_md, features=features)
        state.data["review_draft"] = review_draft
        if "review_synthesis" not in state.completed_steps:
            state.completed_steps.append("review_synthesis")
        engine.save_checkpoint(state)

        # Frame 5: 节点 5 实验数据统计与制图 (88%)
        pipeline_html = render_claude_pipeline("data_analysis", WorkflowStatus.RUNNING.value)
        yield (
            pipeline_html,
            gr.update(visible=True, open=False, label=f"⏳ 全自主模式推进中：综述初稿已合成，正在进行数据统计与科研制图..."),
            gr.update(visible=False),
            badge_html,
            gr.update(choices=paper_choices, value=default_selected_indices),
            candidate_table_rows,
            gr.update(visible=False),
            "", [], features_md, "", [], "", "",
            state.task_id, candidate_papers,
        )
        progress(0.85, desc="[5/7] 实验数据：正在进行数据收敛性统计与科研制图...")
        state.current_step = WorkflowStep.DATA_ANALYSIS
        csv_source = data_file.name if data_file is not None and hasattr(data_file, "name") else get_sample_experiment_csv()
        data_res = data_agent.run(csv_source, task_id=state.task_id, topic=query)
        state.data["data_analysis_report"] = data_res["report_markdown"]
        state.data["generated_charts"] = data_res["charts"]
        if "data_analysis" not in state.completed_steps:
            state.completed_steps.append("data_analysis")
        engine.save_checkpoint(state)

        # Frame 6: 节点 6 参考文献排版校对 (95%)
        pipeline_html = render_claude_pipeline("reference_format", WorkflowStatus.RUNNING.value)
        yield (
            pipeline_html,
            gr.update(visible=True, open=False, label=f"⏳ 全自主模式推进中：正在执行参考文献国标规范排版校对..."),
            gr.update(visible=False),
            badge_html,
            gr.update(choices=paper_choices, value=default_selected_indices),
            candidate_table_rows,
            gr.update(visible=False),
            "", [], features_md,
            state.data.get("data_analysis_report", ""),
            state.data.get("generated_charts", []),
            "", "",
            state.task_id, candidate_papers,
        )
        progress(0.95, desc="[6/7] 国标排版：正在执行参考文献 GB/T 7714-2015 格式校对与规范纠错...")
        state.current_step = WorkflowStep.REFERENCE_FORMAT
        if refs_text and refs_text.strip():
            ref_source = refs_text.strip()
        elif selected_papers:
            ref_lines = []
            for idx, p in enumerate(selected_papers, 1):
                authors = p.get("authors", [])
                auth_str = ", ".join(authors) if authors else "佚名"
                title = p.get("title", "未命名文献")
                year = p.get("publication_year", 2024)
                source = p.get("source", "学术期刊")
                ref_lines.append(f"[{idx}] {auth_str}. {title}. {source}, {year}.")
            ref_source = "\n".join(ref_lines)
        else:
            ref_source = get_sample_references_text()

        ref_res = ref_agent.run(ref_source, target_format="GB/T 7714")
        state.data["formatted_references"] = ref_res["formatted_text"]
        state.data["reference_audit_reports"] = ref_res.get("audit_reports", [])
        if "reference_format" not in state.completed_steps:
            state.completed_steps.append("reference_format")

        # Frame 7: 全流程交付完毕 (100%)
        progress(1.00, desc="[交付完毕] UniScholar 通用智能体科研全流程成果已成功交付！")
        state.status = WorkflowStatus.COMPLETED
        state.current_step = WorkflowStep.COMPLETED
        engine.save_checkpoint(state)

        # 导出成果研报落盘
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        final_report_path = os.path.join(output_dir, f"{state.task_id}_final_report.md")
        with open(final_report_path, "w", encoding="utf-8") as f:
            f.write("# UniScholar 科研全流程综合成果报告\n\n")
            f.write(f"> 任务 ID: `{state.task_id}` | 生成时间: `{state.updated_at}`\n\n")
            f.write(state.data.get("review_draft", "") + "\n\n---\n\n")
            f.write(state.data.get("data_analysis_report", "") + "\n\n---\n\n")
            f.write("## 参考文献 (规范 GB/T 7714-2015 格式)\n\n" + state.data.get("formatted_references", ""))

        table_rows = format_literature_table(selected_papers)
        pipeline_html = render_claude_pipeline("completed", WorkflowStatus.COMPLETED.value)
        yuanjing_config = json.dumps(engine.export_yuanjing_workflow_config(), ensure_ascii=False, indent=2)
        outline_md = clean_thinking_process(outline_md)
        review_draft = clean_thinking_process(review_draft)

        synthesis_deliverable_md = f"""# 成果交付：文献综述大纲规划与初稿框架

> **赛题命题对应**：中国联通大创赛产教协同创新组（功能二）——基于通用智能体结构化逻辑自动生成文献综述大纲与初稿框架。  
> **精选文献支持**：本成果由系统精选的 **{len(selected_papers)}** 篇核心文献驱动，正文引文均经 Citation Validator 白名单交叉验证。  
> **研报落盘归档**：已生成持久化研报文件 `{final_report_path}`。

---

## 交付成果 1：新论文文献综述大纲规划 (Structured Research Outline)
{outline_md}

---

## 交付成果 2：学术文献综述初稿框架 (Initial Review Draft Framework)
{review_draft}
"""
        gr.Info("🎉 综合学术成果已全流程交付完成！请在下方成果画布中查阅。")
        yield (
            pipeline_html,
            gr.update(visible=True, open=False, label=f"✓ 全自主模式：已锁定 Top {len(selected_papers)} 篇核心文献并完成全流程交付"),
            gr.update(visible=False),
            badge_html,
            gr.update(choices=paper_choices, value=default_selected_indices),
            candidate_table_rows,
            gr.update(visible=True),
            synthesis_deliverable_md,
            table_rows,
            features_md,
            state.data.get("data_analysis_report", ""),
            state.data.get("generated_charts", []),
            state.data.get("formatted_references", ""),
            yuanjing_config,
            state.task_id,
            candidate_papers,
        )
        return

    # 人在回路断点挂起：供学者直接点选论文
    progress(0.30, desc="[人在回路] 20篇候选文献池已就绪，工作流断点挂起，直接展示文献卡片供点选...")
    engine.pause_task(state.task_id, reason="人在回路：已检索20篇候选文献池，等待学者挑选核心文献")
    state = engine.load_checkpoint(state.task_id)
    pipeline_html = render_claude_pipeline(state.current_step.value, state.status.value)
    yield (
        pipeline_html,
        gr.update(visible=True, open=True, label="候选文献卡片池 (直接勾选 5~8 篇核心文献并推进后续研究)"),
        gr.update(visible=False),
        badge_html,
        gr.update(choices=paper_choices, value=default_selected_indices),
        candidate_table_rows,
        gr.update(visible=False),
        "",
        [],
        "",
        "",
        [],
        "",
        "",
        state.task_id,
        candidate_papers,
    )


def start_research_flow_auto(query, keywords_str, years, max_papers, data_file, refs_text, *unused_args, progress=gr.Progress(track_tqdm=True)):
    """一键全自动贯通运行模式包装函数 (流式生成器)"""
    yield from start_research_flow(query, keywords_str, years, max_papers, data_file, refs_text, *unused_args, auto_run=True, progress=progress)


def resume_research_with_selected_papers(
    task_id: str,
    candidate_pool: List[Dict[str, Any]],
    selected_paper_indices: List[str],
    data_file=None,
    refs_text: str = "",
    progress=gr.Progress(track_tqdm=True),
):
    """学者确认选中文献后，恢复工作流，AI 仅深度处理所选核心文献（支持实时分步流式流转与双重按钮响应）"""
    # 1. 容错恢复会话 ID (若客户端 Session 掉线则从最新持久化检查点中无缝接管)
    if not task_id:
        ckps = engine.list_checkpoints()
        if ckps:
            task_id = ckps[0]["task_id"]

    if not task_id:
        gr.Warning("未检测到有效的科研任务会话，请先点击【启动人机协同交互】启动文献检索！")
        yield (
            gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(),
        )
        return

    state = engine.load_checkpoint(task_id)
    if not state:
        gr.Warning(f"未找到任务检查点 [{task_id}]，请重新点击【启动人机协同交互】！")
        yield (
            gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
            gr.skip(),
        )
        return

    candidate_papers = candidate_pool or state.data.get("candidate_pool", [])

    # 提取选中的有效数字索引 (支持索引字符串、列表、标签及标题模糊反查)
    clean_indices = parse_selected_indices(selected_paper_indices, len(candidate_papers))
    if not clean_indices and selected_paper_indices and candidate_papers:
        items = selected_paper_indices if isinstance(selected_paper_indices, (list, tuple, set)) else [selected_paper_indices]
        for item in items:
            item_str = str(item).strip().lower()
            for p_idx, p in enumerate(candidate_papers):
                p_title = str(p.get("title", "")).strip().lower()
                if p_title and (p_title in item_str or item_str in p_title):
                    if p_idx not in clean_indices:
                        clean_indices.append(p_idx)
                    break

    # 智能兜底：如果学者未手动勾选，但候选文献池已就绪，自动锁定 Top 6 篇并弹窗明确提示，绝不静默阻塞
    if not clean_indices:
        if candidate_papers:
            clean_indices = list(range(min(6, len(candidate_papers))))
            gr.Info(f"💡 未检测到手动勾选，已自动为您精选推荐 Top {len(clean_indices)} 篇核心文献并启动深度推演！")
        else:
            gr.Warning("候选文献池为空，请先点击上方【启动人机协同交互】检索文献！")
            yield (
                gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
                gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(),
                gr.skip(),
            )
            return

    selected_papers = [candidate_papers[i] for i in clean_indices]
    badge_html = render_selection_badge(len(selected_papers), len(candidate_papers))

    # 【关键交互升级】：点击即刻弹出醒目 Toast 提示，前端状态条秒级响应
    gr.Info(f"✓ 核心文献已锁定（共 {len(selected_papers)} 篇）！工作流已恢复，正在全力推进要素抽取与综述合成...")

    # Frame 0: 秒级响应：状态机推进至节点 2（要素抽取），折叠卡片更新状态
    pipeline_html = render_claude_pipeline("feature_extraction", WorkflowStatus.RUNNING.value)
    yield (
        pipeline_html,
        gr.update(visible=True, open=False, label=f"⏳ 人在回路推进中：已锁定 {len(selected_papers)} 篇文献，AI 正在全速推演..."),
        badge_html,
        gr.update(visible=False),
        "",
        [],
        "",
        "",
        [],
        "",
        "",
    )

    state.data["selected_papers"] = selected_papers
    state.data["literature_pool"] = selected_papers
    state.status = WorkflowStatus.RUNNING
    state.pause_reason = None
    engine.save_checkpoint(state)
    query = state.params.get("query", "通用智能体科研自动化")
    engine.log(state, f"人在回路完成，学者已锁定 {len(selected_papers)} 篇核心文献注入下游深度处理")

    # 2. 深度要素抽取 (仅针对精选核心文献，100% 纯正学术中文)
    progress(0.42, desc=f"[2/7] 要素抽取：正在深度解析已选 {len(selected_papers)} 篇核心文献机制与实验...")
    state.current_step = WorkflowStep.FEATURE_EXTRACTION
    engine.log(state, f"开始对 {len(selected_papers)} 篇核心文献执行结构化要素深度抽取 (ReviewAgent)")
    features = rev_agent.batch_extract(selected_papers, topic=query)
    state.data["extracted_features"] = [f.model_dump() for f in features]
    summary_md = rev_agent.generate_summary_collection(features)
    state.data["summary_collection_md"] = summary_md
    if "feature_extraction" not in state.completed_steps:
        state.completed_steps.append("feature_extraction")
    engine.log(state, f"要素抽取完成，成功萃取 {len(features)} 组科学创新机制与方法学特征")
    engine.save_checkpoint(state)

    # Frame 1: 节点 2 完成，状态条推进至节点 3（大纲规划）
    features_md = format_features_markdown(state.data.get("extracted_features", []))
    pipeline_html = render_claude_pipeline("outline_generation", WorkflowStatus.RUNNING.value)
    yield (
        pipeline_html,
        gr.update(visible=True, open=False, label=f"⏳ 人在回路推进中：要素抽取完成，正在规划综述大纲..."),
        badge_html,
        gr.update(visible=False),
        "",
        [],
        features_md,
        "",
        [],
        "",
        "",
    )

    # 3. 新论文文献综述大纲规划 (基于核心文献证据与领域逻辑)
    progress(0.58, desc="[3/7] 大纲规划：正在推演新论文专属文献综述大纲...")
    state.current_step = WorkflowStep.OUTLINE_GENERATION
    engine.log(state, "启动新论文文献综述大纲规划推演 (ReviewAgent)")
    outline_md = rev_agent.generate_review_outline(query, features)
    state.data["review_outline"] = outline_md
    if "outline_generation" not in state.completed_steps:
        state.completed_steps.append("outline_generation")
    engine.log(state, "文献综述大纲规划完成，结构严谨对齐选题")
    engine.save_checkpoint(state)

    # Frame 2: 节点 3 完成，状态条推进至节点 4（综述初稿长文合成）
    pipeline_html = render_claude_pipeline("review_synthesis", WorkflowStatus.RUNNING.value)
    yield (
        pipeline_html,
        gr.update(visible=True, open=False, label=f"⏳ 人在回路推进中：大纲规划完成，正在深度撰写综述初稿长文..."),
        badge_html,
        gr.update(visible=False),
        "",
        [],
        features_md,
        "",
        [],
        "",
        "",
    )

    # 4. 综述初稿框架合成与防幻觉校验
    progress(0.72, desc="[4/7] 综述初稿：正在合成综述长文初稿并执行 Citation Validator 双向核验...")
    state.current_step = WorkflowStep.REVIEW_SYNTHESIS
    engine.log(state, "启动综述初稿框架长文合成与引文防幻觉双向校验")
    review_draft = rev_agent.generate_review_draft(
        topic=query,
        outline=outline_md,
        features=features,
    )
    state.data["review_draft"] = review_draft
    if "review_synthesis" not in state.completed_steps:
        state.completed_steps.append("review_synthesis")
    engine.log(state, "综述初稿框架合成完成，已通过 Citation Validator 真实文献防幻觉检验")
    engine.save_checkpoint(state)

    # Frame 3: 节点 4 完成，状态条推进至节点 5（数据分析与科研绘图）
    pipeline_html = render_claude_pipeline("data_analysis", WorkflowStatus.RUNNING.value)
    yield (
        pipeline_html,
        gr.update(visible=True, open=False, label=f"⏳ 人在回路推进中：综述初稿已合成，正在进行实验数据统计与科研绘图..."),
        badge_html,
        gr.update(visible=False),
        "",
        [],
        features_md,
        "",
        [],
        "",
        "",
    )

    # 5. 实验数据统计
    progress(0.85, desc="[5/7] 实验数据：正在进行实验数据收敛性统计、Tukey IQR 离群点审计与科研制图...")
    state.current_step = WorkflowStep.DATA_ANALYSIS
    engine.log(state, "启动实验数据初步统计分析与科研图表绘制 (DataAgent)")
    csv_source = data_file.name if data_file is not None and hasattr(data_file, "name") else get_sample_experiment_csv()
    data_res = data_agent.run(csv_source, task_id=state.task_id, topic=query)
    state.data["data_analysis_report"] = data_res["report_markdown"]
    state.data["generated_charts"] = data_res["charts"]
    if "data_analysis" not in state.completed_steps:
        state.completed_steps.append("data_analysis")
    engine.log(state, "实验数据收敛性统计与 Matplotlib 制图完成")
    engine.save_checkpoint(state)

    # 6. 参考文献国标排版
    progress(0.95, desc="[6/7] 国标排版：正在执行参考文献 GB/T 7714-2015 格式校对与规范纠错...")
    state.current_step = WorkflowStep.REFERENCE_FORMAT
    engine.log(state, "启动参考文献 GB/T 7714-2015 国标校对排版 (ReferenceAgent)")
    if refs_text and refs_text.strip():
        ref_source = refs_text.strip()
    elif selected_papers:
        ref_lines = []
        for idx, p in enumerate(selected_papers, 1):
            authors = p.get("authors", [])
            auth_str = ", ".join(authors) if authors else "佚名"
            title = p.get("title", "未命名文献")
            year = p.get("publication_year", 2024)
            source = p.get("source", "学术期刊")
            ref_lines.append(f"[{idx}] {auth_str}. {title}. {source}, {year}.")
        ref_source = "\n".join(ref_lines)
    else:
        ref_source = get_sample_references_text()

    ref_res = ref_agent.run(ref_source, target_format="GB/T 7714")
    state.data["formatted_references"] = ref_res["formatted_text"]
    state.data["reference_audit_reports"] = ref_res.get("audit_reports", [])
    if "reference_format" not in state.completed_steps:
        state.completed_steps.append("reference_format")
    engine.log(state, "参考文献 GB/T 7714-2015 格式化校对完成")

    # 7. 全流程交付完毕
    progress(1.00, desc="[交付完毕] UniScholar 通用智能体科研全流程成果已成功交付！")
    state.status = WorkflowStatus.COMPLETED
    state.current_step = WorkflowStep.COMPLETED
    engine.log(state, "UniScholar 通用智能体科研全流程成果已全部交付完毕")
    engine.save_checkpoint(state)

    # 导出最终总研报到 output 目录
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    final_report_path = os.path.join(output_dir, f"{state.task_id}_final_report.md")
    with open(final_report_path, "w", encoding="utf-8") as f:
        f.write("# UniScholar 科研全流程综合成果报告\n\n")
        f.write(f"> 任务 ID: `{state.task_id}` | 生成时间: `{state.updated_at}`\n\n")
        f.write(state.data.get("review_draft", "") + "\n\n---\n\n")
        f.write(state.data.get("data_analysis_report", "") + "\n\n---\n\n")
        f.write("## 参考文献 (规范 GB/T 7714-2015 格式)\n\n" + state.data.get("formatted_references", ""))
    logger.info(f"最终全流程科研研报已保存至: {final_report_path}")

    table_rows = format_literature_table(selected_papers)
    pipeline_html = render_claude_pipeline("completed", WorkflowStatus.COMPLETED.value)
    yuanjing_config = json.dumps(engine.export_yuanjing_workflow_config(), ensure_ascii=False, indent=2)
    outline_md = clean_thinking_process(outline_md)
    review_draft = clean_thinking_process(review_draft)

    synthesis_deliverable_md = f"""# 成果交付：文献综述大纲规划与初稿框架

> **赛题命题对应**：中国联通大创赛产教协同创新组（功能二）——基于通用智能体结构化逻辑自动生成文献综述大纲与初稿框架。  
> **精选文献支持**：本成果由学者在回路断点精选的 **{len(selected_papers)}** 篇核心文献全量驱动，正文全部引文均经 UniScholar Citation Validator 真实文献双向白名单交叉验证。  
> **研报落盘归档**：已生成持久化研报文件 `{final_report_path}`。

---

## 交付成果 1：文献综述大纲规划 (Structured Review Outline)
{outline_md}

---

## 交付成果 2：学术文献综述初稿框架 (Initial Review Draft Framework)
{review_draft}
"""
    # 弹出成功交付通知
    gr.Info("🎉 综合学术成果已全流程交付完成！请在下方成果画布中查阅。")

    yield (
        pipeline_html,
        gr.update(visible=True, open=False, label=f"✓ 人在回路：已锁定 {len(selected_papers)} 篇核心文献 (点击可展开重新调整并再次推演)"),
        badge_html,
        gr.update(visible=True),   # 展开成果画布
        synthesis_deliverable_md,  # 综述大纲与长文初稿
        table_rows,                # 精选核心文献表格
        features_md,               # 抽取要素 Markdown
        state.data.get("data_analysis_report", ""),
        state.data.get("generated_charts", []),
        state.data.get("formatted_references", ""),
        yuanjing_config,
    )


def continue_research_flow(task_id, selected_papers, data_file, refs_text, progress=gr.Progress(track_tqdm=True)):
    state = engine.load_checkpoint(task_id)
    if not state:
        return "", gr.update(visible=False), gr.update(visible=False), "", [], "", "", [], "", ""

    state.data["selected_papers"] = selected_papers
    state.data["literature_pool"] = selected_papers
    state.status = WorkflowStatus.RUNNING
    state.pause_reason = None
    engine.save_checkpoint(state)

    query = state.params.get("query", "通用智能体科研自动化")
    engine.log(state, f"人在回路完成，学者已锁定 {len(selected_papers)} 篇核心文献注入下游深度处理")

    # 2. 深度要素抽取 (仅针对精选核心文献，100% 纯正学术中文)
    progress(0.42, desc=f"[2/7] 要素抽取：正在深度解析已选 {len(selected_papers)} 篇核心文献机制与实验...")
    state.current_step = WorkflowStep.FEATURE_EXTRACTION
    engine.log(state, f"开始对 {len(selected_papers)} 篇核心文献执行结构化要素深度抽取 (ReviewAgent)")
    features = rev_agent.batch_extract(selected_papers, topic=query)
    state.data["extracted_features"] = [f.model_dump() for f in features]
    summary_md = rev_agent.generate_summary_collection(features)
    state.data["summary_collection_md"] = summary_md
    if "feature_extraction" not in state.completed_steps:
        state.completed_steps.append("feature_extraction")
    engine.log(state, f"要素抽取完成，成功萃取 {len(features)} 组科学创新机制与方法学特征")
    engine.save_checkpoint(state)

    # 3. 新论文文献综述大纲规划 (基于核心文献证据与领域逻辑)
    progress(0.58, desc="[3/7] 大纲规划：正在推演新论文专属文献综述大纲...")
    state.current_step = WorkflowStep.OUTLINE_GENERATION
    engine.log(state, "启动新论文文献综述大纲规划推演 (ReviewAgent)")
    outline_md = rev_agent.generate_review_outline(query, features)
    state.data["review_outline"] = outline_md
    if "outline_generation" not in state.completed_steps:
        state.completed_steps.append("outline_generation")
    engine.log(state, "文献综述大纲规划完成，结构严谨对齐选题")
    engine.save_checkpoint(state)

    # 4. 综述初稿框架合成与防幻觉校验
    progress(0.72, desc="[4/7] 综述初稿：正在合成综述长文初稿并执行 Citation Validator 双向核验...")
    state.current_step = WorkflowStep.REVIEW_SYNTHESIS
    engine.log(state, "启动综述初稿框架长文合成与引文防幻觉双向校验")
    review_draft = rev_agent.generate_review_draft(
        topic=query,
        outline=outline_md,
        features=features,
    )
    state.data["review_draft"] = review_draft
    if "review_synthesis" not in state.completed_steps:
        state.completed_steps.append("review_synthesis")
    engine.log(state, "综述初稿框架合成完成，已通过 Citation Validator 真实文献防幻觉检验")
    engine.save_checkpoint(state)

    # 5. 实验数据统计
    progress(0.85, desc="[5/7] 实验数据：正在进行实验数据收敛性统计、Tukey IQR 离群点审计与科研制图...")
    state.current_step = WorkflowStep.DATA_ANALYSIS
    engine.log(state, "启动实验数据初步统计分析与科研图表绘制 (DataAgent)")
    csv_source = data_file.name if data_file is not None and hasattr(data_file, "name") else get_sample_experiment_csv()
    data_res = data_agent.run(csv_source, task_id=state.task_id, topic=query)
    state.data["data_analysis_report"] = data_res["report_markdown"]
    state.data["generated_charts"] = data_res["charts"]
    if "data_analysis" not in state.completed_steps:
        state.completed_steps.append("data_analysis")
    engine.log(state, "实验数据收敛性统计与 Matplotlib 制图完成")
    engine.save_checkpoint(state)

    # 6. 参考文献国标排版
    progress(0.95, desc="[6/7] 国标排版：正在执行参考文献 GB/T 7714-2015 格式校对与规范纠错...")
    state.current_step = WorkflowStep.REFERENCE_FORMAT
    engine.log(state, "启动参考文献 GB/T 7714-2015 国标校对排版 (ReferenceAgent)")
    if refs_text and refs_text.strip():
        ref_source = refs_text.strip()
    elif selected_papers:
        ref_lines = []
        for idx, p in enumerate(selected_papers, 1):
            authors = p.get("authors", [])
            auth_str = ", ".join(authors) if authors else "佚名"
            title = p.get("title", "未命名文献")
            year = p.get("publication_year", 2024)
            source = p.get("source", "学术期刊")
            ref_lines.append(f"[{idx}] {auth_str}. {title}. {source}, {year}.")
        ref_source = "\n".join(ref_lines)
    else:
        ref_source = get_sample_references_text()

    ref_res = ref_agent.run(ref_source, target_format="GB/T 7714")
    state.data["formatted_references"] = ref_res["formatted_text"]
    state.data["reference_audit_reports"] = ref_res.get("audit_reports", [])
    if "reference_format" not in state.completed_steps:
        state.completed_steps.append("reference_format")
    engine.log(state, "参考文献 GB/T 7714-2015 格式化校对完成")

    # 完成
    progress(1.00, desc="[交付完毕] UniScholar 通用智能体科研全流程成果已成功交付！")
    state.status = WorkflowStatus.COMPLETED
    state.current_step = WorkflowStep.COMPLETED
    engine.log(state, "UniScholar 通用智能体科研全流程成果已全部交付完毕")
    engine.save_checkpoint(state)

    # 导出最终总研报到 output 目录 (保证 CLI 与 WebUI 一致性)
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    final_report_path = os.path.join(output_dir, f"{state.task_id}_final_report.md")
    with open(final_report_path, "w", encoding="utf-8") as f:
        f.write("# UniScholar 科研全流程综合成果报告\n\n")
        f.write(f"> 任务 ID: `{state.task_id}` | 生成时间: `{state.updated_at}`\n\n")
        f.write(state.data.get("review_draft", "") + "\n\n---\n\n")
        f.write(state.data.get("data_analysis_report", "") + "\n\n---\n\n")
        f.write("## 参考文献 (规范 GB/T 7714-2015 格式)\n\n" + state.data.get("formatted_references", ""))
    logger.info(f"最终全流程科研研报已保存至: {final_report_path}")

    table_rows = format_literature_table(selected_papers)
    features_md = format_features_markdown(state.data.get("extracted_features", []))
    pipeline_html = render_claude_pipeline("completed", WorkflowStatus.COMPLETED.value)
    yuanjing_config = json.dumps(engine.export_yuanjing_workflow_config(), ensure_ascii=False, indent=2)

    synthesis_deliverable_md = f"""# 成果交付：基于核心文献规划的文献综述大纲与初稿框架

> **赛题命题对应**：中国联通省级分公司赛道（功能二）——基于通用智能体结构化逻辑自动生成文献综述大纲与初稿框架。  
> **精选文献支持**：本成果由学者在回路断点精选的 **{len(selected_papers)}** 篇核心文献驱动，正文全部引文均经 UniScholar Citation Validator 真实文献双向白名单交叉验证。  
> **研报落盘归档**：已生成持久化研报文件 `{final_report_path}`。

---

## 一、 新论文文献综述大纲规划 (Structured Research Outline)
{outline_md}

---

## 二、 学术文献综述初稿框架全文 (Scholarly Review & Synthesis Draft)
{review_draft}
"""

    return (
        pipeline_html,
        gr.update(visible=True, open=False, label=f"人在回路：已锁定 {len(selected_papers)} 篇核心文献 (点击可展开重新调整并再次推演)"),
        gr.update(visible=True),   # 展开成果画布
        synthesis_deliverable_md,  # 综述大纲与长文初稿
        table_rows,                # 精选核心文献表格
        features_md,               # 抽取要素 Markdown
        data_res["report_markdown"],# 数据分析报告
        data_res["charts"],        # 实验图表
        state.data.get("formatted_references", ""),
        yuanjing_config,           # 元景配置文件
    )


def test_llm_connection(base_url, api_key, model):
    """在线测试大模型网关的可用性与连通耗时"""
    if not api_key or not api_key.strip():
        return "⚠️ **请先输入 API Key**（例如 `sk-...`）"
    import time
    clean_base = base_url.strip() if base_url else ""
    clean_key = api_key.strip() if api_key else ""
    clean_model = model.strip() if model else ""
    t0 = time.time()
    try:
        test_client = LLMClient(
            api_key=clean_key,
            base_url=clean_base,
            model=clean_model,
            timeout=30,
        )
        ans = test_client.call_llm(
            prompt="请回复数字 2，不要输出任何多余符号或解释。",
            system_prompt="你是一个简单的网络连通性与鉴权测试助手。",
            temperature=0.1,
            max_tokens=100,
            max_retries=1,
        )
        dt = round(time.time() - t0, 2)
        return (
            f"✅ **连通测试成功！** 模型 `{clean_model}` 响应正常（耗时 {dt} 秒）。\n"
            f"> 模型回复: `{str(ans).strip()[:100]}`"
        )
    except Exception as e:
        dt = round(time.time() - t0, 2)
        err_str = str(e)
        hint = ""
        if "googleapis.com" in clean_base or "openai.com" in clean_base:
            hint = "\n\n> 💡 **排查提示**：您配置的是境外模型端点（Google/OpenAI），国内直连通常会被网络拦截。请确认系统已开启代理并在 `.env` 中配置 `LLM_PROXY=http://127.0.0.1:7890`（或相应端口）；若无代理环境，建议直接在下方切换为国内免代理的 **DeepSeek 官方端点** (`https://api.deepseek.com`, 模型 `deepseek-chat`)。"
        return f"❌ **连通测试失败 (耗时 {dt} 秒)**: `{err_str[:250]}`{hint}"


def save_llm_config(base_url, api_key, model):
    """持久化保存大模型配置至 .env，并实时热重载各 Agent 的 LLMClient"""
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    clean_url = base_url.strip()
    clean_key = api_key.strip()
    clean_model = model.strip()
    content = (
        f"LLM_API_KEY={clean_key}\n"
        f"LLM_BASE_URL={clean_url}\n"
        f"LLM_MODEL={clean_model}\n"
        f"LLM_API_FORMAT=openai\n"
        f"LLM_TIMEOUT=90\n"
        f"LLM_MAX_TOKENS=4000\n"
    )
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(content)
    os.environ["LLM_API_KEY"] = clean_key
    os.environ["LLM_BASE_URL"] = clean_url
    os.environ["LLM_MODEL"] = clean_model
    rev_agent.llm_client = LLMClient()
    intent_agent.llm_client = LLMClient()
    return f"💾 **配置已成功持久化至 .env 并立即生效！**\n当前已绑定：`{clean_model}` @ `{clean_url}`"


# ==================== Claude 标志性暖雅学术美学体系 ====================
# ==================== 学术极简优雅美学体系 (Slate Minimalist) ====================
def get_claude_theme():
    """构建严谨学术、克制有力的 Slate Minimalist 高质感主题"""
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
    ).set(
        body_background_fill="#F8FAFC",
        body_background_fill_dark="#F8FAFC",
        background_fill_primary="#FFFFFF",
        background_fill_primary_dark="#FFFFFF",
        background_fill_secondary="#F1F5F9",
        background_fill_secondary_dark="#F1F5F9",
        block_background_fill="#FFFFFF",
        block_background_fill_dark="#FFFFFF",
        block_border_color="#E2E8F0",
        block_border_color_dark="#E2E8F0",
        block_label_text_color="#475569",
        block_label_text_color_dark="#475569",
        block_title_text_color="#0F172A",
        block_title_text_color_dark="#0F172A",
        body_text_color="#0F172A",
        body_text_color_dark="#0F172A",
        body_text_color_subdued="#64748B",
        body_text_color_subdued_dark="#64748B",
        input_background_fill="#FFFFFF",
        input_background_fill_dark="#FFFFFF",
        input_border_color="#E2E8F0",
        input_border_color_dark="#E2E8F0",
        input_border_color_focus="#0F172A",
        input_border_color_focus_dark="#0F172A",
        input_placeholder_color="#94A3B8",
        input_placeholder_color_dark="#94A3B8",
        button_primary_background_fill="#0F172A",
        button_primary_background_fill_dark="#0F172A",
        button_primary_background_fill_hover="#1E293B",
        button_primary_background_fill_hover_dark="#1E293B",
        button_primary_text_color="#FFFFFF",
        button_primary_text_color_dark="#FFFFFF",
        button_secondary_background_fill="#FFFFFF",
        button_secondary_background_fill_dark="#FFFFFF",
        button_secondary_background_fill_hover="#F8FAFC",
        button_secondary_background_fill_hover_dark="#F8FAFC",
        button_secondary_border_color="#E2E8F0",
        button_secondary_border_color_dark="#E2E8F0",
        button_secondary_text_color="#0F172A",
        button_secondary_text_color_dark="#0F172A",
        checkbox_background_color="#FFFFFF",
        checkbox_background_color_dark="#FFFFFF",
        checkbox_background_color_selected="#0F172A",
        checkbox_background_color_selected_dark="#0F172A",
        checkbox_border_color="#CBD5E1",
        checkbox_border_color_dark="#CBD5E1",
        slider_color="#0F172A",
        slider_color_dark="#0F172A",
        border_color_primary="#E2E8F0",
        border_color_primary_dark="#E2E8F0",
        border_color_accent="#0F172A",
        border_color_accent_dark="#0F172A",
        color_accent_soft="#F1F5F9",
        color_accent_soft_dark="#F1F5F9",
    )


def get_claude_css():
    """完整注入 CSS 样式表，实现简洁而不失风度的学术典雅排版"""
    return """
    /* 1. 强制系统与根节点锁定浅色纯净底色 */
    :root, html, body, .gradio-container, gradio-app, .dark, [class*="dark"] {
        color-scheme: light !important;
        --body-background-fill: #F8FAFC !important;
        --background-fill-primary: #FFFFFF !important;
        --background-fill-secondary: #F1F5F9 !important;
        --border-color-primary: #E2E8F0 !important;
        --border-color-accent: #0F172A !important;
        --color-accent: #0F172A !important;
        --color-accent-soft: #F1F5F9 !important;
        --body-text-color: #0F172A !important;
        --block-label-text-color: #475569 !important;
        --input-background-fill: #FFFFFF !important;
        --input-border-color: #E2E8F0 !important;
        --input-border-color-focus: #0F172A !important;
        --button-primary-background-fill: #0F172A !important;
        --button-primary-background-fill-hover: #1E293B !important;
        --button-primary-text-color: #FFFFFF !important;
        --block-radius: 10px !important;
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }

    /* 2. 抹平所有暗色残留 */
    .dark div, .dark section, .dark main, .dark form, .dark span, .dark p, .dark label,
    .dark .block, .dark .gr-box, .dark .gr-panel, .dark .gr-input,
    .dark textarea, .dark input, .dark select,
    gradio-app.dark .block, gradio-app.dark textarea, gradio-app.dark input {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border-color: #E2E8F0 !important;
    }

    /* 3. 页面顶层容器与排版居中 */
    html, body {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        overflow-x: hidden !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
    }
    gradio-app {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        box-sizing: border-box !important;
    }
    .gradio-container, .gradio-container.fillable, .gradio-container.app, gradio-app .gradio-container {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        max-width: 1200px !important;
        width: 100% !important;
        margin: 0 auto !important;
        padding: 14px 20px 60px 20px !important;
        box-sizing: border-box !important;
    }
    * {
        box-sizing: border-box !important;
    }
    .markdown, [class*="markdown"], .prose, .gr-box, .html, [class*="prose"], .gr-form, .gr-panel {
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
        white-space: normal !important;
        max-width: 100% !important;
    }
    pre, code, .prose pre, .prose code, .markdown pre, .markdown code {
        word-break: break-all !important;
        overflow-wrap: anywhere !important;
        white-space: pre-wrap !important;
        max-width: 100% !important;
    }
    .row, .gr-row, .gr-column {
        max-width: 100% !important;
        box-sizing: border-box !important;
    }

    /* 4. 品牌导航栏 (Slate Minimalist) */
    .claude-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 20px;
        background: #FFFFFF !important;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        margin-bottom: 14px;
    }
    .claude-brand {
        font-size: 17px;
        font-weight: 700;
        color: #0F172A !important;
        display: flex;
        align-items: center;
        gap: 10px;
        letter-spacing: -0.3px;
    }
    .claude-brand-tag {
        font-size: 11px;
        background: #F1F5F9 !important;
        color: #475569 !important;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
        border: 1px solid #E2E8F0;
    }

    /* 5. 核心输入卡片 */
    .claude-card {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 16px 22px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
        margin-bottom: 16px !important;
    }

    /* 6. 主操作按钮 (深墨蓝灰 Slate 900) */
    .claude-primary-btn {
        background: #0F172A !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 14.5px !important;
        box-shadow: 0 1px 3px rgba(15,23,42,0.12) !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
    }
    .claude-primary-btn:hover {
        background: #1E293B !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 3px 8px rgba(15,23,42,0.18) !important;
    }

    /* 7. 人在回路折叠卡片与工具栏 */
    .claude-hitl-accordion {
        background: #FFFFFF !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important;
        margin-bottom: 24px !important;
        overflow: hidden !important;
    }
    .claude-hitl-accordion > .label-wrap,
    .claude-hitl-accordion summary,
    .claude-hitl-accordion .label-wrap,
    .claude-hitl-accordion > button {
        background: #F8FAFC !important;
        padding: 12px 18px !important;
        border-bottom: 1px solid #E2E8F0 !important;
        cursor: pointer !important;
        font-weight: 600 !important;
        color: #0F172A !important;
    }
    .claude-hitl-toolbar {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        flex-wrap: wrap !important;
        gap: 12px !important;
        padding: 8px 0 !important;
        margin-bottom: 12px !important;
        border-bottom: 1px solid #F1F5F9 !important;
    }
    .claude-tool-btn {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        color: #334155 !important;
        font-size: 12.5px !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
    }
    .claude-tool-btn:hover {
        border-color: #94A3B8 !important;
        color: #0F172A !important;
        background: #F8FAFC !important;
    }
    .claude-tool-btn.primary {
        background: #0F172A !important;
        border-color: #0F172A !important;
        color: #FFFFFF !important;
    }
    .claude-tool-btn.primary:hover {
        background: #1E293B !important;
        border-color: #1E293B !important;
    }

    /* 8. 原生 CheckboxGroup 选项卡片化 */
    .claude-paper-selector {
        background: transparent !important;
        border: none !important;
        user-select: text !important;
        -webkit-user-select: text !important;
    }
    .claude-paper-selector .wrap {
        display: flex !important;
        flex-direction: column !important;
        gap: 8px !important;
    }
    .claude-paper-selector label {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        display: flex !important;
        align-items: flex-start !important;
        gap: 12px !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.01) !important;
        user-select: text !important;
        -webkit-user-select: text !important;
    }
    .claude-paper-selector label:hover {
        border-color: #94A3B8 !important;
        background: #F8FAFC !important;
    }
    .claude-paper-selector label:has(input:checked),
    .claude-paper-selector label.selected {
        border-color: #0F172A !important;
        background: #F8FAFC !important;
        box-shadow: 0 1px 3px rgba(15,23,42,0.06) !important;
    }
    .claude-paper-selector label span {
        white-space: pre-wrap !important;
        line-height: 1.55 !important;
        font-size: 13px !important;
        color: #0F172A !important;
        user-select: text !important;
        -webkit-user-select: text !important;
    }
    .claude-paper-selector input[type="checkbox"] {
        accent-color: #0F172A !important;
        width: 17px !important;
        height: 17px !important;
        margin-top: 2px !important;
        cursor: pointer !important;
        flex-shrink: 0 !important;
    }

    /* 9. 核心恢复按钮 (全宽、稳重、优雅) */
    .claude-resume-primary-btn {
        background: #0F172A !important;
        color: #FFFFFF !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        padding: 13px 24px !important;
        border-radius: 8px !important;
        border: none !important;
        box-shadow: 0 2px 6px rgba(15,23,42,0.15) !important;
        letter-spacing: 0.2px !important;
        width: 100% !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
        margin-top: 12px !important;
    }
    .claude-resume-primary-btn:hover {
        background: #1E293B !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(15,23,42,0.2) !important;
    }
    .claude-hitl-action-bar {
        background: #F8FAFC !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        padding: 8px 14px !important;
        margin-top: 6px !important;
        margin-bottom: 12px !important;
        display: flex !important;
        align-items: center !important;
    }
    .claude-resume-primary-btn-top {
        background: #0F172A !important;
        color: #FFFFFF !important;
        font-size: 13.5px !important;
        font-weight: 700 !important;
        padding: 9px 18px !important;
        border-radius: 6px !important;
        border: none !important;
        box-shadow: 0 2px 6px rgba(15,23,42,0.18) !important;
        width: 100% !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
    }
    .claude-resume-primary-btn-top:hover {
        background: #1E293B !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(15,23,42,0.25) !important;
    }

    /* 10. 成果画布 */
    .claude-canvas {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 22px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }

    /* 11. 表单输入与排版 */
    label span {
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 12.5px !important;
    }
    textarea, input[type="text"], input[type="number"] {
        border-color: #E2E8F0 !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border-radius: 8px !important;
    }
    textarea:focus, input:focus {
        border-color: #0F172A !important;
        box-shadow: 0 0 0 1.5px rgba(15,23,42,0.15) !important;
    }

    /* 12. Markdown 学术排版与代码块渲染 */
    .prose, .markdown {
        color: #0F172A !important;
        line-height: 1.75 !important;
    }
    .prose h1, .prose h2, .prose h3, .markdown h1, .markdown h2, .markdown h3 {
        color: #0F172A !important;
        font-weight: 700 !important;
        letter-spacing: -0.2px;
    }
    .prose hr, .markdown hr {
        border-color: #E2E8F0 !important;
    }

    /* 严谨的学术三线表 */
    .prose table, .markdown table, table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 16px 0 !important;
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 6px !important;
        overflow: hidden !important;
    }
    .prose th, .markdown th, th {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        font-weight: 600 !important;
        font-size: 12.5px !important;
        padding: 9px 13px !important;
        border-bottom: 1.5px solid #CBD5E1 !important;
        text-align: left !important;
    }
    .prose td, .markdown td, td {
        padding: 9px 13px !important;
        border-bottom: 1px solid #F1F5F9 !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        font-size: 12.5px !important;
    }
    .prose tr:hover td, .markdown tr:hover td, tr:hover td {
        background-color: #F8FAFC !important;
    }

    /* 行内代码与引用标签 */
    code, pre, .prose code, .markdown code, table code, span code {
        background-color: #F1F5F9 !important;
        color: #0F172A !important;
        padding: 2px 5px !important;
        border-radius: 4px !important;
        font-size: 0.88em !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        border: 1px solid #E2E8F0 !important;
        font-weight: 500 !important;
    }
    pre code {
        padding: 0 !important;
        border: none !important;
        background-color: transparent !important;
    }
    pre {
        background-color: #F8FAFC !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 6px !important;
        padding: 12px !important;
    }

    /* 学术引用块 */
    .prose blockquote, .markdown blockquote, blockquote {
        border-left: 3px solid #0F172A !important;
        background: #F8FAFC !important;
        padding: 10px 14px !important;
        margin: 12px 0 !important;
        border-radius: 0 6px 6px 0 !important;
        color: #475569 !important;
    }

    /* 13. 大模型导读卡片样式 (Slate Clean) */
    .claude-llm-guide-box {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-left: 4px solid #0F172A !important;
        border-radius: 10px !important;
        padding: 16px 20px !important;
        margin-bottom: 14px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
        color: #0F172A !important;
        line-height: 1.7 !important;
    }
    .claude-llm-guide-box h3, .claude-llm-guide-box h4 {
        color: #0F172A !important;
        margin-top: 12px !important;
        margin-bottom: 5px !important;
        font-weight: 700 !important;
    }
    .claude-llm-guide-box ul, .claude-llm-guide-box ol {
        margin: 6px 0 10px 16px !important;
    }
    .claude-llm-guide-box li {
        margin-bottom: 4px !important;
    }

    /* 14. 成果画布选项卡自适应 */
    .tab-nav, [role="tablist"] {
        flex-wrap: wrap !important;
        gap: 4px !important;
        border-bottom: 1px solid #E2E8F0 !important;
        padding-bottom: 2px !important;
    }
    .tab-nav button, [role="tablist"] button {
        white-space: nowrap !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 7px 14px !important;
        border-radius: 6px 6px 0 0 !important;
    }

    /* 15. 隐藏 Gradio 顶部浮动进度条 (响应学者指示：视觉焦点完全收拢至下方 1-7 节点编排轨迹长条) */
    div[data-testid="progress"],
    .progress-container,
    .progress-level,
    .progress-bar-wrap,
    .toast-wrap,
    .toast-body,
    div.wrap.generating,
    div.wrap.loading {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        height: 0 !important;
        width: 0 !important;
        pointer-events: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    footer { display: none !important; }
    """


def get_claude_js():
    """客户端 JavaScript：强制消除暗色模式冲突，保持纯净学术浅色"""
    return """
    () => {
        try {
            localStorage.setItem('gradio_theme', 'light');
        } catch (e) {}

        function purgeDark() {
            document.documentElement.classList.remove('dark');
            document.body.classList.remove('dark');
            const apps = document.querySelectorAll('gradio-app');
            apps.forEach(app => app.classList.remove('dark'));
        }

        purgeDark();

        if (window.MutationObserver) {
            const observer = new MutationObserver(() => {
                purgeDark();
            });
            observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
            observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
        }
    }
    """


def get_claude_head():
    """向 HTML Head 注入元标签和高优先级样式，确保浏览器首屏以学术浅色渲染"""
    return """
    <meta name="color-scheme" content="light">
    <style>
        :root, html, body {
            color-scheme: light !important;
            background-color: #F8FAFC !important;
        }
    </style>
    """


def launch_claude_ui(demo, server_name="127.0.0.1", server_port=7860, inbrowser=False):
    """统一配置 Claude 主题、CSS、JS 与 Head，启动 Gradio 6 服务"""
    theme = get_claude_theme()
    css = get_claude_css()
    js = get_claude_js()
    head = get_claude_head()

    return demo.launch(
        server_name=server_name,
        server_port=server_port,
        inbrowser=inbrowser,
        theme=theme,
        css=css,
        js=js,
        head=head,
    )


# ==================== 构建 Claude 风格 UI ====================
def build_ui():
    claude_css = get_claude_css()

    with gr.Blocks(title="UniScholar - 通用AI科研智能体") as demo:
        gr.HTML(f"<style>{claude_css}</style>")

        # 会话级安全状态 (Session Safety)
        task_id_state = gr.State(value="")
        candidate_papers_state = gr.State(value=[])

        gr.HTML("""
        <div class="claude-nav">
            <div class="claude-brand">
                <span style="display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #0F172A; margin-right: 2px;"></span>
                <span>UniScholar</span>
                <span style="font-size: 13px; font-weight: 500; color: #64748B; margin-left: 6px;">联智学者 · 高校科研通用智能体工作台</span>
                <span class="claude-brand-tag">中国联通产业赛道</span>
            </div>
            <div style="font-size: 12px; color: #64748B; display: flex; align-items: center; gap: 12px;">
                <span>系统引擎: <b style="color: #059669; font-weight: 600;">就绪 (Ready)</b></span>
                <span style="color: #CBD5E1;">|</span>
                <span>工作流规范: <b style="color: #0F172A; font-weight: 600;">元景万悟 v2.0 (DAG)</b></span>
            </div>
        </div>
        """)

        # 核心 Pipeline 流程轴
        pipeline_status_component = gr.HTML(render_claude_pipeline("init", "IDLE"))

        # ==================== 0. 大模型服务网关与连接配置抽屉 ====================
        default_key = os.getenv("LLM_API_KEY", "")
        masked_key = (default_key[:6] + "..." + default_key[-4:]) if len(default_key) > 10 else (default_key or "未配置")
        with gr.Accordion("模型服务网关与连接配置 (当前默认: Atria-Dawn-Preview)", open=False):
            with gr.Row():
                ui_base_url = gr.Textbox(
                    label="API Base URL",
                    value=os.getenv("LLM_BASE_URL", "https://api.atria-asi.ai/v1"),
                    placeholder="https://api.atria-asi.ai/v1 或 https://api.deepseek.com/v1",
                    scale=5,
                )
                ui_model = gr.Textbox(
                    label="模型名称 (Model)",
                    value=os.getenv("LLM_MODEL", "Atria-Dawn-Preview"),
                    placeholder="Atria-Dawn-Preview 或 deepseek-chat",
                    scale=4,
                )
                ui_api_key = gr.Textbox(
                    label="API Key",
                    value=default_key,
                    type="password",
                    placeholder="sk-... 或 atr_...",
                    scale=5,
                )
            with gr.Row():
                ui_test_btn = gr.Button("测试服务连通性", size="sm")
                ui_save_btn = gr.Button("保存并应用配置", variant="primary", size="sm", elem_classes=["claude-primary-btn"])
            ui_status_info = gr.Markdown(f"当前模型服务：`{os.getenv('LLM_MODEL', 'Atria-Dawn-Preview')}` | Key 状态：`{masked_key}`")

            ui_test_btn.click(
                fn=test_llm_connection,
                inputs=[ui_base_url, ui_api_key, ui_model],
                outputs=[ui_status_info],
            )
            ui_save_btn.click(
                fn=save_llm_config,
                inputs=[ui_base_url, ui_api_key, ui_model],
                outputs=[ui_status_info],
            )

        # ==================== 1. 主输入交互卡片 ====================
        with gr.Group(elem_classes=["claude-card"]):
            with gr.Row():
                main_query = gr.Textbox(
                    label="研究方向与核心选题",
                    placeholder="请输入拟探索的科研课题或方向，例如：看色情片对大脑神经回路与认知控制的影响、大语言模型在药物设计中的应用等",
                    value="",
                    lines=1,
                    scale=12,
                )

            with gr.Row():
                with gr.Column(scale=6):
                    keywords_input = gr.Textbox(
                        label="聚焦关键词 (英文逗号分隔，可选)",
                        placeholder="例如：fMRI, Cognitive Control, Striatum（选填，留空大模型将自动规划高区分度检索短语）",
                        value="",
                    )
                with gr.Column(scale=3):
                    years_slider = gr.Slider(minimum=1, maximum=10, value=3, step=1, label="文献发表跨度 (近N年)")
                with gr.Column(scale=3):
                    papers_slider = gr.Slider(minimum=15, maximum=40, value=20, step=5, label="初筛候选文献规模")

            with gr.Accordion("附加实验数据与参考文献样本 (可选，点击展开)", open=False):
                with gr.Row():
                    with gr.Column(scale=6):
                        data_file_input = gr.File(label="上传实验数据表格 (.csv / .xlsx，不传则使用系统内置公开实验数据)")
                    with gr.Column(scale=6):
                        refs_text_input = gr.Textbox(
                            label="输入待规范参考文献 (不填则使用内置学术样本进行国标排版)",
                            placeholder="每行一条参考文献...",
                            lines=3,
                        )

            # 底部宽屏操作栏
            with gr.Row(elem_classes=["claude-action-bar"]):
                with gr.Column(scale=6):
                    gr.HTML("""
                    <div style="font-size: 12.5px; color: #64748B; display: flex; align-items: center; gap: 6px; padding-top: 8px;">
                        <span><b>交互指引</b>：推荐使用【人在回路】模式，可在文献池检索完成后介入精选；亦可选择【一键全自主闭环交付】。</span>
                    </div>
                    """)
                with gr.Column(scale=3):
                    run_auto_btn = gr.Button("一键全自主闭环交付", variant="secondary", size="lg")
                with gr.Column(scale=3):
                    run_main_btn = gr.Button("启动人机协同交互 (人在回路)", variant="primary", elem_classes=["claude-primary-btn"], size="lg")

        # ==================== 2. 人在回路精选折叠卡片 (HITL Checkpoint) ====================
        with gr.Accordion(
            "候选文献卡片池 (直接勾选 5~8 篇核心文献并推进后续研究)",
            open=True,
            visible=False,
            elem_classes=["claude-hitl-accordion"],
        ) as hitl_accordion:
            # 候选文献选择工具栏
            with gr.Row(elem_classes=["claude-hitl-toolbar"]):
                with gr.Column(scale=5):
                    selection_counter_badge = gr.HTML(render_selection_badge(6, 20))
                with gr.Column(scale=7):
                    with gr.Row():
                        btn_top6 = gr.Button("推荐精选 Top 6", size="sm", elem_classes=["claude-tool-btn", "primary"])
                        btn_all = gr.Button("全部勾选", size="sm", elem_classes=["claude-tool-btn"])
                        btn_clear = gr.Button("清空已选", size="sm", elem_classes=["claude-tool-btn"])
                        btn_invert = gr.Button("反向选择", size="sm", elem_classes=["claude-tool-btn"])

            # 顶部快捷确认推进条 (位于卡片正上方，无需滚动即可一键直接推进)
            with gr.Row(elem_classes=["claude-hitl-action-bar"]):
                with gr.Column(scale=8):
                    gr.HTML("""
                    <div style="font-size: 13px; color: #475569; display: flex; align-items: center; gap: 8px; padding: 4px 0;">
                        <span style="font-weight: 700; color: #0F172A;">💡 核心操作：</span>
                        <span>勾选下方核心文献（或直接点击上方“推荐精选”），点击右侧按钮立即推进后续要素抽取与综述生成 ➔</span>
                    </div>
                    """)
                with gr.Column(scale=4):
                    resume_flow_btn_top = gr.Button(
                        "确认核心文献并推进后续研究 ➔",
                        variant="primary",
                        elem_classes=["claude-resume-primary-btn-top"],
                        size="md",
                    )

            # 隐藏占位符（保持回调签名稳定兼容）
            hitl_llm_guide = gr.Markdown(visible=False)

            # 原生 CheckboxGroup 选择器
            paper_selector = gr.CheckboxGroup(
                choices=[],
                value=[],
                label="候选文献池 (直接勾选核心文献，支持自由划选文本复制)",
                elem_classes=["claude-paper-selector"],
            )

            # 底部确认恢复主按钮 (滚动到底部同样可直接点击)
            resume_flow_btn = gr.Button(
                "确认核心文献并推进后续研究 ➔",
                variant="primary",
                elem_classes=["claude-resume-primary-btn"],
                size="lg",
            )

            with gr.Accordion("候选文献情报详表 (点击展开)", open=False):
                hitl_candidate_detail_table = gr.Dataframe(
                    headers=["序号", "论文标题", "中文要点导读", "年份", "数据源/期刊", "相关度"],
                    datatype=["number", "str", "str", "number", "str", "str"],
                    label="候选文献情报索引",
                    wrap=True,
                )

        # ==================== 3. 最终科研成果大画布 ====================
        with gr.Group(visible=False, elem_classes=["claude-canvas"]) as result_workspace:
            with gr.Row():
                with gr.Column(scale=8):
                    gr.HTML("""
                    <div style="font-size: 15px; font-weight: 700; color: #0F172A; padding-top: 4px; display: flex; align-items: center; gap: 10px;">
                        <span>UniScholar 科研综合成果交付画布</span>
                        <span style="font-size: 11.5px; color: #059669; font-weight: 500; background: #ECFDF5; border: 1px solid #A7F3D0; padding: 2px 8px; border-radius: 4px;">真实文献防幻觉检验通过</span>
                    </div>
                    """)
                with gr.Column(scale=4):
                    with gr.Row():
                        download_report_btn = gr.Button("导出 Markdown 综合研报", size="sm", elem_classes=["claude-tool-btn", "primary"])
            download_file_out = gr.File(label="综合研报文件 (.md)", visible=False)

            with gr.Tabs():
                with gr.TabItem("学术综述初稿与大纲规划"):
                    final_report_md = gr.Markdown()

                with gr.TabItem("核心文献要素萃取矩阵"):
                    result_papers_table = gr.Dataframe(
                        headers=["序号", "论文标题", "年份", "被引频次", "相关度得分", "数据源"],
                        datatype=["number", "str", "number", "number", "str", "str"],
                        label="精选核心文献池 (已注入下游深度解析)",
                        wrap=True,
                    )
                    features_summary_md = gr.Markdown()

                with gr.TabItem("实证数据统计与科研制图"):
                    data_analysis_md = gr.Markdown()
                    charts_gallery = gr.Gallery(label="实证科研图表 (趋势收敛图 / Tukey 箱线图 / 频数分布图)", columns=2, height="auto")

                with gr.TabItem("规范引文格式库 (GB/T 7714)"):
                    formatted_citations_box = gr.Markdown()

                with gr.TabItem("元景工作流标准定义与执行轨迹"):
                    workflow_meta_json = gr.Code(language="json", label="workflow_config.json (元景万悟 DAG 编排格式)")

        # ==================== 交互事件绑定 ====================
        # 工具栏按钮联动
        btn_top6.click(
            fn=select_top6_action,
            inputs=[candidate_papers_state],
            outputs=[paper_selector, selection_counter_badge],
        )
        btn_all.click(
            fn=select_all_action,
            inputs=[candidate_papers_state],
            outputs=[paper_selector, selection_counter_badge],
        )
        btn_clear.click(
            fn=clear_all_action,
            inputs=[candidate_papers_state],
            outputs=[paper_selector, selection_counter_badge],
        )
        btn_invert.click(
            fn=invert_selection_action,
            inputs=[paper_selector, candidate_papers_state],
            outputs=[paper_selector, selection_counter_badge],
        )
        paper_selector.change(
            fn=on_selection_change_action,
            inputs=[paper_selector, candidate_papers_state],
            outputs=[selection_counter_badge],
        )

        # 1. 启动人机协同交互
        run_main_btn.click(
            fn=start_research_flow,
            inputs=[
                main_query,
                keywords_input,
                years_slider,
                papers_slider,
                data_file_input,
                refs_text_input,
            ],
            outputs=[
                pipeline_status_component,
                hitl_accordion,
                hitl_llm_guide,
                selection_counter_badge,
                paper_selector,
                hitl_candidate_detail_table,
                result_workspace,
                final_report_md,
                result_papers_table,
                features_summary_md,
                data_analysis_md,
                charts_gallery,
                formatted_citations_box,
                workflow_meta_json,
                task_id_state,
                candidate_papers_state,
            ],
        )

        # 1.2 一键全自动闭环交付按钮
        run_auto_btn.click(
            fn=start_research_flow_auto,
            inputs=[
                main_query,
                keywords_input,
                years_slider,
                papers_slider,
                data_file_input,
                refs_text_input,
            ],
            outputs=[
                pipeline_status_component,
                hitl_accordion,
                hitl_llm_guide,
                selection_counter_badge,
                paper_selector,
                hitl_candidate_detail_table,
                result_workspace,
                final_report_md,
                result_papers_table,
                features_summary_md,
                data_analysis_md,
                charts_gallery,
                formatted_citations_box,
                workflow_meta_json,
                task_id_state,
                candidate_papers_state,
            ],
        )

        # 2. 确认核心文献并续跑至交付 (顶部工具栏与底部双主按钮联动，随时便捷推进)
        resume_inputs = [
            task_id_state,
            candidate_papers_state,
            paper_selector,
            data_file_input,
            refs_text_input,
        ]
        resume_outputs = [
            pipeline_status_component,
            hitl_accordion,
            selection_counter_badge,
            result_workspace,
            final_report_md,
            result_papers_table,
            features_summary_md,
            data_analysis_md,
            charts_gallery,
            formatted_citations_box,
            workflow_meta_json,
        ]

        resume_flow_btn.click(
            fn=resume_research_with_selected_papers,
            inputs=resume_inputs,
            outputs=resume_outputs,
        )
        resume_flow_btn_top.click(
            fn=resume_research_with_selected_papers,
            inputs=resume_inputs,
            outputs=resume_outputs,
        )

        # 3. 综合科研研报导出下载
        def export_final_report_download(tid):
            if not tid:
                return None, gr.update(visible=False)
            report_p = os.path.join("output", f"{tid}_final_report.md")
            if os.path.exists(report_p):
                return report_p, gr.update(visible=True)
            return None, gr.update(visible=False)

        download_report_btn.click(
            fn=export_final_report_download,
            inputs=[task_id_state],
            outputs=[download_file_out, download_file_out],
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    launch_claude_ui(demo, server_name="127.0.0.1", server_port=7860, inbrowser=False)

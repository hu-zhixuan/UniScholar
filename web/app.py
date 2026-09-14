"""
UniScholar (联智学者) - 极简 Claude 暖雅学术科研工作台
面向大创赛产业赛道（中国联通浙江省分公司命题）：基于通用智能体工作流的高校科研全流程自动化系统。
采用 Anthropic Claude 标志性的暖雅学术美学（Warm Terracotta & Sand / Ivory），
彻底清除浏览器暗色模式冲突（告别黑白混杂），呈现呼吸感、极具人文科研质感的商业级界面。
"""

import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional

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

import gradio as gr

from agents.data_agent import DataAgent
from agents.intent_agent import IntentAgent
from agents.literature_agent import LiteratureAgent
from agents.reference_agent import ReferenceAgent
from agents.review_agent import PaperFeature, ReviewAgent
from utils.llm_client import LLMClient
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

current_active_task_id = None


def render_claude_pipeline(current_step: str, status: str) -> str:
    """生成具有 Claude 质感的优雅工作流 Pipeline 进度卡片与流光进度条"""
    steps = [
        ("0. 学术意图规划", WorkflowStep.INTENT_FORMULATION.value, "✦"),
        ("1. 候选文献召回 (HITL)", WorkflowStep.LITERATURE_RETRIEVAL.value, "✦"),
        ("2. 核心要素抽取", WorkflowStep.FEATURE_EXTRACTION.value, "✦"),
        ("3. 综述大纲规划", WorkflowStep.OUTLINE_GENERATION.value, "✦"),
        ("4. 成果合成与交付", WorkflowStep.COMPLETED.value, "✦"),
    ]

    step_keys = [s[1] for s in steps]
    cur_idx = step_keys.index(current_step) if current_step in step_keys else 0
    if status == WorkflowStatus.COMPLETED.value:
        cur_idx = 5

    # 精确计算平滑进度百分比与当前动作指示
    if status == WorkflowStatus.COMPLETED.value:
        pct = 100
        progress_text = "全流程科研成果已全部交付 (100%)"
        badge_style = "background: #F0F5F0; color: #2D6A3E; border: 1px solid #C8E6C9;"
        bar_gradient = "linear-gradient(90deg, #52B788 0%, #2D6A3E 100%)"
        bar_shadow = "0 0 10px rgba(45, 106, 62, 0.35)"
    elif current_step == WorkflowStep.INTENT_FORMULATION.value:
        pct = 20
        progress_text = "Step 0 · 正在解耦学术选题与规划检索词 (20%)"
        badge_style = "background: #FDF3EE; color: #C25E3E; border: 1px solid #F5C6B5;"
        bar_gradient = "linear-gradient(90deg, #F5B041 0%, #C25E3E 100%)"
        bar_shadow = "0 0 10px rgba(194, 94, 62, 0.3)"
    elif current_step == WorkflowStep.LITERATURE_RETRIEVAL.value:
        if status == WorkflowStatus.PAUSED.value:
            pct = 40
            progress_text = "Step 1 · 20篇候选文献池已就绪 · 人在回路待学者点选 (40%)"
            badge_style = "background: #FEF8EC; color: #A06400; border: 1px solid #F5DAA5;"
            bar_gradient = "linear-gradient(90deg, #F5B041 0%, #D97706 100%)"
            bar_shadow = "0 0 12px rgba(217, 119, 6, 0.4)"
        else:
            pct = 35
            progress_text = "Step 1 · 跨源检索 20 篇真实候选文献中 (35%)"
            badge_style = "background: #FDF3EE; color: #C25E3E; border: 1px solid #F5C6B5;"
            bar_gradient = "linear-gradient(90deg, #E27D60 0%, #C25E3E 100%)"
            bar_shadow = "0 0 10px rgba(194, 94, 62, 0.3)"
    elif current_step == WorkflowStep.FEATURE_EXTRACTION.value:
        pct = 60
        progress_text = "Step 2 · 核心文献要素与微观机制深度萃取中 (60%)"
        badge_style = "background: #FDF3EE; color: #C25E3E; border: 1px solid #F5C6B5;"
        bar_gradient = "linear-gradient(90deg, #E27D60 0%, #C25E3E 60%, #52B788 100%)"
        bar_shadow = "0 0 10px rgba(194, 94, 62, 0.3)"
    elif current_step == WorkflowStep.OUTLINE_GENERATION.value:
        pct = 80
        progress_text = "Step 3 · 领域专属新论文综述大纲推演生成中 (80%)"
        badge_style = "background: #FDF3EE; color: #C25E3E; border: 1px solid #F5C6B5;"
        bar_gradient = "linear-gradient(90deg, #E27D60 0%, #C25E3E 50%, #52B788 100%)"
        bar_shadow = "0 0 10px rgba(45, 106, 62, 0.3)"
    elif current_step == WorkflowStep.REVIEW_SYNTHESIS.value:
        pct = 90
        progress_text = "Step 4 · 长篇学术综述初稿合成与 Citation 防幻觉核验中 (90%)"
        badge_style = "background: #FDF3EE; color: #C25E3E; border: 1px solid #F5C6B5;"
        bar_gradient = "linear-gradient(90deg, #E27D60 0%, #C25E3E 30%, #2D6A3E 100%)"
        bar_shadow = "0 0 12px rgba(45, 106, 62, 0.35)"
    else:
        pct = 0
        progress_text = "智能体集群已就绪，等待启动 (Ready)"
        badge_style = "background: #F4F1EA; color: #79746C; border: 1px solid #E2DDD5;"
        bar_gradient = "#E2DDD5"
        bar_shadow = "none"

    html_items = []
    for idx, (name, key, icon) in enumerate(steps):
        step_num = f"0{idx}"
        if status == WorkflowStatus.COMPLETED.value or idx < cur_idx:
            # 优雅鼠尾草绿 (Sage Green - 已完成)
            style = "background: #F0F5F0; color: #2D6A3E; border: 1.5px solid #C8E6C9;"
            tag = "已完成 ✓"
            node_dot = '<span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #2D6A3E; margin-right: 5px;"></span>'
        elif idx == cur_idx:
            if status == WorkflowStatus.PAUSED.value:
                # 暖杏琥珀色 (Amber Gold - 待学者点选)
                style = "background: #FEF8EC; color: #A06400; border: 1.5px solid #F5DAA5; box-shadow: 0 0 14px rgba(160,100,0,0.18);"
                tag = "待学者点选 ⏸️"
                node_dot = '<span class="claude-pulse-paused" style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #D97706; margin-right: 5px;"></span>'
            elif status == WorkflowStatus.RUNNING.value:
                # 克劳德陶土珊瑚色 (Claude Terracotta - 进行中)
                style = "background: #FDF3EE; color: #C25E3E; border: 1.5px solid #F5C6B5; box-shadow: 0 0 14px rgba(194,94,62,0.2);"
                tag = "执行中 ⏳"
                node_dot = '<span class="claude-pulse-active" style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #CC785C; margin-right: 5px;"></span>'
            else:
                style = "background: #F7F4EE; color: #78736B; border: 1px solid #E8E2D6;"
                tag = "就绪"
                node_dot = '<span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #A8A196; margin-right: 5px;"></span>'
        else:
            # 柔和暖燕麦灰 (Muted Sand - 待执行)
            style = "background: #FAF8F5; color: #9E978D; border: 1px solid #EDE8DF;"
            tag = "待执行"
            node_dot = '<span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #D4CEBF; margin-right: 5px;"></span>'

        html_items.append(f"""
        <div style="flex: 1; min-width: 145px; padding: 10px 14px; border-radius: 11px; {style}; display: flex; flex-direction: column; gap: 4px; font-family: inherit; transition: all 0.3s ease;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 11px; font-weight: 700; opacity: 0.7; letter-spacing: 0.5px;">STEP {step_num}</span>
                <span style="font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 10px; background: rgba(255,255,255,0.85);">{tag}</span>
            </div>
            <div style="font-weight: 600; font-size: 13px; display: flex; align-items: center; margin-top: 2px;">
                {node_dot}<span>{name}</span>
            </div>
        </div>
        """)

    connector = '<div style="color: #D6D0C4; font-weight: 600; font-size: 13px; align-self: center; padding: 0 1px;">➔</div>'
    joined_nodes = f" {connector} ".join(html_items)

    status_pill = {
        WorkflowStatus.IDLE.value: '<span style="color: #79746C; font-weight: 500;">● 智能体就绪 (Ready)</span>',
        WorkflowStatus.RUNNING.value: '<span style="color: #C25E3E; font-weight: 600;">● 自主编排执行中 (Running)</span>',
        WorkflowStatus.PAUSED.value: '<span style="color: #A06400; font-weight: 600;">● 候选文献池挂起 · 等待学者精选 (HITL Paused)</span>',
        WorkflowStatus.COMPLETED.value: '<span style="color: #2D6A3E; font-weight: 600;">● 全流程已交付 (Completed)</span>',
    }.get(status, '<span style="color: #79746C;">就绪</span>')

    return f"""
    <div style="background: #FFFFFF; border: 1px solid #E8E3DA; border-radius: 16px; padding: 16px 22px; box-shadow: 0 3px 14px rgba(0,0,0,0.02); margin-bottom: 22px;">
        <!-- 标题栏与状态徽章 -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-size: 13.5px; font-weight: 700; color: #2B2824; display: flex; align-items: center; gap: 8px;">
                <span style="color: #CC785C; font-size: 15px;">✦</span>
                <span>通用智能体工作流执行管线 (StateGraph DAG Pipeline)</span>
                <span style="font-size: 11px; background: #F4F1EA; color: #6E685E; padding: 2px 9px; border-radius: 12px; font-weight: 500;">联通元景万悟标准</span>
            </div>
            <div style="font-size: 12.5px; font-family: inherit;">{status_pill}</div>
        </div>

        <!-- 极具 Claude 质感的流光连续进度条 -->
        <div style="margin: 6px 0 16px 0; background: #FAF8F5; padding: 10px 14px; border-radius: 10px; border: 1px solid #ECE7DE;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 7px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 12px; font-weight: 600; color: #4A443B;">全流程编排进度 (Workflow Timeline Progress)</span>
                    <span style="font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; {badge_style};">{progress_text}</span>
                </div>
                <div style="display: flex; align-items: baseline; gap: 2px;">
                    <span style="font-size: 14px; font-weight: 700; color: #C25E3E; font-family: ui-monospace, SFMono-Regular, monospace;">{pct}</span>
                    <span style="font-size: 11px; font-weight: 600; color: #A8A196;">%</span>
                </div>
            </div>
            <div style="height: 8px; width: 100%; background: #E6E0D6; border-radius: 999px; overflow: hidden; position: relative;">
                <div class="claude-progress-shimmer" style="height: 100%; width: {pct}%; background: {bar_gradient}; border-radius: 999px; transition: width 0.7s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: {bar_shadow};"></div>
            </div>
        </div>

        <!-- 5大节点卡片连线图 -->
        <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: stretch;">
            {joined_nodes}
        </div>
    </div>
    """


def render_funnel_svg(candidate_count: int = 20, selected_count: int = 6) -> str:
    """生成具有 Claude 质感的工作流漏斗连线流 (DAG Funnel Flow) SVG"""
    pct = int((selected_count / max(1, candidate_count)) * 100) if candidate_count else 0
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; min-height: 380px; padding: 14px; background: #FAF9F5; border-radius: 14px; border: 1.5px solid #ECE7DE; box-shadow: inset 0 1px 4px rgba(0,0,0,0.02);">
        <div style="font-size: 12px; font-weight: 700; color: #8C533E; margin-bottom: 8px; letter-spacing: 0.5px; text-transform: uppercase;">
            ✦ 智能收敛连线流 (Funnel Flow)
        </div>
        <svg width="220" height="280" viewBox="0 0 220 280" fill="none" xmlns="http://www.w3.org/2000/svg" style="max-width: 100%;">
            <defs>
                <linearGradient id="terracottaGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#E27D60" />
                    <stop offset="100%" stop-color="#C25E3E" />
                </linearGradient>
                <linearGradient id="amberGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#F5B041" />
                    <stop offset="100%" stop-color="#D97706" />
                </linearGradient>
                <linearGradient id="sageGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#52B788" />
                    <stop offset="100%" stop-color="#2D6A3E" />
                </linearGradient>
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
            </defs>

            <!-- 顶端候选池节点 -->
            <rect x="25" y="12" width="170" height="42" rx="8" fill="#FFFFFF" stroke="#E2DDD5" stroke-width="1.5"/>
            <circle cx="45" cy="33" r="11" fill="#FDF3EE" stroke="#CC785C" stroke-width="1.5"/>
            <text x="45" y="37" text-anchor="middle" font-size="11" font-weight="bold" fill="#CC785C">{candidate_count}</text>
            <text x="65" y="29" font-size="11.5" font-weight="600" fill="#2D2A26">候选文献初筛池</text>
            <text x="65" y="44" font-size="9.5" fill="#79746C">多源检索与递归语义打分</text>

            <!-- 汇聚连线流 -->
            <path d="M 45 54 C 45 95, 95 105, 110 128" stroke="#CC785C" stroke-width="2.5" stroke-dasharray="4,3" fill="none" class="pulse-flow"/>
            <path d="M 175 54 C 175 95, 125 105, 110 128" stroke="#CC785C" stroke-width="2.5" stroke-dasharray="4,3" fill="none" class="pulse-flow"/>
            <path d="M 110 54 L 110 128" stroke="#E2DDD5" stroke-width="1.5" stroke-dasharray="2,2" fill="none"/>

            <!-- 漏斗漏斗颈部：学者人在回路核心节点 -->
            <polygon points="65,102 155,102 132,148 88,148" fill="#FDF3EE" stroke="#E27D60" stroke-width="1.2" opacity="0.65"/>
            <circle cx="110" cy="138" r="21" fill="url(#amberGrad)" filter="url(#glow)"/>
            <text x="110" y="134" text-anchor="middle" font-size="9" font-weight="bold" fill="#FFFFFF">HITL</text>
            <text x="110" y="146" text-anchor="middle" font-size="8" font-weight="500" fill="#FFFFFF">学者精选</text>

            <!-- 向下发散流线 -->
            <path d="M 110 160 L 110 205" stroke="url(#sageGrad)" stroke-width="3" stroke-dasharray="5,3" fill="none" class="pulse-flow"/>
            <polygon points="106,206 114,206 110,212" fill="#2D6A3E"/>

            <!-- 底部核心研读池节点 -->
            <rect x="25" y="218" width="170" height="48" rx="8" fill="#F0F5F0" stroke="#D1E3D3" stroke-width="1.5"/>
            <circle cx="45" cy="242" r="12" fill="url(#sageGrad)"/>
            <text x="45" y="246" text-anchor="middle" font-size="11" font-weight="bold" fill="#FFFFFF">{selected_count}</text>
            <text x="66" y="238" font-size="12" font-weight="700" fill="#2D6A3E">核心研读文献池</text>
            <text x="66" y="253" font-size="9.5" fill="#588157">精选收敛率: {pct}% (深度研判)</text>
        </svg>
        <div style="font-size: 11.5px; color: #79746C; text-align: center; line-height: 1.5; margin-top: 6px;">
            <span>初筛候选: <b>{candidate_count}</b> 篇</span> ➔ <span>精选核心: <b>{selected_count}</b> 篇</span><br/>
            <span style="font-size: 10.5px; color: #9A4122;">仅对已选文献启动深度要素抽取与大纲规划</span>
        </div>
    </div>
    """


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
        lines.append(f"#### 📄 核心文献 {idx}：《{f.get('title', '未知文献')}》({f.get('publication_year', 2024)})")
        lines.append(f"- **研究背景与动机**：{f.get('background', '未注明')}")
        inno = '；'.join(f.get('core_innovations', [])) if isinstance(f.get('core_innovations'), list) else str(f.get('core_innovations', '未注明'))
        lines.append(f"- **核心创新机制**：{inno}")
        lines.append(f"- **研究方法与技术范式**：{f.get('methodology', '未注明')}")
        conc = '；'.join(f.get('main_conclusions', [])) if isinstance(f.get('main_conclusions'), list) else str(f.get('main_conclusions', '未注明'))
        lines.append(f"- **主要实证结论**：{conc}")
        lines.append("")
    return "\n".join(lines)


# ==================== 工作流事件调度 (Decision 1 & 3: 单阶段人在回路漏斗) ====================
def start_research_flow(query, keywords_str, years, max_papers, pause_hitl, data_file, refs_text, progress=gr.Progress(track_tqdm=True)):
    global current_active_task_id

    progress(0.05, desc="✦ [0/5] 学术意图规划：正在解耦核心科学选题与跨学科关键词...")
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
    current_active_task_id = state.task_id

    # 0. 意图理解与规划 (LLM Think First)
    state.status = WorkflowStatus.RUNNING
    state.current_step = WorkflowStep.INTENT_FORMULATION
    plan = intent_agent.formulate(query=query, user_keywords=keywords, years=int(years), max_papers=candidate_target)
    state.data["intent_plan"] = plan.model_dump()
    state.completed_steps.append("intent_formulation")
    engine.save_checkpoint(state)

    # 1. 跨源检索候选文献池 (~20篇)
    progress(0.20, desc="✦ [1/5] 文献初筛：正在通过 OpenAlex 与 Europe PMC 跨源检索候选文献池 (~20篇)...")
    state.current_step = WorkflowStep.LITERATURE_RETRIEVAL
    lit_res = lit_agent.run(
        query=query,
        keywords=keywords,
        years=int(years),
        max_papers=candidate_target,
        search_queries=plan.search_queries,
        filter_keywords=plan.filter_keywords,
    )
    progress(0.35, desc="✦ [1/5] 候选文献已检索就绪，正在生成学术中文要点索引表...")
    candidate_papers = lit_res["papers"]
    state.data["candidate_pool"] = candidate_papers
    state.data["literature_pool"] = candidate_papers
    state.completed_steps.append("literature_retrieval")
    engine.save_checkpoint(state)

    # 格式化候选文献选项与情报详情表
    choices = [
        f"[{i+1}] {p['title']} ({p.get('publication_year', 2024)}, {p.get('source', 'OpenAlex')}) | 相关度: {int(float(p.get('relevance_score', 0.8)) * 100)}%"
        for i, p in enumerate(candidate_papers)
    ]
    default_selected = choices[:6] if len(choices) >= 6 else choices
    candidate_table_rows = [
        [i+1, p['title'], p.get('chinese_summary', '围绕该课题开展的学术实证研究'), p.get('publication_year', 2024), p.get('source', 'OpenAlex'), f"{int(float(p.get('relevance_score', 0.8)) * 100)}%"]
        for i, p in enumerate(candidate_papers)
    ]
    preview_rows = [
        [i+1, p['title'], p.get('publication_year', 2024), f"{int(float(p.get('relevance_score', 0.8)) * 100)}%"]
        for i, p in enumerate(candidate_papers[:len(default_selected)])
    ]

    funnel_svg = render_funnel_svg(len(candidate_papers), len(default_selected))
    counter_md = f"### 🎯 已选核心文献池: **{len(default_selected)}** / {len(candidate_papers)} 篇\n> AI 将仅针对您选中的核心文献展开深度要素抽取、新论文综述大纲规划与初稿长文合成。"

    if pause_hitl:
        progress(0.40, desc="✦ [人在回路] 20篇候选文献池已就绪，工作流断点挂起，等待学者点选核心文献...")
        engine.pause_task(state.task_id, reason="人在回路：已检索20篇候选文献池，等待学者挑选核心文献")
        state = engine.load_checkpoint(state.task_id)
        pipeline_html = render_claude_pipeline(state.current_step.value, state.status.value)
        return (
            pipeline_html,
            gr.update(visible=True),                # 展开人在回路漏斗卡片
            gr.update(choices=choices, value=default_selected), # 填充候选文献复选框
            candidate_table_rows,                   # 候选文献情报详情表
            funnel_svg,                             # 中间漏斗 SVG 连线流
            counter_md,                             # 右侧计数状态
            preview_rows,                           # 右侧已选文献预览
            gr.update(visible=False),               # 成果画布保持隐藏
            "",                                     # synthesis_deliverable_md
            [],                                     # result_papers_table
            "",                                     # features_summary_md
            "",                                     # data_analysis_md
            [],                                     # charts_gallery
            "",                                     # formatted_citations_box
            "",                                     # workflow_meta_json
        )

    # 若关闭人在回路，默认直接使用推荐 Top 6 文献平滑续跑
    selected_papers = candidate_papers[:6]
    res = continue_research_flow(state.task_id, selected_papers, data_file, refs_text, progress=progress)
    return (
        res[0],
        gr.update(visible=False),
        gr.update(choices=choices, value=default_selected),
        candidate_table_rows,
        funnel_svg,
        counter_md,
        preview_rows,
        res[2],
        res[3],
        res[4],
        res[5],
        res[6],
        res[7],
        res[8],
        res[9],
    )


def update_candidate_selection_view(selected_choices):
    """当学者在复选框中勾选/取消时，动态更新中间漏斗与右侧精选预览"""
    global current_active_task_id
    candidate_papers = []
    if current_active_task_id:
        state = engine.load_checkpoint(current_active_task_id)
        if state:
            candidate_papers = state.data.get("candidate_pool", [])

    sel_indices = []
    for c in selected_choices or []:
        m = re.match(r"^\[(\d+)\]", str(c))
        if m:
            sel_indices.append(int(m.group(1)) - 1)

    selected_papers = [candidate_papers[i] for i in sel_indices if 0 <= i < len(candidate_papers)]
    sel_count = len(selected_papers)
    cand_count = len(candidate_papers) if candidate_papers else 20

    funnel_svg = render_funnel_svg(candidate_count=cand_count, selected_count=sel_count)
    counter_md = f"### 🎯 已选核心文献池: **{sel_count}** / {cand_count} 篇\n> AI 将仅针对您选中的核心文献展开深度要素抽取、新论文综述大纲规划与初稿长文合成。"
    preview_rows = [
        [idx, p.get("title", ""), p.get("publication_year", 2024), f"{int(float(p.get('relevance_score', 0.8)) * 100)}%"]
        for idx, p in enumerate(selected_papers, 1)
    ]
    return funnel_svg, counter_md, preview_rows


def select_all_candidates_action():
    global current_active_task_id
    if not current_active_task_id:
        return []
    state = engine.load_checkpoint(current_active_task_id)
    if not state:
        return []
    papers = state.data.get("candidate_pool", [])
    return [
        f"[{i+1}] {p['title']} ({p.get('publication_year', 2024)}, {p.get('source', 'OpenAlex')}) | 相关度: {int(float(p.get('relevance_score', 0.8)) * 100)}%"
        for i, p in enumerate(papers)
    ]


def select_top6_candidates_action():
    global current_active_task_id
    if not current_active_task_id:
        return []
    state = engine.load_checkpoint(current_active_task_id)
    if not state:
        return []
    papers = state.data.get("candidate_pool", [])
    return [
        f"[{i+1}] {p['title']} ({p.get('publication_year', 2024)}, {p.get('source', 'OpenAlex')}) | 相关度: {int(float(p.get('relevance_score', 0.8)) * 100)}%"
        for i, p in enumerate(papers[:6])
    ]


def clear_candidate_selection_action():
    return []


def resume_research_with_selected_papers(selected_choices, data_file, refs_text, progress=gr.Progress(track_tqdm=True)):
    """学者确认选中文献后，恢复工作流，AI 仅深度处理所选核心文献"""
    global current_active_task_id
    if not current_active_task_id:
        return "", gr.update(visible=False), gr.update(visible=False), "", [], "", "", [], "", ""

    state = engine.load_checkpoint(current_active_task_id)
    if not state:
        return "", gr.update(visible=False), gr.update(visible=False), "", [], "", "", [], "", ""

    candidate_papers = state.data.get("candidate_pool", [])
    sel_indices = []
    for c in selected_choices or []:
        m = re.match(r"^\[(\d+)\]", str(c))
        if m:
            sel_indices.append(int(m.group(1)) - 1)

    selected_papers = [candidate_papers[i] for i in sel_indices if 0 <= i < len(candidate_papers)]
    if not selected_papers:
        selected_papers = candidate_papers[:6] if candidate_papers else []

    return continue_research_flow(state.task_id, selected_papers, data_file, refs_text, progress=progress)


def continue_research_flow(task_id, selected_papers, data_file, refs_text, progress=gr.Progress(track_tqdm=True)):
    state = engine.load_checkpoint(task_id)
    if not state:
        return "", gr.update(visible=False), gr.update(visible=False), "", [], "", "", [], "", ""

    state.data["selected_papers"] = selected_papers
    state.data["literature_pool"] = selected_papers
    state.status = WorkflowStatus.RUNNING
    engine.save_checkpoint(state)

    query = state.params.get("query", "通用智能体科研自动化")

    # 2. 深度要素抽取 (仅针对精选核心文献，100% 纯正学术中文)
    progress(0.45, desc=f"✦ [2/5] 要素抽取：正在深度解析已选 {len(selected_papers)} 篇核心文献机制与实验...")
    state.current_step = WorkflowStep.FEATURE_EXTRACTION
    features = rev_agent.batch_extract(selected_papers, topic=query)
    state.data["extracted_features"] = [f.model_dump() for f in features]
    state.completed_steps.append("feature_extraction")
    engine.save_checkpoint(state)

    # 3. 新论文文献综述大纲规划 (基于核心文献证据与领域逻辑)
    progress(0.65, desc="✦ [3/5] 大纲规划：正在推演新论文专属文献综述大纲...")
    state.current_step = WorkflowStep.OUTLINE_GENERATION
    outline_md = rev_agent.generate_review_outline(query, features)
    state.data["review_outline"] = outline_md
    state.completed_steps.append("outline_generation")
    engine.save_checkpoint(state)

    # 4. 综述初稿框架合成与防幻觉校验
    progress(0.80, desc="✦ [4/5] 综述初稿：正在合成综述长文初稿并执行 Citation Validator 双向核验...")
    state.current_step = WorkflowStep.REVIEW_SYNTHESIS
    review_draft = rev_agent.generate_review_draft(
        topic=query,
        outline=outline_md,
        features=features,
    )
    state.data["review_draft"] = review_draft
    state.completed_steps.append("review_synthesis")
    engine.save_checkpoint(state)

    # 5. 实验数据统计
    progress(0.92, desc="✦ [5/5] 实验数据：正在进行实验数据收敛性统计、Tukey IQR 离群点审计与科研制图...")
    state.current_step = WorkflowStep.DATA_ANALYSIS
    csv_source = data_file.name if data_file is not None and hasattr(data_file, "name") else get_sample_experiment_csv()
    data_res = data_agent.run(csv_source, task_id=state.task_id)
    state.data["data_analysis_report"] = data_res["report_markdown"]
    state.data["generated_charts"] = data_res["charts"]
    state.completed_steps.append("data_analysis")
    engine.save_checkpoint(state)

    # 6. 参考文献国标排版
    progress(0.98, desc="✦ [6/5] 国标排版：正在执行参考文献 GB/T 7714-2015 格式校对与规范纠错...")
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
    state.completed_steps.append("reference_format")

    # 完成
    progress(1.00, desc="✦ [交付完毕] UniScholar 通用智能体科研全流程成果已成功交付！")
    state.status = WorkflowStatus.COMPLETED
    state.current_step = WorkflowStep.COMPLETED
    engine.save_checkpoint(state)

    table_rows = format_literature_table(selected_papers)
    features_md = format_features_markdown(state.data.get("extracted_features", []))
    pipeline_html = render_claude_pipeline("completed", WorkflowStatus.COMPLETED.value)
    yuanjing_config = json.dumps(engine.export_yuanjing_workflow_config(), ensure_ascii=False, indent=2)

    # 组合交付物成果大画卷：契合赛题第二大核心功能（文献综述大纲规划与初稿框架）
    synthesis_deliverable_md = f"""# 📑 成果交付：基于核心文献规划的文献综述大纲与初稿框架

> **赛题命题对应**：中国联通省级分公司赛道（功能二）——基于通用智能体结构化逻辑自动生成文献综述大纲与初稿框架。  
> **精选文献支持**：本成果由学者在回路断点精选的 **{len(selected_papers)}** 篇核心文献驱动，正文全部引文均经 UniScholar Citation Validator 真实文献双向白名单交叉验证。

---

## ✦ 一、 新论文文献综述大纲规划 (Structured Research Outline)
{outline_md}

---

## ✦ 二、 学术文献综述初稿框架全文 (Scholarly Review & Synthesis Draft)
{review_draft}
"""

    return (
        pipeline_html,
        gr.update(visible=False),  # 隐藏人在回路漏斗卡片
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
    import requests
    s = requests.Session()
    s.trust_env = False
    url = base_url.strip().rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions" if url.endswith("/v1") else "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    payload = {
        "model": model.strip(),
        "messages": [{"role": "user", "content": "1+1等于几？请直接给出数字。"}],
        "max_tokens": 50,
    }
    t0 = time.time()
    try:
        r = s.post(url, headers=headers, json=payload, timeout=20)
        dt = round(time.time() - t0, 2)
        if r.status_code == 200:
            res_json = r.json()
            msg = res_json.get("choices", [{}])[0].get("message", {})
            ans = msg.get("content") or msg.get("reasoning_content") or "成功响应"
            return f"✅ **连通测试成功！** 模型 `{model}` 响应正常（耗时 {dt} 秒）。\n> 示例回复片段: `{str(ans).strip()[:80]}`"
        elif r.status_code == 403:
            return f"❌ **鉴权或额度不足 (HTTP 403)**: 当前 Key 额度可能为 0 或无权调用模型 `{model}`。\n详情: `{r.text[:200]}`"
        elif r.status_code == 500:
            return f"⚠️ **上游服务器临时报错 (HTTP 500)**: TokenRouter 或上游服务提供商暂时不可用（`upstream error`）。\n详情: `{r.text[:200]}`"
        else:
            return f"⚠️ **上游返回状态码 HTTP {r.status_code}**:\n`{r.text[:200]}`"
    except Exception as e:
        return f"❌ **网络请求超时或异常**: `{str(e)}`"


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
        f"LLM_TIMEOUT=25\n"
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
def get_claude_theme():
    """构建严格匹配 Anthropic Claude 风格的 Warm Linen & Terracotta 主题"""
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.orange,
        neutral_hue=gr.themes.colors.stone,
    ).set(
        # 页面与卡片底色 (彻底覆盖暗色变量，杜绝黑白混杂)
        body_background_fill="#FAF9F5",
        body_background_fill_dark="#FAF9F5",
        background_fill_primary="#FFFFFF",
        background_fill_primary_dark="#FFFFFF",
        background_fill_secondary="#F5F2EB",
        background_fill_secondary_dark="#F5F2EB",

        # 卡片与组件边框与背景
        block_background_fill="#FFFFFF",
        block_background_fill_dark="#FFFFFF",
        block_border_color="#E8E4DB",
        block_border_color_dark="#E8E4DB",
        block_label_text_color="#6E685E",
        block_label_text_color_dark="#6E685E",
        block_title_text_color="#2D2A26",
        block_title_text_color_dark="#2D2A26",

        # 字体与排版颜色
        body_text_color="#2D2A26",
        body_text_color_dark="#2D2A26",
        body_text_color_subdued="#79746C",
        body_text_color_subdued_dark="#79746C",

        # 输入控件
        input_background_fill="#FFFFFF",
        input_background_fill_dark="#FFFFFF",
        input_border_color="#E2DDD5",
        input_border_color_dark="#E2DDD5",
        input_border_color_focus="#CC785C",
        input_border_color_focus_dark="#CC785C",
        input_placeholder_color="#A8A196",
        input_placeholder_color_dark="#A8A196",

        # 克劳德陶土珊瑚色主按钮 (#CC785C)
        button_primary_background_fill="#CC785C",
        button_primary_background_fill_dark="#CC785C",
        button_primary_background_fill_hover="#B8654B",
        button_primary_background_fill_hover_dark="#B8654B",
        button_primary_text_color="#FFFFFF",
        button_primary_text_color_dark="#FFFFFF",

        # 次级按钮
        button_secondary_background_fill="#FFFFFF",
        button_secondary_background_fill_dark="#FFFFFF",
        button_secondary_background_fill_hover="#F7F4EE",
        button_secondary_background_fill_hover_dark="#F7F4EE",
        button_secondary_border_color="#E2DDD5",
        button_secondary_border_color_dark="#E2DDD5",
        button_secondary_text_color="#4D4740",
        button_secondary_text_color_dark="#4D4740",

        # 交互组件 (单选、复选、滑块)
        checkbox_background_color="#FFFFFF",
        checkbox_background_color_dark="#FFFFFF",
        checkbox_background_color_selected="#CC785C",
        checkbox_background_color_selected_dark="#CC785C",
        checkbox_border_color="#D1CABE",
        checkbox_border_color_dark="#D1CABE",
        slider_color="#CC785C",
        slider_color_dark="#CC785C",

        # 装饰与强调线条
        border_color_primary="#E8E4DB",
        border_color_primary_dark="#E8E4DB",
        border_color_accent="#CC785C",
        border_color_accent_dark="#CC785C",
        color_accent_soft="#FDF3EE",
        color_accent_soft_dark="#FDF3EE",
    )


def get_claude_css():
    """完整注入 CSS 样式表，双重兜底强制消除 Gradio 暗色残留并应用 Claude 美学"""
    return """
    /* 1. 强制系统与根节点锁定浅色暖调 */
    :root, html, body, .gradio-container, gradio-app, .dark, [class*="dark"] {
        color-scheme: light !important;
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
        background-color: #FAF9F5 !important;
        color: #2D2A26 !important;
    }

    /* 2. 彻底抹平所有带有 dark 类的子元素深色背景，杜绝“一块黑一块白” */
    .dark div, .dark section, .dark main, .dark form, .dark span, .dark p, .dark label,
    .dark .block, .dark .gr-box, .dark .gr-panel, .dark .gr-input,
    .dark textarea, .dark input, .dark select,
    gradio-app.dark .block, gradio-app.dark textarea, gradio-app.dark input {
        background-color: #FFFFFF !important;
        color: #2D2A26 !important;
        border-color: #E2DDD5 !important;
    }

    /* 3. 页面顶层容器与排版居中 */
    body, .gradio-container {
        background-color: #FAF9F5 !important;
        color: #2D2A26 !important;
        max-width: 1300px !important;
        margin: 0 auto !important;
        padding-top: 24px !important;
        padding-bottom: 60px !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
    }

    /* 4. 顶部 Claude 品牌导航栏 */
    .claude-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 18px 24px;
        background: #FFFFFF !important;
        border-radius: 16px;
        border: 1px solid #E8E4DB;
        box-shadow: 0 2px 10px rgba(0,0,0,0.02);
        margin-bottom: 20px;
    }
    .claude-brand {
        font-size: 20px;
        font-weight: 700;
        color: #2D2A26 !important;
        display: flex;
        align-items: center;
        gap: 10px;
        letter-spacing: -0.3px;
    }
    .claude-logo-icon {
        color: #CC785C !important;
        font-size: 22px;
    }
    .claude-tag {
        font-size: 11px;
        background: #FDF3EE !important;
        color: #CC785C !important;
        padding: 3px 10px;
        border-radius: 16px;
        font-weight: 600;
        border: 1px solid #F5C6B5;
    }

    /* 5. 核心输入卡片 */
    .claude-card {
        background: #FFFFFF !important;
        border: 1px solid #E8E4DB !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 4px 18px rgba(0,0,0,0.02) !important;
        margin-bottom: 20px !important;
    }

    /* 6. 克劳德陶土色主按钮 */
    .claude-primary-btn {
        background: #CC785C !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        box-shadow: 0 4px 12px rgba(204,120,92,0.25) !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }
    .claude-primary-btn:hover {
        background: #B8654B !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 16px rgba(204,120,92,0.35) !important;
    }

    /* 7. 人在回路漏斗交互卡片 */
    .claude-hitl-box {
        background: #FEFBF4 !important;
        border: 1.5px solid #EBDCC2 !important;
        border-radius: 16px !important;
        padding: 22px !important;
        box-shadow: 0 6px 24px rgba(160,100,0,0.07) !important;
        margin-bottom: 24px !important;
    }
    .claude-resume-btn {
        background: #CC785C !important;
        color: #FFFFFF !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(204,120,92,0.3) !important;
        width: 100% !important;
        padding: 12px 20px !important;
        font-size: 15px !important;
    }
    .claude-resume-btn:hover {
        background: #B8654B !important;
        transform: translateY(-1px) !important;
    }

    /* 8. 成果画布 */
    .claude-canvas {
        background: #FFFFFF !important;
        border: 1px solid #E8E4DB !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.02) !important;
    }

    /* 9. 输入框和标签排版 */
    label span {
        color: #6E685E !important;
        font-weight: 600 !important;
        font-size: 12.5px !important;
    }
    textarea, input[type="text"], input[type="number"] {
        border-color: #E2DDD5 !important;
        background-color: #FFFFFF !important;
        color: #2D2A26 !important;
        border-radius: 8px !important;
    }
    textarea:focus, input:focus {
        border-color: #CC785C !important;
        box-shadow: 0 0 0 1.5px rgba(204,120,92,0.25) !important;
    }

    /* 10. 漏斗动效与流线样式 */
    @keyframes pulseFlow {
        from { stroke-dashoffset: 20; }
        to { stroke-dashoffset: 0; }
    }
    .pulse-flow {
        animation: pulseFlow 1.6s linear infinite;
    }
    .claude-checkbox-group label {
        padding: 6px 10px !important;
        border-radius: 8px !important;
        transition: background 0.15s ease !important;
    }
    .claude-checkbox-group label:hover {
        background: #FAF6EF !important;
    }

    /* 11. Markdown 学术排版与代码块高质感渲染 */
    .prose, .markdown {
        color: #2D2A26 !important;
        line-height: 1.75 !important;
    }
    .prose h1, .prose h2, .prose h3, .markdown h1, .markdown h2, .markdown h3 {
        color: #2D2A26 !important;
        font-weight: 700 !important;
        letter-spacing: -0.2px;
    }
    .prose hr, .markdown hr {
        border-color: #E8E4DB !important;
    }

    /* 严谨的学术表格样式 */
    .prose table, .markdown table, table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 16px 0 !important;
        background-color: #FFFFFF !important;
        border: 1px solid #E8E4DB !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    .prose th, .markdown th, th {
        background-color: #F8F5EE !important;
        color: #2D2A26 !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        padding: 10px 14px !important;
        border-bottom: 2px solid #E2DDD5 !important;
        text-align: left !important;
    }
    .prose td, .markdown td, td {
        padding: 10px 14px !important;
        border-bottom: 1px solid #EFECE6 !important;
        background-color: #FFFFFF !important;
        color: #2D2A26 !important;
        font-size: 13px !important;
    }
    .prose tr:hover td, .markdown tr:hover td, tr:hover td {
        background-color: #FAF8F5 !important;
    }

    /* 行内代码与引用标签 */
    code, pre, .prose code, .markdown code, table code, span code {
        background-color: #F4F0E8 !important;
        color: #9A4122 !important;
        padding: 2px 6px !important;
        border-radius: 5px !important;
        font-size: 0.88em !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        border: 1px solid #E8DFD1 !important;
        font-weight: 500 !important;
    }
    pre code {
        padding: 0 !important;
        border: none !important;
        background-color: transparent !important;
    }
    pre {
        background-color: #FAF8F5 !important;
        border: 1px solid #E8E4DB !important;
        border-radius: 8px !important;
        padding: 14px !important;
    }

    /* 学术引用块 */
    .prose blockquote, .markdown blockquote, blockquote {
        border-left: 3.5px solid #CC785C !important;
        background: #FBF9F4 !important;
        padding: 10px 16px !important;
        margin: 12px 0 !important;
        border-radius: 0 8px 8px 0 !important;
        color: #59534B !important;
    }

    /* 14. 极具人文科研质感的流光进度条动效与呼吸指示器 */
    @keyframes progressShimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    @keyframes pulseGlow {
        0% { transform: scale(0.92); box-shadow: 0 0 0 0 rgba(194, 94, 62, 0.45); }
        70% { transform: scale(1); box-shadow: 0 0 0 7px rgba(194, 94, 62, 0); }
        100% { transform: scale(0.92); box-shadow: 0 0 0 0 rgba(194, 94, 62, 0); }
    }
    @keyframes pulseAmber {
        0% { transform: scale(0.92); box-shadow: 0 0 0 0 rgba(217, 119, 6, 0.45); }
        70% { transform: scale(1); box-shadow: 0 0 0 7px rgba(217, 119, 6, 0); }
        100% { transform: scale(0.92); box-shadow: 0 0 0 0 rgba(217, 119, 6, 0); }
    }
    .claude-progress-shimmer {
        background-size: 200% 100% !important;
        animation: progressShimmer 2.8s ease-in-out infinite !important;
    }
    .claude-pulse-active {
        animation: pulseGlow 1.8s infinite !important;
    }
    .claude-pulse-paused {
        animation: pulseAmber 1.8s infinite !important;
    }

    footer { display: none !important; }
    """


def get_claude_js():
    """客户端 JavaScript：强制清理暗色模式，并实时监听阻止 dark 类被重新注入"""
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
    """向 HTML Head 注入元标签和高优先级样式，确保浏览器首屏即以纯粹浅色渲染"""
    return """
    <meta name="color-scheme" content="light">
    <style>
        :root, html, body {
            color-scheme: light !important;
            background-color: #FAF9F5 !important;
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
                <span>工作流标准：<b>元景万悟 v2.0 (DAG)</b></span>
            </div>
        </div>
        """)

        # 核心 Pipeline 流程轴
        pipeline_status_component = gr.HTML(render_claude_pipeline("init", "IDLE"))

        # ==================== 0. 大模型大脑连接与网关配置抽屉 ====================
        default_key = os.getenv("LLM_API_KEY", "")
        masked_key = (default_key[:6] + "..." + default_key[-4:]) if len(default_key) > 10 else (default_key or "未配置")
        with gr.Accordion("⚙️ 大模型大脑连接与网关配置 (已接入 TokenRouter · 支持随时在线测通/切换)", open=False):
            with gr.Row():
                ui_base_url = gr.Textbox(
                    label="API Base URL",
                    value=os.getenv("LLM_BASE_URL", "https://api.tokenrouter.com/v1"),
                    placeholder="https://api.tokenrouter.com/v1 或 https://api.deepseek.com/v1",
                    scale=5,
                )
                ui_model = gr.Textbox(
                    label="模型名称 (Model)",
                    value=os.getenv("LLM_MODEL", "z-ai/glm-5.3-free"),
                    placeholder="z-ai/glm-5.3-free 或 deepseek-chat",
                    scale=4,
                )
                ui_api_key = gr.Textbox(
                    label="API Key",
                    value=default_key,
                    type="password",
                    placeholder="sk-...",
                    scale=5,
                )
            with gr.Row():
                ui_test_btn = gr.Button("🔌 测试大模型实时连通性", size="sm")
                ui_save_btn = gr.Button("💾 保存并应用配置到 .env", variant="primary", size="sm", elem_classes=["claude-primary-btn"])
            ui_status_info = gr.Markdown(f"当前已绑定模型：`{os.getenv('LLM_MODEL', 'z-ai/glm-5.3-free')}` | Key 状态：`{masked_key}`")

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
                    papers_slider = gr.Slider(minimum=15, maximum=40, value=20, step=5, label="初筛候选文献池规模 (~20篇)")

            with gr.Row():
                pause_hitl_checkbox = gr.Checkbox(
                    label="✦ 开启人在回路 (HITL) 漏斗遴选：在初筛召回 ~20 篇候选文献后自动暂停，供学者勾选核心文献再继续深度研讨",
                    value=True,
                )

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

        # ==================== 2. 人在回路漏斗连线流卡片 (Decision 1 & 3) ====================
        with gr.Group(visible=False, elem_classes=["claude-hitl-box"]) as hitl_card:
            gr.HTML("""
            <div style="font-weight: 700; font-size: 16px; color: #A06400; margin-bottom: 4px; display: flex; align-items: center; gap: 8px;">
                <span>✦ 工作流已在候选文献断点挂起 (Human-in-the-Loop Checkpoint)</span>
            </div>
            <div style="font-size: 13.5px; color: #6E5325; margin-bottom: 16px; line-height: 1.6;">
                智能体已完成学术意图规划与多源文献召回，为您构建了包含 <b>约 20 篇相关前沿论文的初筛池</b>。请学者审阅并勾选最想要精读的 <b>5-8 篇核心论文</b>。确认后，AI 将仅针对选中文献展开深度微观特征提取、新论文大纲规划与高水平文献综述初稿框架合成！
            </div>
            """)

            # 漏斗三列连线流布局
            with gr.Row():
                # 左侧：20篇候选文献池多选与情报表
                with gr.Column(scale=6):
                    gr.Markdown("### 📚 1. 初筛候选文献池 (Candidate Pool)\n*请在下方勾选拟重点研讨的核心文献（支持快捷一键精选）：*")
                    hitl_candidate_checkboxes = gr.CheckboxGroup(
                        choices=[],
                        value=[],
                        label="候选文献池 (勾选作为核心精读样本)：",
                        elem_classes=["claude-checkbox-group"],
                    )
                    with gr.Row():
                        btn_select_all = gr.Button("全选", size="sm")
                        btn_select_top6 = gr.Button("推荐精选 Top 6", size="sm", variant="secondary")
                        btn_clear_all = gr.Button("清空选择", size="sm")

                    hitl_candidate_detail_table = gr.Dataframe(
                        headers=["序号", "论文标题", "中文要点导读", "年份", "数据源/期刊", "相关度"],
                        datatype=["number", "str", "str", "number", "str", "str"],
                        label="📋 候选文献详细情报与中文摘要索引",
                        wrap=True,
                    )

                # 中间：视觉漏斗连线流 SVG 动画
                with gr.Column(scale=3):
                    funnel_svg_html = gr.HTML(render_funnel_svg(20, 6))

                # 右侧：已选核心文献池预览与续跑按钮
                with gr.Column(scale=5):
                    hitl_selected_counter_md = gr.Markdown("### 🎯 2. 已选核心文献池: **6** / 20 篇\n> 点击下方按钮即可将选中文献注入智能体，启动要素深度抽取与大纲合成。")
                    hitl_selected_preview = gr.Dataframe(
                        headers=["已选序号", "核心论文标题", "发表年份", "相关度"],
                        datatype=["number", "str", "number", "str"],
                        label="🌟 拟注入智能体深度抽取与大纲生成的文献池",
                        wrap=True,
                    )
                    resume_flow_btn = gr.Button(
                        "✦ 确认选中文献并启动AI深度研判与大纲生成 ➔",
                        variant="primary",
                        elem_classes=["claude-resume-btn"],
                        size="lg",
                    )

        # ==================== 3. 最终科研成果大画布 (Decision 2: 赛题核心功能交付) ====================
        with gr.Group(visible=False, elem_classes=["claude-canvas"]) as result_workspace:
            gr.HTML("""
            <div style="font-size: 16px; font-weight: 700; color: #2D2A26; margin-bottom: 16px; border-bottom: 1.5px solid #E8E4DB; padding-bottom: 8px; display: flex; justify-content: space-between;">
                <span>📑 UniScholar 全流程科研综合成果画布 (All Research Deliverables)</span>
                <span style="font-size: 12px; color: #2D6A3E; font-weight: 500;">✓ 已通过 Citation Validator 真实文献防幻觉检验</span>
            </div>
            """)

            with gr.Tabs():
                with gr.TabItem("📄 综述大纲规划与初稿框架 (核心成果)"):
                    final_report_md = gr.Markdown()

                with gr.TabItem("📚 精选核心文献池与特征萃取"):
                    result_papers_table = gr.Dataframe(
                        headers=["序号", "论文标题", "年份", "被引频次", "相关度得分", "数据源"],
                        datatype=["number", "str", "number", "number", "str", "str"],
                        label="📚 学者精选核心文献池 (已注入下游深度解析)",
                        wrap=True,
                    )
                    features_summary_md = gr.Markdown()

                with gr.TabItem("📊 实验数据初步统计与科研图表"):
                    data_analysis_md = gr.Markdown()
                    charts_gallery = gr.Gallery(label="Matplotlib 渲染科研图表 (折线图 / 箱线图 / 直方图)", columns=2, height="auto")

                with gr.TabItem("📐 规范参考文献库 (GB/T 7714-2015)"):
                    formatted_citations_box = gr.Markdown()

                with gr.TabItem("⚙️ 联通元景工作流标准配置与执行轨迹"):
                    workflow_meta_json = gr.Code(language="json", label="workflow_config.json (元景万悟 DAG 编排格式)")

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
        # 1. 启动工作流
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
                hitl_candidate_checkboxes,
                hitl_candidate_detail_table,
                funnel_svg_html,
                hitl_selected_counter_md,
                hitl_selected_preview,
                result_workspace,
                final_report_md,
                result_papers_table,
                features_summary_md,
                data_analysis_md,
                charts_gallery,
                formatted_citations_box,
                workflow_meta_json,
            ],
        )

        # 2. 复选框状态动态联动
        hitl_candidate_checkboxes.change(
            fn=update_candidate_selection_view,
            inputs=[hitl_candidate_checkboxes],
            outputs=[funnel_svg_html, hitl_selected_counter_md, hitl_selected_preview],
        )

        # 3. 快捷选择操作
        btn_select_all.click(
            fn=select_all_candidates_action,
            inputs=[],
            outputs=[hitl_candidate_checkboxes],
        )
        btn_select_top6.click(
            fn=select_top6_candidates_action,
            inputs=[],
            outputs=[hitl_candidate_checkboxes],
        )
        btn_clear_all.click(
            fn=clear_candidate_selection_action,
            inputs=[],
            outputs=[hitl_candidate_checkboxes],
        )

        # 4. 确认核心文献并续跑至交付
        resume_flow_btn.click(
            fn=resume_research_with_selected_papers,
            inputs=[hitl_candidate_checkboxes, data_file_input, refs_text_input],
            outputs=[
                pipeline_status_component,
                hitl_card,
                result_workspace,
                final_report_md,
                result_papers_table,
                features_summary_md,
                data_analysis_md,
                charts_gallery,
                formatted_citations_box,
                workflow_meta_json,
            ],
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    launch_claude_ui(demo, server_name="127.0.0.1", server_port=7860, inbrowser=False)

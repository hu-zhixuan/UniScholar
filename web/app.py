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
from utils.llm_client import LLMClient
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
        lines.append(f"#### 📄 文献 {idx}：《{f.get('title', '未知文献')}》({f.get('publication_year', 2024)})")
        lines.append(f"- **研究背景与动机**：{f.get('background', '未注明')}")
        inno = '; '.join(f.get('core_innovations', [])) if isinstance(f.get('core_innovations'), list) else str(f.get('core_innovations', '未注明'))
        lines.append(f"- **核心创新突破**：{inno}")
        lines.append(f"- **研究方法与技术方案**：{f.get('methodology', '未注明')}")
        conc = '; '.join(f.get('main_conclusions', [])) if isinstance(f.get('main_conclusions'), list) else str(f.get('main_conclusions', '未注明'))
        lines.append(f"- **主要研究结论**：{conc}")
        lines.append("")
    return "\n".join(lines)


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

    table_rows = format_literature_table(lit_res["papers"])

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
            table_rows,                # 填入精选文献池表格
            outline_md,                # 填入生成的大纲初稿
            gr.update(visible=False),  # 成果画布保持隐藏
            "",
            [],
            "",
            "",
            [],
            "",
            "",
        )

    return continue_research_flow(state.task_id, outline_md, data_file, refs_text)


def continue_research_flow(task_id, approved_outline, data_file, refs_text):
    state = engine.load_checkpoint(task_id)
    if not state:
        return "", gr.update(visible=False), [], "", gr.update(visible=False), "", [], "", "", [], "", ""

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

    table_rows = format_literature_table(state.data.get("literature_pool", []))
    features_md = format_features_markdown(state.data.get("extracted_features", []))
    pipeline_html = render_claude_pipeline("completed", WorkflowStatus.COMPLETED.value)
    yuanjing_config = json.dumps(engine.export_yuanjing_workflow_config(), ensure_ascii=False, indent=2)

    return (
        pipeline_html,
        gr.update(visible=False),  # 隐藏人在回路卡片
        table_rows,                # 保留文献表格
        approved_outline,
        gr.update(visible=True),   # 展开成果画布
        state.data.get("review_draft", ""),
        table_rows,                # 成果画布中的文献表格
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

        # 字体与排版颜色 (柔和炭黑，非纯黑刺眼)
        body_text_color="#2D2A26",
        body_text_color_dark="#2D2A26",
        body_text_color_subdued="#79746C",
        body_text_color_subdued_dark="#79746C",

        # 输入控件 (纯白底、暖米边框、陶土色聚焦环)
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
        max-width: 1260px !important;
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

    /* 7. 人在回路温润琥珀卡片 */
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
    .claude-resume-btn:hover {
        background: #B8654B !important;
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

    /* 10. Markdown 学术排版与代码块高质感渲染 (彻底杜绝黑底方块) */
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

    /* 行内代码与引用标签 (解决黑底方块Bug，赋予暖卡其学术高亮) */
    code, pre, .prose code, .markdown code, table code, span code {
        background-color: #F4F0E8 !important;
        color: #9A4122 !important;
        padding: 2px 6px !important;
        border-radius: 5px !important;
        font-size: 0.88em !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace !important;
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

    /* 11. 隐藏无用的 Gradio 底部 */
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
        # DOM 内联注入样式表，确保即使外部资源加载延迟，界面也绝无黑白混杂
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
                <span>工作流标准：<b>元景万悟 v2.0</b></span>
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
                智能体已完成多源文献检索与实体去重，为您精筛出<b>高质量学术文献池</b>，并规划了<b>综述大纲初稿</b>。请学者审阅文献池并在线润色大纲，确认无误后点击右侧按钮无损续跑！
            </div>
            """)

            # 呈现精准文献池
            hitl_papers_table = gr.Dataframe(
                headers=["序号", "论文标题", "年份", "被引频次", "相关度得分", "数据源"],
                datatype=["number", "str", "number", "number", "str", "str"],
                label="📚 智能体精筛学术文献池 (Literature Pool)",
                wrap=True,
            )

            hitl_outline_editor = gr.Textbox(label="💡 文献综述大纲规划初稿 (支持在线编辑增删章节)", lines=8)
            with gr.Row():
                gr.Markdown("*(提示：修改后的内容将作为最新检查点保存，下游节点将基于您的修改继续合成正文)*")
                resume_flow_btn = gr.Button("确认大纲并生成最终成果画布 ➔", variant="primary", elem_classes=["claude-resume-btn"], size="lg")

        # ==================== 3. 最终科研成果大画布 ====================
        with gr.Group(visible=False, elem_classes=["claude-canvas"]) as result_workspace:
            gr.HTML("""
            <div style="font-size: 16px; font-weight: 700; color: #2D2A26; margin-bottom: 16px; border-bottom: 1.5px solid #E8E4DB; padding-bottom: 8px; display: flex; justify-content: space-between;">
                <span>📑 UniScholar 全流程科研综合成果画布 (All Research Deliverables)</span>
                <span style="font-size: 12px; color: #2D6A3E; font-weight: 500;">✓ 已通过 Citation Validator 真实文献防幻觉检验</span>
            </div>
            """)

            with gr.Tabs():
                with gr.TabItem("📄 学术文献综述与选题长文"):
                    final_report_md = gr.Markdown()

                with gr.TabItem("📚 精选学术文献池与特征萃取"):
                    result_papers_table = gr.Dataframe(
                        headers=["序号", "论文标题", "年份", "被引频次", "相关度得分", "数据源"],
                        datatype=["number", "str", "number", "number", "str", "str"],
                        label="📚 高相关精选文献池 (精准去重与语义过滤后)",
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
                hitl_papers_table,
                hitl_outline_editor,
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

        resume_flow_btn.click(
            fn=lambda outline, dfile, refs: continue_research_flow(current_active_task_id, outline, dfile, refs),
            inputs=[hitl_outline_editor, data_file_input, refs_text_input],
            outputs=[
                pipeline_status_component,
                hitl_card,
                hitl_papers_table,
                hitl_outline_editor,
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


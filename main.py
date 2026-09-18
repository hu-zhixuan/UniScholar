"""
UniScholar (联智学者) CLI 命令行入口与全流程工作流调度器
面向大创赛产业赛道（中国联通命题）：基于通用智能体工作流的科研全流程自动化系统。
"""

import argparse
import json
import logging
import os
import sys

# 避免 Windows 控制台 GBK 编码输出 Emoji 时崩溃
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 必须最先导入网络引导配置
import utils.network_config  # noqa: F401

from agents.data_agent import DataAgent
from agents.intent_agent import IntentAgent
from agents.literature_agent import LiteratureAgent
from agents.reference_agent import ReferenceAgent
from agents.review_agent import ReviewAgent
from core.workflow_engine import WorkflowEngine, WorkflowStatus, WorkflowStep
from offline_demo.demo_data import get_sample_experiment_csv, get_sample_references_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("UniScholar.Main")


def run_full_pipeline(
    query: str = "通用智能体科研自动化",
    keywords: list = None,
    years: int = 3,
    max_papers: int = 15,
    experiment_data: str = None,
    raw_references: str = None,
    pause_for_human: bool = False,
    task_id: str = None,
    output_dir: str = "output",
):
    """
    全流程执行函数：
    1. 文献检索与筛选 -> 2. 核心要素抽取 -> 3. 综述大纲 (支持暂停) -> 4. 综述正文 -> 5. 实验数据分析 -> 6. 国标参考文献
    """
    os.makedirs(output_dir, exist_ok=True)
    engine = WorkflowEngine()

    # 导出符合联通元景万悟标准的工作流配置文件
    engine.generate_wanwu_workflow_config()

    if not task_id:
        task_params = {
            "query": query,
            "keywords": keywords or ["AI Agent", "Workflow", "Scientific Research"],
            "years": years,
            "max_papers": max_papers,
        }
        state = engine.create_task(task_params)
        task_id = state.task_id
    else:
        state = engine.load_checkpoint(task_id)
        if not state:
            raise ValueError(f"未找到检查点任务 {task_id}")

    logger.info(f"🚀 开始执行 UniScholar 工作流任务: {task_id}")

    # ==================== Step 0: 学术意图理解与管线规划 (LLM Think First) ====================
    if "intent_formulation" not in state.completed_steps:
        state.status = WorkflowStatus.RUNNING
        state.current_step = WorkflowStep.INTENT_FORMULATION
        engine.log(state, "启动节点 0: 学术意图理解与检索管线规划 (LLM Think First)")

        intent_agent = IntentAgent()
        plan = intent_agent.formulate(
            query=state.params.get("query", query),
            user_keywords=state.params.get("keywords", keywords),
            years=state.params.get("years", years),
            max_papers=state.params.get("max_papers", max_papers),
        )
        state.data["intent_plan"] = plan.model_dump()
        state.completed_steps.append("intent_formulation")
        engine.save_checkpoint(state)
        engine.log(state, f"节点 0 完成: 提炼英文课题【{plan.academic_topic_en}】，规划高区分度检索短语: {plan.search_queries}")

    # ==================== Step 1: 文献检索与递归筛选 ====================
    if "literature_retrieval" not in state.completed_steps:
        state.status = WorkflowStatus.RUNNING
        state.current_step = WorkflowStep.LITERATURE_RETRIEVAL
        engine.log(state, "启动节点 1: 文献自动化检索与递归筛选")

        lit_agent = LiteratureAgent()
        plan_data = state.data.get("intent_plan", {})
        lit_res = lit_agent.run(
            query=state.params.get("query", query),
            keywords=state.params.get("keywords", keywords),
            years=state.params.get("years", years),
            max_papers=state.params.get("max_papers", max_papers),
            search_queries=plan_data.get("search_queries"),
            filter_keywords=plan_data.get("filter_keywords"),
        )
        state.data["candidate_pool"] = lit_res["papers"]
        state.data["literature_pool"] = lit_res["papers"]
        state.data["literature_stats"] = {
            "total_fetched": lit_res["total_fetched"],
            "selected_count": lit_res["selected_count"],
            "filtered_out_count": lit_res["filtered_out_count"],
        }
        state.completed_steps.append("literature_retrieval")
        engine.save_checkpoint(state)
        engine.log(state, f"节点 1 完成: 候选文献池包含 {len(lit_res['papers'])} 篇高相关文献")

        # 检查是否需要人工干预断点 (Decision 1: 候选文献池检出后挂起等待学者点选)
        if pause_for_human:
            engine.pause_task(state.task_id, reason="人在回路断点：已检索出候选文献池，等待学者挑选核心文献")
            print(f"\n[🛑 工作流已在候选文献断点暂停] 检查点任务 ID: {state.task_id}")
            print(f"已召回 {len(lit_res['papers'])} 篇候选文献。学者可在 WebUI 交互漏斗中点选核心文献，或指定任务 ID 断点续跑。")
            return state

    # ==================== 确定核心精读文献池 (过滤用户未选中的文献) ====================
    core_papers = state.data.get("selected_papers")
    if not core_papers:
        # 若未手动挑选，默认遴选 Top 6 篇高相关文献注入深度流水线
        all_candidates = state.data.get("candidate_pool") or state.data.get("literature_pool", [])
        core_papers = all_candidates[:6] if all_candidates else []
        state.data["selected_papers"] = core_papers
        state.data["literature_pool"] = core_papers

    # ==================== Step 2: 核心信息抽取 (仅深度解析所选核心文献) ====================
    if "feature_extraction" not in state.completed_steps:
        state.current_step = WorkflowStep.FEATURE_EXTRACTION
        engine.log(state, f"启动节点 2: 针对已选 {len(core_papers)} 篇核心文献进行深度要素与创新机制抽取")

        rev_agent = ReviewAgent()
        features = rev_agent.batch_extract(
            core_papers,
            topic=state.params.get("query", query),
        )
        state.data["extracted_features"] = [f.model_dump() for f in features]
        summary_md = rev_agent.generate_summary_collection(features)
        state.data["summary_collection_md"] = summary_md

        state.completed_steps.append("feature_extraction")
        engine.save_checkpoint(state)
        engine.log(state, f"节点 2 完成: 成功结构化抽取 {len(features)} 篇核心文献要素")

    # ==================== Step 3: 综述大纲生成 ====================
    if "outline_generation" not in state.completed_steps:
        state.current_step = WorkflowStep.OUTLINE_GENERATION
        engine.log(state, "启动节点 3: 基于精选核心文献规划新论文综述大纲")

        rev_agent = ReviewAgent()
        from agents.review_agent import PaperFeature
        features_objs = [PaperFeature(**f) for f in state.data.get("extracted_features", [])]
        outline_md = rev_agent.generate_review_outline(state.params.get("query", query), features_objs)
        state.data["review_outline"] = outline_md

        state.completed_steps.append("outline_generation")
        engine.save_checkpoint(state)
        engine.log(state, "节点 3 完成: 领域专属文献综述大纲已规划生成")

    # ==================== Step 4: 综述正文合成与防幻觉校验 ====================
    if "review_synthesis" not in state.completed_steps:
        state.current_step = WorkflowStep.REVIEW_SYNTHESIS
        engine.log(state, "启动节点 4: 综述初稿合成与 Citation Validator 引文校验")

        rev_agent = ReviewAgent()
        from agents.review_agent import PaperFeature
        features_objs = [PaperFeature(**f) for f in state.data.get("extracted_features", [])]
        review_draft = rev_agent.generate_review_draft(
            topic=state.params.get("query", query),
            outline=state.data.get("review_outline", ""),
            features=features_objs,
        )
        state.data["review_draft"] = review_draft
        state.completed_steps.append("review_synthesis")
        engine.save_checkpoint(state)
        engine.log(state, "节点 4 完成: 文献综述初稿已生成并通过引文防幻觉检验")

    # ==================== Step 5: 实验数据统计与科研绘图 ====================
    if "data_analysis" not in state.completed_steps:
        state.current_step = WorkflowStep.DATA_ANALYSIS
        engine.log(state, "启动节点 5: 实验数据初步统计与科研可视化")

        data_agent = DataAgent(output_dir=os.path.join(output_dir, "charts"))
        # 如果未提供具体文件，使用内置公开科研实验样例
        raw_csv_content = experiment_data or get_sample_experiment_csv()
        data_res = data_agent.run(
            raw_csv_content,
            task_id=state.task_id,
            topic=state.params.get("query", query),
        )

        state.data["data_analysis_report"] = data_res["report_markdown"]
        state.data["generated_charts"] = data_res["charts"]
        state.completed_steps.append("data_analysis")
        engine.save_checkpoint(state)
        engine.log(state, f"节点 5 完成: 数据统计完成，生成 {len(data_res['charts'])} 张科研图表")

    # ==================== Step 6: 参考文献国标排版与校对 ====================
    if "reference_format" not in state.completed_steps:
        state.current_step = WorkflowStep.REFERENCE_FORMAT
        ref_agent = ReferenceAgent()
        if raw_references:
            raw_ref_text = raw_references
        elif state.data.get("literature_pool"):
            pool = state.data.get("literature_pool", [])
            ref_lines = []
            for idx, p in enumerate(pool[:15], 1):
                authors = p.get("authors", [])
                auth_str = ", ".join(authors) if authors else "佚名"
                title = p.get("title", "未命名文献")
                year = p.get("publication_year", 2024)
                source = p.get("source", "学术期刊")
                ref_lines.append(f"[{idx}] {auth_str}. {title}. {source}, {year}.")
            raw_ref_text = "\n".join(ref_lines)
        else:
            raw_ref_text = get_sample_references_text()

        ref_res = ref_agent.run(raw_ref_text, target_format="GB/T 7714")

        state.data["formatted_references"] = ref_res["formatted_text"]
        state.data["reference_audit_reports"] = ref_res["audit_reports"]
        state.completed_steps.append("reference_format")
        engine.save_checkpoint(state)
        engine.log(state, f"节点 6 完成: 成功校对并排版 {ref_res['total_items']} 条参考文献")

    # ==================== 完成全流程 ====================
    state.status = WorkflowStatus.COMPLETED
    state.current_step = WorkflowStep.COMPLETED
    engine.log(state, "🎉 UniScholar 科研全流程智能体工作流执行完毕！")
    engine.save_checkpoint(state)

    # 导出最终总研报
    final_report_path = os.path.join(output_dir, f"{state.task_id}_final_report.md")
    with open(final_report_path, "w", encoding="utf-8") as f:
        f.write(f"# UniScholar 科研全流程综合成果报告\n\n")
        f.write(f"> 任务 ID: `{state.task_id}` | 生成时间: `{state.updated_at}`\n\n")
        f.write(state.data.get("review_draft", "") + "\n\n---\n\n")
        f.write(state.data.get("data_analysis_report", "") + "\n\n---\n\n")
        f.write("## 参考文献 (规范 GB/T 7714-2015 格式)\n\n" + state.data.get("formatted_references", ""))

    logger.info(f"📄 最终全流程科研研报已保存至: {final_report_path}")
    return state


def main():
    parser = argparse.ArgumentParser(description="UniScholar - 通用AI科研智能体应用系统")
    parser.add_argument("-q", "--query", default="通用智能体科研自动化", help="科研研究方向或主题")
    parser.add_argument("-k", "--keywords", default="AI Agent,Workflow,Research Automation", help="检索关键词，逗号分隔")
    parser.add_argument("-y", "--years", type=int, default=3, help="检索近年文献范围(年)")
    parser.add_argument("-m", "--max-papers", type=int, default=15, help="最大精选文献数量")
    parser.add_argument("-d", "--data", default=None, help="实验数据文件路径 (.csv/.xlsx)")
    parser.add_argument("-r", "--references", default=None, help="原始参考文献文件路径 (.txt)")
    parser.add_argument("--pause", action="store_true", help="在大纲节点自动暂停等待人工干预 (人在回路测试)")
    parser.add_argument("--resume", default=None, help="指定已暂停的任务 ID 并继续执行")
    parser.add_argument("--offline", action="store_true", help="启用评委无密钥离线演示模式")

    args = parser.parse_args()

    if args.offline:
        os.environ["OFFLINE_DEMO"] = "1"

    keywords_list = [k.strip() for k in args.keywords.split(",") if k.strip()]

    if args.resume:
        logger.info(f"恢复执行任务: {args.resume}")
        engine = WorkflowEngine()
        engine.resume_task(args.resume)
        run_full_pipeline(task_id=args.resume)
    else:
        run_full_pipeline(
            query=args.query,
            keywords=keywords_list,
            years=args.years,
            max_papers=args.max_papers,
            experiment_data=args.data,
            raw_references=args.references,
            pause_for_human=args.pause,
        )


if __name__ == "__main__":
    main()

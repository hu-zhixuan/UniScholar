"""
UniScholar 自动化单元测试集
验证工作流引擎状态机、四大核心智能体与引文防幻觉校验器逻辑。
"""

import os
import sys
import unittest

# 导入 UniScholar 根目录
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from agents.data_agent import DataAgent
from agents.intent_agent import IntentAgent
from agents.literature_agent import LiteratureAgent, calculate_relevance_score
from agents.reference_agent import ReferenceAgent, format_gbt7714, parse_reference_line
from agents.review_agent import PaperFeature, ReviewAgent
from core.workflow_engine import WorkflowEngine, WorkflowStatus, WorkflowStep
from utils.citation_validator import validate_citations


class TestUniScholar(unittest.TestCase):

    def setUp(self):
        self.engine = WorkflowEngine(checkpoints_dir="tests/temp_checkpoints", logs_dir="tests/temp_logs")

    def tearDown(self):
        import shutil
        if os.path.exists("tests/temp_checkpoints"):
            shutil.rmtree("tests/temp_checkpoints")
        if os.path.exists("tests/temp_logs"):
            shutil.rmtree("tests/temp_logs")

    def test_workflow_state_machine_and_resume(self):
        """测试工作流引擎的创建、暂停、检查点保存与断点恢复"""
        params = {"query": "AI科研智能体", "years": 3}
        state = self.engine.create_task(params, task_id="test_task_001")
        self.assertEqual(state.status, WorkflowStatus.IDLE)

        # 模拟执行第1步
        state.status = WorkflowStatus.RUNNING
        state.current_step = WorkflowStep.LITERATURE_RETRIEVAL
        state.completed_steps.append("literature_retrieval")
        self.engine.save_checkpoint(state)

        # 模拟暂停
        paused_state = self.engine.pause_task("test_task_001", reason="测试暂停")
        self.assertEqual(paused_state.status, WorkflowStatus.PAUSED)

        # 模拟续跑并修改数据
        resumed_state = self.engine.resume_task("test_task_001", modified_data={"user_approved": True})
        self.assertEqual(resumed_state.status, WorkflowStatus.RUNNING)
        self.assertTrue(resumed_state.data.get("user_approved"))
        self.assertIn("literature_retrieval", resumed_state.completed_steps)

    def test_literature_relevance_scoring(self):
        """测试文献语义打分逻辑"""
        title = "Autonomous Scientific Research Agent with Workflow"
        abstract = "This paper presents a general agent for laboratory automation."
        query_terms = ["Agent", "Workflow"]

        score = calculate_relevance_score(title, abstract, query_terms)
        self.assertGreater(score, 0.3)

        # 无关文本测试
        irrelevant_title = "Cooking recipes in Italian cuisine"
        irrelevant_abstract = "How to make authentic pasta and pizza."
        irrelevant_score = calculate_relevance_score(irrelevant_title, irrelevant_abstract, query_terms)
        self.assertEqual(irrelevant_score, 0.0)

    def test_data_agent_statistics_and_outliers(self):
        """测试实验数据统计计算与 IQR 异常值标记"""
        agent = DataAgent(output_dir="tests/temp_charts")
        csv_text = """Epoch,Loss,Accuracy
1,0.9,0.5
2,0.8,0.6
3,0.7,0.7
4,0.6,0.8
5,0.5,0.85
6,0.4,0.9
7,0.3,0.92
8,0.2,0.95
9,10.5,0.2
"""
        res = agent.run(csv_text, task_id="test_data")
        self.assertEqual(res["row_count"], 9)
        self.assertIn("Loss", res["stats"])
        # 验证 10.5 被标记为离群异常值
        self.assertIn("Loss", res["outliers"])
        self.assertGreater(res["outliers"]["Loss"]["outlier_count"], 0)
        self.assertIn("llm_interpretation", res)
        self.assertGreater(len(res["llm_interpretation"]), 10)

        import shutil
        if os.path.exists("tests/temp_charts"):
            shutil.rmtree("tests/temp_charts")

    def test_reference_agent_gbt7714_formatting(self):
        """测试 GB/T 7714-2015 格式化与要素解析"""
        agent = ReferenceAgent()
        raw_ref = "Boiko D A, MacKnight R, Kline B. Autonomous research. Nature, 2023, 624(7992): 570-578."
        res = agent.run(raw_ref, target_format="GB/T 7714")

        self.assertEqual(res["total_items"], 1)
        formatted_line = res["formatted_text"]
        self.assertIn("[1]", formatted_line)
        self.assertIn("[J]", formatted_line)
        self.assertIn("2023", formatted_line)
        self.assertIn("570-578", formatted_line)

    def test_citation_validator(self):
        """测试引文防幻觉交叉校验器"""
        valid_papers = [{"title": "Autonomous Scientific Research System"}]
        text_with_hallucination = "根据《Autonomous Scientific Research System》的结论，对比《Nonexistent Hallucinated Paper》的方法..."

        checked_text = validate_citations(text_with_hallucination, valid_papers)
        # 真实存在的文献被标记为已核验徽章
        self.assertIn("✓ 已核验证实引文", checked_text)
        # 虚假捏造的文献必须被标记警告徽章
        self.assertIn("⚠️ 疑似幻觉引文", checked_text)

    def test_intent_agent_academic_harness_formulation(self):
        """测试学术意图理解与选题解构 (Step 0)"""
        agent = IntentAgent()
        plan = agent.formulate("色情片对大脑影响", ["pron effect"])

        self.assertIn("pornography", plan.academic_topic_en.lower())
        self.assertIn("Neuroscience", plan.primary_discipline)
        self.assertTrue(any("pornography" in q.lower() for q in plan.search_queries))
        self.assertTrue(any(any(k in q.lower() for k in ["brain", "cortex", "neural", "striatum", "frontostriatal"]) for q in plan.search_queries))
        self.assertGreaterEqual(len(plan.core_mechanisms), 2)
        self.assertTrue(any("pornography" in k.lower() for k in plan.filter_keywords))

    def test_literature_agent_topic_awareness_and_fallback(self):
        """测试文献检索与离线兜底的主题感知能力（彻底消除 Cadmium 和猪精油脱靶文献）"""
        agent = LiteratureAgent()
        # 模拟脱机或网络受限状态
        os.environ["OFFLINE_DEMO"] = "1"
        try:
            res = agent.run("色情片对大脑影响", ["porn effect"], max_papers=5)
            self.assertGreater(res["selected_count"], 0)
            for p in res["papers"]:
                title_lower = p["title"].lower()
                # 必须为神经科学/色情/脑相关文献，绝不能为 Cadmium、GLP-1 或 猪饲料
                self.assertNotIn("cadmium", title_lower)
                self.assertNotIn("glp-1", title_lower)
                self.assertNotIn("pig", title_lower)
                self.assertTrue(
                    any(w in title_lower for w in ["pornography", "brain", "neural", "sexual", "addiction", "internet"])
                )
        finally:
            os.environ.pop("OFFLINE_DEMO", None)

    def test_review_agent_topic_centric_synthesis_no_template_leakage(self):
        """测试综述正文合成完全聚焦用户选题，绝不泄露无关的通用智能体模板"""
        agent = ReviewAgent()
        from offline_demo.demo_data import get_offline_features
        features = [PaperFeature(**f) for f in get_offline_features(topic="色情片对大脑影响")]

        outline = agent.generate_review_outline("色情片对大脑影响", features)
        draft = agent.synthesize_deep_academic_review("色情片对大脑影响", outline, features)

        # 验证彻底清除了脱靶模板词汇
        self.assertNotIn("通用智能体工作流", draft)
        self.assertNotIn("高校科研全流程中，师生普遍面临", draft)
        self.assertNotIn("中国联通元景", draft)
        self.assertNotIn("提出针对性优化模型与研究方案", draft)
        self.assertNotIn("定量实证分析对科研任务流水线进行系统解耦", draft)
        # 验证彻底消除了把学术论文扯成解决大模型幻觉的荒谬表述
        self.assertNotIn("大型语言模型在生成学术综述时固有的“虚构文献幻觉”是阻碍其在严肃科研场景应用的最大隐患", draft)

        # 验证具备高水平神经科学与脑科学论述
        self.assertIn("色情片对大脑影响", draft)
        self.assertIn("多巴胺", draft)
        self.assertIn("前额叶", draft)
        self.assertIn("纹状体", draft)
        # 验证真实文献被引用且能通过校验器
        self.assertIn(features[0].title, draft)

    def test_intent_agent_domain_separation_non_porn_topics(self):
        """测试领域解耦：确保一般脑科学（如阿尔茨海默）与通用科学（如量子计算）绝不被误劫持为色情片或通用智能体"""
        agent = IntentAgent()

        # 1. 神经科学非色情主题
        ad_plan = agent._heuristic_domain_formulation("阿尔茨海默症对大脑记忆功能的影响", ["Alzheimer"])
        self.assertNotIn("porn", ad_plan.academic_topic_en.lower())
        self.assertNotIn("pornography", [q.lower() for q in ad_plan.search_queries])
        self.assertIn("alzheimer", ad_plan.academic_topic_en.lower())

        # 2. 通用跨学科前沿科学主题
        qc_plan = agent._heuristic_domain_formulation("量子计算在材料科学中的应用", ["Quantum"])
        self.assertNotIn("porn", qc_plan.academic_topic_en.lower())
        self.assertNotIn("agent", qc_plan.academic_topic_en.lower())
        self.assertTrue(any("quantum" in q.lower() for q in qc_plan.search_queries))

    def test_offline_demo_domain_adaptive_data(self):
        """测试离线脱机包对不同领域选题的自适应支持"""
        from offline_demo.demo_data import get_offline_papers, is_neuroscience_topic, is_porn_topic

        self.assertTrue(is_porn_topic("色情片对大脑影响"))
        self.assertFalse(is_porn_topic("阿尔茨海默症的大脑机制"))
        self.assertTrue(is_neuroscience_topic("阿尔茨海默症的大脑机制"))

        ad_papers = get_offline_papers("阿尔茨海默症的大脑机制")
        for p in ad_papers:
            self.assertNotIn("porn", p["title"].lower())
            self.assertNotIn("cadmium", p["title"].lower())

    def test_no_english_sentence_leakage_and_pure_chinese_synthesis(self):
        """测试彻底消除中英夹杂与原始英文长句机械拼接 (Decision 4)"""
        from agents.review_agent import _extract_fallback_features_from_abstract, synthesize_deep_academic_review

        # 模拟包含原始英文摘要和 section 标记的文献
        raw_paper = {
            "title": "Enhanced conditioning and disrupted extinction processes in men struggling with compulsive sexual behaviors",
            "publication_year": 2025,
            "authors": ["Kowalewska E", "Gola M"],
            "abstract": "Background and aims Despite a previously reported connection between compulsive sexual behaviors (CSB) and heightened cue-reactivity, empirical evidence remains sparse. Methods Thirty-two heterosexual males struggling with CSB underwent active appetitive conditioning and extinction tasks in fMRI. Results During conditioning users showed ventral striatum response. Additionally, despite the absence of rewards, the persistence of arousal towards cues underscored the maladaptive extinction process. These insights advance CSB neurobiology.",
        }

        feat = _extract_fallback_features_from_abstract(raw_paper, topic="色情片对大脑影响")

        # 验证要素中绝无未经翻译的英文 section 标记
        self.assertNotIn("Background and aims", feat.background)
        self.assertNotIn("Methods Thirty-two", feat.methodology)
        for inno in feat.core_innovations:
            self.assertNotIn("Results During", inno)
        for conc in feat.main_conclusions:
            self.assertNotIn("Additionally, despite", conc)

        # 验证所有字段均为地道学术中文
        import re
        self.assertGreater(len(re.findall(r"[\u4e00-\u9fff]", feat.background)), 5)
        self.assertGreater(len(re.findall(r"[\u4e00-\u9fff]", feat.methodology)), 5)
        self.assertGreater(len(re.findall(r"[\u4e00-\u9fff]", feat.core_innovations[0])), 5)
        self.assertGreater(len(re.findall(r"[\u4e00-\u9fff]", feat.main_conclusions[0])), 5)

        # 合成综述正文并验证绝无中英夹杂的拼装病句
        outline = "# 《色情片对大脑影响》综述大纲"
        review_text = synthesize_deep_academic_review("色情片对大脑影响", outline, [feat])

        self.assertNotIn("该工作创新性地Background and aims", review_text)
        self.assertNotIn("并依托Methods Thirty-two", review_text)
        self.assertNotIn("其实证结果明确揭示：Additionally, despite", review_text)
        self.assertNotIn("maladaptive extinction process", review_text)

        # 验证表格内容为纯中文
        self.assertIn("核心创新突破与机制", review_text)
        self.assertIn("研究方法与技术方案", review_text)
        self.assertIn("实证对标结论", review_text)
        self.assertIn(raw_paper["title"], review_text)

    def test_hitl_candidate_funnel_workflow(self):
        """测试人在回路候选文献池遴选工作流 (Decision 1 & 3)"""
        # 1. 测试候选检索返回 ~20 篇文献，且每篇具备 chinese_summary
        lit_agent = LiteratureAgent()
        res = lit_agent.run("色情片对大脑影响", ["porn effect"], max_papers=20)
        self.assertGreaterEqual(len(res["papers"]), 15)
        for p in res["papers"]:
            self.assertTrue(bool(p.get("chinese_summary")))
            self.assertIn("relevance_score", p)

        # 2. 测试工作流引擎在文献检索后支持暂停 (人在回路检查点)
        task_params = {"query": "色情片对大脑影响", "years": 3}
        state = self.engine.create_task(task_params, task_id="test_hitl_task_001")
        state.data["candidate_pool"] = res["papers"]
        state.current_step = WorkflowStep.LITERATURE_RETRIEVAL
        state.completed_steps.append("literature_retrieval")
        self.engine.save_checkpoint(state)
        self.engine.pause_task("test_hitl_task_001", reason="人在回路：已检索候选池，等待学者挑选")

        paused_state = self.engine.load_checkpoint("test_hitl_task_001")
        self.assertEqual(paused_state.status, WorkflowStatus.PAUSED)
        self.assertEqual(len(paused_state.data["candidate_pool"]), len(res["papers"]))

        # 3. 模拟学者勾选 5 篇核心文献并断点恢复
        selected_5 = res["papers"][:5]
        resumed_state = self.engine.resume_task("test_hitl_task_001", modified_data={
            "selected_papers": selected_5,
            "literature_pool": selected_5,
        })
        self.assertEqual(resumed_state.status, WorkflowStatus.RUNNING)
        self.assertEqual(len(resumed_state.data["selected_papers"]), 5)

        # 4. 测试 WebUI 原生绑定与工具栏联动逻辑
        from web.app import (
            format_paper_choices,
            render_selection_badge,
            select_top6_action,
            select_all_action,
            clear_all_action,
            invert_selection_action,
            parse_selected_indices,
            resume_research_with_selected_papers,
        )
        choices = format_paper_choices(res["papers"])
        self.assertEqual(len(choices), len(res["papers"]))
        self.assertEqual(choices[0][1], "0")

        badge_0 = render_selection_badge(0, len(res["papers"]))
        self.assertIn("未选中文献", badge_0)

        badge_opt = render_selection_badge(6, len(res["papers"]))
        self.assertIn("最佳配比", badge_opt)

        top6_sel, _ = select_top6_action(res["papers"])
        self.assertEqual(top6_sel, ["0", "1", "2", "3", "4", "5"])

        all_sel, _ = select_all_action(res["papers"])
        self.assertEqual(len(all_sel), len(res["papers"]))

        clear_sel, _ = clear_all_action(res["papers"])
        self.assertEqual(clear_sel, [])

        inv_sel, _ = invert_selection_action(top6_sel, res["papers"])
        self.assertEqual(len(inv_sel), len(res["papers"]) - 6)

        parsed = parse_selected_indices(["[1] 《测试文献》", "3"], len(res["papers"]))
        self.assertEqual(parsed, [0, 3])

        # 5. 测试空选时拦截并返回 gr.skip
        import gradio as gr
        skip_res = resume_research_with_selected_papers("test_hitl_task_001", res["papers"], [])
        self.assertEqual(len(skip_res), 11)
        self.assertEqual(skip_res[0], gr.skip())


if __name__ == "__main__":
    unittest.main()

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
from agents.literature_agent import calculate_relevance_score
from agents.reference_agent import ReferenceAgent, format_gbt7714, parse_reference_line
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
        # 真实存在的文献不被标记警告
        self.assertIn("《Autonomous Scientific Research System》", checked_text)
        self.assertNotIn("《Autonomous Scientific Research System》`[⚠️ Unverified Reference]`", checked_text)
        # 虚假捏造的文献必须被标记警告
        self.assertIn("《Nonexistent Hallucinated Paper》`[⚠️ Unverified Reference]`", checked_text)


if __name__ == "__main__":
    unittest.main()

"""
UniScholar 通用智能体工作流状态机与断点续跑引擎 (Workflow Engine)
实现基于 DAG 状态图的任务编排、本地 Checkpoints 持久化、任务暂停、人工干预与断点续跑机制。
对标中国联通元景万悟通用智能体工作流标准规范。
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"          # 处于断点，等待人工确认或修改
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowStep(str, Enum):
    INIT = "init"
    LITERATURE_RETRIEVAL = "literature_retrieval"  # 1. 文献递归检索与初筛
    FEATURE_EXTRACTION = "feature_extraction"      # 2. 核心创新点与要素结构化提取
    OUTLINE_GENERATION = "outline_generation"      # 3. 综述大纲规划 (人工干预关键点)
    REVIEW_SYNTHESIS = "review_synthesis"          # 4. 综述初稿生成与防幻觉核验
    DATA_ANALYSIS = "data_analysis"                # 5. 实验数据统计与科研绘图
    REFERENCE_FORMAT = "reference_format"          # 6. 参考文献国标校对与排版
    COMPLETED = "completed"


STEP_ORDER = [
    WorkflowStep.LITERATURE_RETRIEVAL,
    WorkflowStep.FEATURE_EXTRACTION,
    WorkflowStep.OUTLINE_GENERATION,
    WorkflowStep.REVIEW_SYNTHESIS,
    WorkflowStep.DATA_ANALYSIS,
    WorkflowStep.REFERENCE_FORMAT,
]


@dataclass
class WorkflowState:
    task_id: str
    status: WorkflowStatus = WorkflowStatus.IDLE
    current_step: WorkflowStep = WorkflowStep.INIT
    completed_steps: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    pause_reason: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowState":
        return cls(
            task_id=d["task_id"],
            status=WorkflowStatus(d.get("status", WorkflowStatus.IDLE)),
            current_step=WorkflowStep(d.get("current_step", WorkflowStep.INIT)),
            completed_steps=d.get("completed_steps", []),
            params=d.get("params", {}),
            data=d.get("data", {}),
            pause_reason=d.get("pause_reason"),
            created_at=d.get("created_at", datetime.now().isoformat()),
            updated_at=d.get("updated_at", datetime.now().isoformat()),
            logs=d.get("logs", []),
        )


class WorkflowEngine:
    """
    通用科研智能体工作流执行引擎
    """

    def __init__(
        self,
        checkpoints_dir: str = "checkpoints",
        logs_dir: str = "logs",
        config_dir: str = "config",
    ):
        self.checkpoints_dir = checkpoints_dir
        self.logs_dir = logs_dir
        self.config_dir = config_dir

        os.makedirs(self.checkpoints_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)

        self.execution_log_path = os.path.join(self.logs_dir, "workflow_execution.log")

    def log(self, state: WorkflowState, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{state.task_id}] [{state.current_step.value}] {message}"
        state.logs.append(log_entry)
        state.updated_at = datetime.now().isoformat()
        logger.info(log_entry)

        # 写入持久化日志文件 (赛题要求提交项)
        try:
            with open(self.execution_log_path, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            logger.error(f"写入执行日志失败: {e}")

    def create_task(self, params: Dict[str, Any], task_id: Optional[str] = None) -> WorkflowState:
        if not task_id:
            task_id = f"task_{int(time.time())}_{os.urandom(3).hex()}"
        state = WorkflowState(
            task_id=task_id,
            status=WorkflowStatus.IDLE,
            current_step=WorkflowStep.INIT,
            params=params,
        )
        self.save_checkpoint(state)
        self.log(state, f"任务已创建，初始参数: {json.dumps(params, ensure_ascii=False)}")
        return state

    def get_checkpoint_path(self, task_id: str) -> str:
        return os.path.join(self.checkpoints_dir, f"{task_id}.json")

    def save_checkpoint(self, state: WorkflowState):
        state.updated_at = datetime.now().isoformat()
        filepath = self.get_checkpoint_path(state.task_id)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)

    def load_checkpoint(self, task_id: str) -> Optional[WorkflowState]:
        filepath = self.get_checkpoint_path(task_id)
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            d = json.load(f)
        return WorkflowState.from_dict(d)

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        results = []
        if not os.path.exists(self.checkpoints_dir):
            return results
        for fname in os.listdir(self.checkpoints_dir):
            if fname.endswith(".json"):
                path = os.path.join(self.checkpoints_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        results.append({
                            "task_id": data.get("task_id"),
                            "status": data.get("status"),
                            "current_step": data.get("current_step"),
                            "updated_at": data.get("updated_at"),
                        })
                except Exception:
                    pass
        results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return results

    def pause_task(self, task_id: str, reason: str = "人工介入修改") -> WorkflowState:
        state = self.load_checkpoint(task_id)
        if not state:
            raise ValueError(f"任务 {task_id} 不存在")
        state.status = WorkflowStatus.PAUSED
        state.pause_reason = reason
        self.log(state, f"🛑 工作流触发断点暂停，原因: {reason}")
        self.save_checkpoint(state)
        return state

    def resume_task(
        self,
        task_id: str,
        modified_data: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        state = self.load_checkpoint(task_id)
        if not state:
            raise ValueError(f"任务 {task_id} 不存在")

        if modified_data:
            self.log(state, f"接收到用户人工干预数据更新: {list(modified_data.keys())}")
            state.data.update(modified_data)

        state.status = WorkflowStatus.RUNNING
        state.pause_reason = None
        self.log(state, f"▶️ 工作流断点恢复运行，继续执行后续节点")
        self.save_checkpoint(state)
        return state

    def generate_wanwu_workflow_config(self) -> Dict[str, Any]:
        """
        导出符合中国联通元景万悟平台标准的通用智能体工作流 DAG 配置文件
        (赛题硬性交付物: 通用智能体流程配置文件)
        """
        config = {
            "$schema": "https://yuanjing.unicom.cn/schemas/workflow-v2.json",
            "metadata": {
                "name": "UniScholar-Universal-Research-Agent",
                "displayName": "联智学者-高校科研全流程智能体工作流",
                "version": "1.0.0",
                "author": "UniScholar Team",
                "description": "面向大创赛产业赛道（中国联通命题）的通用智能体自动化科研工作流系统",
                "platform": "unicom_yuanjing_wanwu",
                "category": "Academic_Research_Automation",
            },
            "nodes": [
                {
                    "id": "node_literature_retrieval",
                    "type": "agent",
                    "agent": "LiteratureRetrievalAgent",
                    "displayName": "文献自动化检索与递归筛选",
                    "tools": ["OpenAlexAPI", "ArxivAPI", "SemanticRelevanceScorer"],
                    "inputs": ["query", "keywords", "years", "max_papers"],
                    "outputs": ["literature_pool", "filtered_count"],
                    "next": "node_feature_extraction",
                    "supportsPause": True,
                },
                {
                    "id": "node_feature_extraction",
                    "type": "agent",
                    "agent": "ReviewExtractionAgent",
                    "displayName": "文献核心信息抽取与结构化提炼",
                    "tools": ["PydanticSchemaExtractor", "ParallelLLMExecutor"],
                    "inputs": ["literature_pool"],
                    "outputs": ["extracted_features", "summary_collection"],
                    "next": "node_outline_generation",
                    "supportsPause": False,
                },
                {
                    "id": "node_outline_generation",
                    "type": "hitl_checkpoint",
                    "agent": "ReviewSynthesisAgent",
                    "displayName": "综述大纲规划 (人在回路干预节点)",
                    "tools": ["OutlinePlannerLLM"],
                    "inputs": ["extracted_features"],
                    "outputs": ["review_outline"],
                    "next": "node_review_synthesis",
                    "supportsPause": True,
                    "defaultAction": "PAUSE_FOR_HUMAN_REVIEW",
                },
                {
                    "id": "node_review_synthesis",
                    "type": "agent",
                    "agent": "ReviewSynthesisAgent",
                    "displayName": "综述正文生成与防幻觉引文校验",
                    "tools": ["CitationValidator", "RAGContextEngine"],
                    "inputs": ["review_outline", "literature_pool"],
                    "outputs": ["final_review_markdown"],
                    "next": "node_data_analysis",
                    "supportsPause": False,
                },
                {
                    "id": "node_data_analysis",
                    "type": "tool_executor",
                    "agent": "ExperimentalDataAgent",
                    "displayName": "实验数据初步统计与科研可视化",
                    "tools": ["PandasStatsTool", "MatplotlibPlotTool", "IQRAnomalyDetector"],
                    "inputs": ["experiment_data_file"],
                    "outputs": ["statistics_summary", "charts_generated"],
                    "next": "node_reference_format",
                    "supportsPause": False,
                },
                {
                    "id": "node_reference_format",
                    "type": "tool_executor",
                    "agent": "ReferenceFormatterAgent",
                    "displayName": "参考文献 GB/T 7714 国标自动排版与纠错",
                    "tools": ["GBT7714Parser", "FormatSwitcher"],
                    "inputs": ["raw_references_text"],
                    "outputs": ["formatted_references", "audit_report"],
                    "next": None,
                    "supportsPause": False,
                },
            ],
            "stateManagement": {
                "persistence": "file_json_checkpoints",
                "checkpointDir": "checkpoints/",
                "supportResume": True,
                "humanInTheLoop": True,
            },
        }

        config_path = os.path.join(self.config_dir, "workflow_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        return config

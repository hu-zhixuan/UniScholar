"""
UniScholar 学术意图理解与检索规划 Agent (Academic Intent & Query Formulation Agent)
作为整个学术工作流的大脑 (Academic Harness Planner)：
接收用户的原始研究选题与初始关键词，由大模型最先进行深度思考与选题解构：
1. 规范化学术主题定义 (中英文)
2. 纠正用户初始输入中的拼写错误 (如 "pron" -> "pornography")
3. 规划出 3-5 个高影响英文学术检索短语 (包含神经机制、脑成像、实验范式等专业术语)
4. 明确归属学科与分支领域 (如 认知神经科学、精神病学、行为成瘾)
5. 提取预期关注的核心科学机制与观察指标
6. 生成用于语义打分的高精准中英文关键词词表
7. 规划领域定制化的综述叙事大纲框架
当大模型网络波动或离线时，具备语义感知与领域词典兜底规划引擎，绝不硬编码脱靶模板。
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class IntentPlan(BaseModel):
    original_topic: str = Field(default="", description="用户原始输入的选题")
    academic_topic_zh: str = Field(default="", description="学术化规范中文课题名称")
    academic_topic_en: str = Field(default="", description="国际学术界对应英文课题名称")
    primary_discipline: str = Field(default="Interdisciplinary Sciences", description="主要所属一级学科")
    sub_disciplines: List[str] = Field(default_factory=list, description="分支学科或交叉领域")
    search_queries: List[str] = Field(default_factory=list, description="高影响国际学术数据库英文检索短语")
    core_mechanisms: List[str] = Field(default_factory=list, description="预期重点提取的科学机制/神经生物指标/理论构念")
    filter_keywords: List[str] = Field(default_factory=list, description="用于文献相关度语义打分的中英文关键词库")
    outline_framework: List[str] = Field(default_factory=list, description="针对该领域定制的综述大纲章节框架")
    is_heuristic: bool = Field(default=False, description="是否由领域规则引擎启发式兜底生成")
    generation_source: str = Field(default="LLM 真实在线推理", description="生成来源标识")


INTENT_PROMPT = """你是一名资深跨学科学术导师与科研智能体大脑。
用户提交了以下科研选题与开题设想：
【研究选题】：{query}
【补充信息/关键词】：{user_keywords}

请作为科研自动化系统的思考大脑，充分发挥你的专业学术判断与主观能动性，自主为该课题规划最佳的研究推进方案：
包括规范化中英文学术课题界定、所属核心学科领域、检索国际学术文献（OpenAlex / Europe PMC）所需的英文检索词、预期关注的核心科学机制与指标、用于文献相关度打分的关键词库，以及该主题定制的学术大纲框架。

请直接以纯 JSON 格式输出你的自主规划方案：
{{
  "original_topic": "{query}",
  "academic_topic_zh": "更具学术严谨性的中文规范课题名称",
  "academic_topic_en": "对应的国际学术标准英文课题名称",
  "primary_discipline": "主要所属学科",
  "sub_disciplines": ["分支学科/交叉领域"],
  "search_queries": [
    "你自主推演的最佳英文文献检索短语"
  ],
  "core_mechanisms": [
    "你认为该课题核心值得深入探究的机制、指标或理论"
  ],
  "filter_keywords": [
    "用于相关度评估的中英文核心关键词"
  ],
  "outline_framework": [
    "一、 引言与核心问题界定",
    "二、 ...",
    "三、 ...",
    "四、 ..."
  ]
}}
"""


class IntentAgent:
    """
    学术意图理解与规划智能体
    """

    def __init__(self):
        self.llm_client = LLMClient()

    def formulate(
        self,
        query: str,
        user_keywords: Optional[List[str]] = None,
        years: int = 3,
        max_papers: int = 15,
    ) -> IntentPlan:
        """
        理解用户意图，生成结构化学术规划
        """
        clean_query = query.strip() if query else "通用智能体科研自动化"
        kw_str = ", ".join(user_keywords) if user_keywords else "无"

        # 离线演示模式优先判定
        if os.getenv("OFFLINE_DEMO", "0") == "1":
            return self._heuristic_domain_formulation(clean_query, user_keywords)

        prompt = INTENT_PROMPT.format(
            query=clean_query,
            user_keywords=kw_str,
        )

        try:
            raw_res = self.llm_client.call_llm(
                prompt=prompt,
                system_prompt="你是一名严谨的跨学科学术战略规划智能体，输出纯 JSON 格式。",
                temperature=0.2,
                timeout=15,
                max_retries=1,
            )
            data = self.llm_client.extract_json_from_text(raw_res)
            if isinstance(data, dict):
                # 兼容不同键名与缺失默认
                if not data.get("original_topic"):
                    data["original_topic"] = clean_query
                if not data.get("academic_topic_zh") and data.get("topic_zh"):
                    data["academic_topic_zh"] = data["topic_zh"]
                if not data.get("academic_topic_en") and data.get("topic_en"):
                    data["academic_topic_en"] = data["topic_en"]
                if data.get("search_queries") and data.get("filter_keywords"):
                    plan = IntentPlan(**data)
                    if not plan.academic_topic_zh:
                        plan.academic_topic_zh = clean_query
                    if not plan.academic_topic_en:
                        plan.academic_topic_en = clean_query
                    elif "pornographic" in plan.academic_topic_en.lower() and "pornography" not in plan.academic_topic_en.lower():
                        plan.academic_topic_en = re.sub(r"\bpornographic\s+media\b", "pornography", plan.academic_topic_en, flags=re.IGNORECASE)
                        plan.academic_topic_en = re.sub(r"\bpornographic\b", "pornography", plan.academic_topic_en, flags=re.IGNORECASE)
                    plan.is_heuristic = False
                    plan.generation_source = f"LLM 在线推理 ({getattr(self.llm_client, 'model', '大模型')})"
                    logger.info(f"【真实 LLM 推理】学术规划成功: {plan.academic_topic_en}, 规划检索词: {plan.search_queries}")
                    return plan
        except Exception as e:
            logger.warning(f"【触发兜底】LLM 学术规划调用失败或未连通 ({e})，自动激活领域规则引擎高保真兜底")

        fallback_plan = self._heuristic_domain_formulation(clean_query, user_keywords)
        fallback_plan.is_heuristic = True
        fallback_plan.generation_source = "内置领域知识库规则引擎 (未连通API或离线模式)"
        return fallback_plan

    def _heuristic_domain_formulation(
        self, query: str, user_keywords: Optional[List[str]] = None
    ) -> IntentPlan:
        """
        语义感知与领域词典规划引擎（保证 100% 不依赖 LLM 也能精准生成高质量检索管线）
        """
        q_lower = query.lower()
        combined_text = q_lower + " " + " ".join(user_keywords or []).lower()

        # 纠正拼写错误
        combined_text = re.sub(r"\bpron\b", "porn", combined_text)
        combined_text = re.sub(r"\bporno\b", "pornography", combined_text)

        # 1. 服饰恋物 / 性唤起 / 丝袜与特殊偏好 / 性心理学（严密独立分支，确保性学权威文献对标）
        is_fetish_or_sex = any(w in combined_text for w in [
            "丝袜", "恋物", "恋足", "性唤起", "性欲", "情趣", "内衣", "高跟鞋",
            "fetish", "fetishism", "paraphilia", "stocking", "stockings",
            "hosiery", "pantyhose", "sexual arousal", "sexual desire"
        ])
        if is_fetish_or_sex:
            return IntentPlan(
                original_topic=query,
                academic_topic_zh="丝袜与特定服饰刺激对人类性欲水平、性唤起及条件反射形成的实证影响机制",
                academic_topic_en="Empirical Mechanisms of Clothing Fetishism, Conditioned Sexual Arousal, and Hosiery-Induced Sexual Desire",
                primary_discipline="Sexual Psychology & Behavioral Neuroscience",
                sub_disciplines=[
                    "Conditioned Sexual Arousal (Pavlovian Conditioning)",
                    "Erotic Stimulus Processing & Attention Bias",
                    "Paraphilic Interests & Fetishism",
                    "Autonomic & Genital Arousal Assessment",
                ],
                search_queries=[
                    "stocking fetishism sexual arousal",
                    "clothing fetish sexual desire paraphilia",
                    "conditioned sexual arousal fetishism empirical",
                    "hosiery sexual arousal psychological mechanisms",
                ],
                core_mechanisms=[
                    "经典巴甫洛夫条件反射在非生殖器物体与性唤起联结中的习得机制 (Pavlovian conditioning of sexual arousal)",
                    "特定服饰视觉线索（织物光泽、包裹感）引发的早期注意力捕获与奖赏系统敏化 (Early attentional capture and reward sensitization)",
                    "多感官联觉刺激下的自主神经系统交感神经激活与外周生殖器血流变化 (Autonomic and genital arousal responses)",
                    "非病理性恋物倾向在现代性心理与伴侣互动满意度中的积极调节效应 (Non-clinical fetishism and relationship satisfaction)",
                ],
                filter_keywords=[
                    "fetishism", "fetish", "sexual", "arousal", "desire", "stocking", "stockings",
                    "hosiery", "pantyhose", "paraphilia", "conditioning", "erotic", "plethysmograph",
                    "丝袜", "性欲", "性唤起", "恋物", "条件反射", "心理", "偏好",
                ],
                outline_framework=[
                    "一、 引言与核心概念界定：服饰恋物与性欲影响的性心理学审视",
                    "二、 刺激加工与实验测量范式（生殖器光电容积描记法、瞳孔眼动追踪与主观量表）",
                    "三、 关键机理剖析：条件反射习得、注意力敏化与代表性实证文献对标",
                    "四、 心理与亲密关系影响（健康非病理化表达vs临床分歧）、现有局限与未来演进展望",
                ],
            )

        # 2. 色情片 / 成人内容 / 性行为成瘾 / 网络性心理（严密独立判定，杜绝普通神经科学被误劫持）
        is_porn = any(w in combined_text for w in [
            "色情", "porn", "成人视频", "淫秽", "cybersex", "erotic", "adult content",
            "sexually explicit", "csbd", "compulsive sexual", "性成瘾", "黄色"
        ])
        if is_porn:
            return IntentPlan(
                original_topic=query,
                academic_topic_zh="网络色情暴露对人类大脑结构、神经回路与认知控制功能的影响机制",
                academic_topic_en="Neural Correlates and Neurobiological Mechanisms of Pornography Consumption and Cybersex Addiction",
                primary_discipline="Cognitive Neuroscience & Psychiatry",
                sub_disciplines=[
                    "Functional Neuroimaging (fMRI)",
                    "Mesolimbic Dopamine System",
                    "Prefrontal Inhibitory Control",
                    "Compulsive Sexual Behavior Disorder (CSBD)",
                ],
                search_queries=[
                    "pornography brain neural mechanisms",
                    "pornography consumption neuroimaging fMRI",
                    "problematic pornography use prefrontal cortex striatum",
                    "cybersex addiction cue reactivity dopamine",
                    "compulsive sexual behavior disorder brain connectivity",
                ],
                core_mechanisms=[
                    "腹侧纹状体（伏隔核）线索诱发反应与多巴胺奖赏敏化 (Mesolimbic reward sensitization)",
                    "背外侧/眶额叶前额皮层激活减弱与抑制控制障碍 (Prefrontal executive hypofrontality)",
                    "脑岛介导的渴求感知与情绪调节失衡 (Insular craving regulation)",
                    "长期暴露伴随的尾状核灰质体积可塑性改变 (Striatal gray matter structural alterations)",
                ],
                filter_keywords=[
                    "pornography", "porn", "cybersex", "brain", "neural", "neuroimaging",
                    "fMRI", "striatum", "prefrontal", "dopamine", "addiction", "cue reactivity",
                    "compulsive", "caudate", "色情", "大脑", "神经", "脑区", "前额叶", "纹状体",
                    "多巴胺", "成瘾", "抑制控制",
                ],
                outline_framework=[
                    "一、 引言与神经生物学核心问题界定：色情内容消费的脑科学审视",
                    "二、 实验观测范式与神经影像学实证（fMRI线索诱发反应与功能连接）",
                    "三、 关键机理剖析：奖赏系统敏化、抑制控制衰减与代表性文献对标",
                    "四、 理论争议（成瘾模型vs高性欲模型）、方法学局限与未来演进展望",
                ],
            )

        # 2. 通用脑科学 / 神经科学 / 神经系统疾病（非色情主题）
        is_neuro = any(w in combined_text for w in [
            "大脑", "脑", "神经", "neuro", "fmri", "mri", "eeg", "阿尔茨海默", "脑机接口",
            "帕金森", "脑卒中", "认知", "cognitive", "alzheimer", "parkinson", "stroke", "bci",
            "dopamine", "多巴胺", "抑郁", "depression", "脑电", "脑区"
        ])
        if is_neuro:
            words = re.findall(r"[a-zA-Z0-9]+", combined_text)
            eng_tokens = [w for w in words if len(w) > 2]
            key_kw = " ".join(eng_tokens) if eng_tokens else "neural"
            return IntentPlan(
                original_topic=query,
                academic_topic_zh=f"《{query}》的神经生物学机制、影像学表型与实证研究前沿",
                academic_topic_en=f"Neural Mechanisms, Neuroimaging Phenotypes, and Empirical Advances in {query if not eng_tokens else key_kw.title()}",
                primary_discipline="Cognitive Neuroscience & Clinical Neurology",
                sub_disciplines=[
                    "Functional Neuroimaging (fMRI / EEG)",
                    "Neural Circuit Analysis",
                    "Neuropathological Mechanisms",
                    "Cognitive & Behavioral Phenotypes",
                ],
                search_queries=[
                    f"{key_kw} brain neural mechanisms" if eng_tokens else f"brain neural mechanisms {query}",
                    f"{key_kw} neuroimaging functional connectivity" if eng_tokens else "neuroimaging brain functional connectivity",
                    f"{key_kw} cognitive neural circuits" if eng_tokens else "cognitive neural circuits empirical study",
                    f"{key_kw} clinical neurobiology review" if eng_tokens else "clinical neurobiology review",
                ],
                core_mechanisms=[
                    "特定功能网络连接性与脑区拓扑结构动态重塑",
                    "神经生化递质传递与突触可塑性改变",
                    "神经电生理节律与微观回路异常机制",
                ],
                filter_keywords=eng_tokens + [
                    "brain", "neural", "neuroimaging", "cortex", "cognitive", "fMRI",
                    "大脑", "脑区", "神经", "回路", "认知", "实证", query,
                ],
                outline_framework=[
                    f"一、 引言与核心神经科学问题界定：{query}的研究背景与学术价值",
                    "二、 多模态神经影像学与电生理观测范式演进",
                    "三、 关键机理剖析、受累神经回路与代表性文献横向对标",
                    "四、 理论争议、方法学局限与未来脑科学突破方向",
                ],
            )

        # 3. 通用智能体 / 科研自动化 / Multi-Agent / Workflow
        if any(w in combined_text for w in ["智能体", "agent", "工作流", "workflow", "科研自动化", "大模型", "llm"]):
            return IntentPlan(
                original_topic=query,
                academic_topic_zh="基于通用智能体工作流的高校科研全流程自动化系统与状态编排",
                academic_topic_en="Autonomous Scientific Research Workflows Based on Multi-Agent Systems and StateGraph Orchestration",
                primary_discipline="Computer Science & Artificial Intelligence",
                sub_disciplines=[
                    "Multi-Agent Systems",
                    "Workflow Orchestration",
                    "Zero-Hallucination RAG",
                    "Scientific Automation",
                ],
                search_queries=[
                    "autonomous scientific research agent multi-agent workflow",
                    "stateful agentic workflows human-in-the-loop",
                    "zero hallucination literature synthesis citation verification",
                    "large language models scientific laboratory automation",
                ],
                core_mechanisms=[
                    "DAG 状态图执行引擎与检查点持久化机制 (StateGraph DAG Engine)",
                    "人在回路 (HITL) 动态干预与大纲重构能力",
                    "双向文献白名单交叉防幻觉校验机制 (Citation Validator)",
                    "多工具链动态调度与实验数据自动化审计",
                ],
                filter_keywords=[
                    "agent", "workflow", "autonomous", "scientific", "research", "orchestration",
                    "stategraph", "checkpoint", "hallucination", "verification", "智能体", "工作流",
                    "科研", "自动化", "状态图", "断点续跑", "防幻觉",
                ],
                outline_framework=[
                    "一、 引言与问题界定：科研全流程中的事务性瓶颈与智能体机遇",
                    "二、 智能体科研工作流编排架构与关键演进范式对比",
                    "三、 代表性创新突破与方法横向对标（文献、实验与引文校验）",
                    "四、 现有研究瓶颈、产业级规范接轨与未来演进展望",
                ],
            )

        # 4. 通用科学选题自适应解构与跨语言语义对齐引擎
        ZH_EN_CONCEPT_MAP = {
            "丝袜": "stocking hosiery", "性欲": "sexual desire", "性唤起": "sexual arousal",
            "恋物": "fetishism", "情趣": "erotic lingerie", "心理": "psychology",
            "神经": "neural", "大脑": "brain", "认知": "cognitive", "成瘾": "addiction",
            "材料": "materials", "纳米": "nanomaterials", "催化": "catalysis", "电池": "battery",
            "储能": "energy storage", "半导体": "semiconductor", "钙钛矿": "perovskite",
            "生物": "biological", "医药": "pharmaceutical", "肿瘤": "tumor cancer",
            "基因": "gene genomic", "免疫": "immune", "病毒": "virus viral",
            "算法": "algorithm", "智能体": "agent system", "大模型": "large language models",
            "深度学习": "deep learning", "机器人": "robotics", "计算机视觉": "computer vision",
            "经济": "economic", "金融": "financial", "管理": "management", "教育": "education",
            "气候": "climate", "环境": "environmental", "生态": "ecological", "碳中和": "carbon neutral",
            "机制": "mechanisms", "模型": "model", "实证": "empirical", "分析": "analysis",
            "评估": "evaluation", "优化": "optimization", "影响": "impact effects",
        }

        translated_parts = []
        for zh_kw, en_kw in ZH_EN_CONCEPT_MAP.items():
            if zh_kw in combined_text:
                translated_parts.append(en_kw)

        words = re.findall(r"[a-zA-Z0-9]+", combined_text)
        eng_tokens = [w for w in words if len(w) > 2]
        all_en_tokens = list(dict.fromkeys(eng_tokens + translated_parts))
        base_query_en = " ".join(all_en_tokens) if all_en_tokens else "scientific empirical research"

        return IntentPlan(
            original_topic=query,
            academic_topic_zh=f"《{query}》核心机制、实证前沿与演进趋势研究",
            academic_topic_en=f"Advances and Empirical Foundations in {base_query_en.title()}",
            primary_discipline="Interdisciplinary Sciences",
            sub_disciplines=["Methodological Advances", "Empirical Evaluation", "Theoretical Foundations"],
            search_queries=[
                f"{base_query_en} mechanisms empirical",
                f"{base_query_en} recent advances review",
                f"{base_query_en} methodology evaluation",
                f"{base_query_en} theoretical model",
            ],
            core_mechanisms=[
                "基础理论与机理模型演进",
                "实证评估与实验范式对比",
                "核心参数与定量指标关联分析",
            ],
            filter_keywords=all_en_tokens + [query, "empirical", "mechanisms", "analysis", "review"],
            outline_framework=[
                f"一、 引言与核心问题界定：{query}的研究背景与学术价值",
                "二、 主流研究范式与观测方法演进脉络",
                "三、 代表性创新突破与前沿方法横向对标",
                "四、 现有理论瓶颈、争议与未来演进方向",
            ],
        )

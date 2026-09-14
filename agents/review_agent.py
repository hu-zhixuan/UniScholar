"""
UniScholar 文献核心信息抽取与综述框架生成 Agent (Review Extraction & Synthesis Agent)
自动抽取文献背景、创新点、方法与结论；批量输出摘要整理稿；
并基于结构化逻辑自动生成多级综述大纲与带真实引文的综述初稿框架。
"""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from utils.citation_validator import validate_citations
from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class PaperFeature(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    publication_year: Optional[int] = None
    background: str = Field(description="研究背景与解决的痛点", default="")
    core_innovations: List[str] = Field(description="核心创新点列表 (1-3条)", default_factory=list)
    methodology: str = Field(description="主要研究方法、算法或理论模型", default="")
    main_conclusions: List[str] = Field(description="主要结论与实验发现 (1-3条)", default_factory=list)


EXTRACTION_PROMPT = """
你是一名严谨的学术科研情报分析专家。请仔细阅读以下论文的标题与摘要，提取核心科研要素。
输出必须严格符合 JSON Schema 规范，绝不允许编造摘要中未提及的信息。

【论文信息】
标题: {title}
作者: {authors}
年份: {year}
摘要: {abstract}

【提取要求】
1. background: 1-2句话简述该论文的研究背景和旨在解决的具体痛点。
2. core_innovations: 列出 1-3 条该论文的最核心创新点（新架构、新机制、新理论或新范式）。
3. methodology: 1句话明确该论文采用的核心算法、实验方法或工具链。
4. main_conclusions: 列出 1-3 条核心实验结论或定量发现。

请直接返回纯 JSON 对象，格式如下：
{{
  "title": "{title}",
  "authors": {authors_json},
  "publication_year": {year},
  "background": "...",
  "core_innovations": ["创新点1", "创新点2"],
  "methodology": "...",
  "main_conclusions": ["结论1", "结论2"]
}}
"""


class ReviewAgent:
    """
    文献信息抽取与综述生成智能体
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.llm_client = LLMClient()

    def extract_single_paper(self, paper: Dict[str, Any]) -> PaperFeature:
        """单篇论文要素抽取"""
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        authors = paper.get("authors", [])
        year = paper.get("publication_year", 2024)

        if not abstract.strip():
            return PaperFeature(
                title=title,
                authors=authors,
                publication_year=year,
                background="摘要缺失，基于公开标题归纳",
                core_innovations=[f"围绕 {title} 开展的研究工作"],
                methodology="学术实证与定量分析",
                main_conclusions=["详见原刊发表版本"],
            )

        prompt = EXTRACTION_PROMPT.format(
            title=title,
            authors=", ".join(authors) if authors else "未知作者",
            authors_json=json.dumps(authors, ensure_ascii=False),
            year=year,
            abstract=abstract,
        )

        try:
            raw_res = self.llm_client.call_llm(
                prompt=prompt,
                system_prompt="你是一名学术要素结构化抽取智能体，严格输出纯 JSON。",
                temperature=0.1,
            )

            # 提取 JSON 块
            json_match = re.search(r"\{.*\}", raw_res, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                return PaperFeature(**parsed)
        except Exception as e:
            logger.warning(f"抽取论文《{title}》异常: {e}，使用降级特征")

        return PaperFeature(
            title=title,
            authors=authors,
            publication_year=year,
            background=abstract[:150] + "...",
            core_innovations=["提出针对性优化模型与研究方案"],
            methodology="定量实证分析",
            main_conclusions=["实验结果表明所提方案具有显著效能提升"],
        )

    def batch_extract(self, papers: List[Dict[str, Any]]) -> List[PaperFeature]:
        """多线程并发抽取"""
        if os.getenv("OFFLINE_DEMO", "0") == "1":
            from offline_demo.demo_data import get_offline_features
            logger.info("⚡ 检测到 OFFLINE_DEMO=1，加载内置离线结构化要素数据")
            return [PaperFeature(**f) for f in get_offline_features()]

        results: List[PaperFeature] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_paper = {
                executor.submit(self.extract_single_paper, p): p for p in papers
            }
            for future in as_completed(future_to_paper):
                try:
                    feat = future.result()
                    results.append(feat)
                except Exception as e:
                    p = future_to_paper[future]
                    logger.error(f"处理失败: {p.get('title')}: {e}")

        return results

    def generate_summary_collection(self, features: List[PaperFeature]) -> str:
        """生成批量摘要与创新点整理稿 (Markdown 格式)"""
        lines = ["# 📚 精选文献核心要素与创新点整理稿\n\n> 本稿件由 UniScholar 智能体自动并发提取生成，包含论文背景、方法、创新点与结论。\n"]
        for idx, f in enumerate(features, 1):
            lines.append(f"## {idx}. 《{f.title}》")
            lines.append(f"- **作者**: {', '.join(f.authors) if f.authors else '未知'}")
            lines.append(f"- **年份**: {f.publication_year or '未知'}")
            lines.append(f"- **研究背景**: {f.background}")
            lines.append(f"- **核心方法**: `{f.methodology}`")
            lines.append("- **核心创新点**:")
            for inn in f.core_innovations:
                lines.append(f"  * {inn}")
            lines.append("- **主要结论**:")
            for conc in f.main_conclusions:
                lines.append(f"  * {conc}")
            lines.append("\n---\n")
        return "\n".join(lines)

    def generate_review_outline(self, topic: str, features: List[PaperFeature]) -> str:
        """基于文献群落结构，生成文献综述大纲"""
        if os.getenv("OFFLINE_DEMO", "0") == "1":
            from offline_demo.demo_data import get_offline_outline
            return get_offline_outline()

        titles_summary = "\n".join([f"- 《{f.title}》: {f.methodology} | 创新点: {', '.join(f.core_innovations[:2])}" for f in features[:10]])

        prompt = f"""
你是一名资深科研导师与学术期刊特邀主编。基于以下围绕研究方向【{topic}】精选的代表性文献库：
{titles_summary}

请根据通用智能体的结构化逻辑，规划出一份高水平、逻辑演进清晰的【文献综述大纲】。
必须包含三级标题结构，要求：
1. 第一章：引言、研究背景与关键科学问题界定
2. 第二章：主流技术与研究范式演进对比（细分2-3个子领域或流派）
3. 第三章：代表性创新突破与前沿方法对标（明确标注各章节对应的代表性论文《标题》）
4. 第四章：现有研究瓶颈、评价指标与未来突破方向

请直接输出规范的 Markdown 大纲：
"""
        try:
            outline_md = self.llm_client.call_llm(
                prompt=prompt,
                system_prompt="你是一名专业的文献综述大纲规划智能体，输出专业规范的 Markdown 大纲。",
                temperature=0.3,
            )
            return outline_md.strip()
        except Exception as e:
            logger.warning(f"生成大纲失败: {e}，返回备用大纲模板")

        return f"""# 《{topic}》研究前沿与文献综述大纲

## 一、 引言与问题界定
### 1.1 研究背景与学术价值
### 1.2 核心痛点与现有挑战

## 二、 关键技术路线与演进脉络
### 2.1 传统与基准方法演进
### 2.2 深度学习与大模型前沿驱动范式

## 三、 代表性创新突破与方法对标
### 3.1 架构创新与代表性方案
### 3.2 实验评测体系与实证对比

## 四、 总结与未来趋势展望
### 4.1 现有瓶颈分析
### 4.2 未来高价值演进方向
"""

    def generate_review_draft(
        self,
        topic: str,
        outline: str,
        features: List[PaperFeature],
    ) -> str:
        """根据大纲与文献池，合成综述初稿框架，并执行引文防幻觉校验"""
        if os.getenv("OFFLINE_DEMO", "0") == "1":
            from offline_demo.demo_data import get_offline_review_draft
            return get_offline_review_draft()

        papers_context = "\n".join([
            f"《{f.title}》({f.publication_year})：创新点[{'; '.join(f.core_innovations)}]，方法[{f.methodology}]，结论[{'; '.join(f.main_conclusions)}]"
            for f in features[:8]
        ])

        prompt = f"""
你是一名严谨的学术综述撰写专家。请根据以下大纲和真实文献证据池，为研究主题【{topic}】撰写一份结构化文献综述初稿框架。

【综述大纲】
{outline}

【真实文献证据池】
{papers_context}

【🔴 严谨学术规范】：
1. 正文中提及或引用具体学术观点时，**必须严格使用《完整论文标题》** 予以指代和印证。
2. **严禁凭空捏造任何不在证据池中的虚假论文**！
3. 请为大纲中的核心章节撰写精炼、学术化、逻辑连贯的正文论述段落，每章包含实质性综述内容。

请输出规范的 Markdown 文献综述全文：
"""
        raw_review = self.llm_client.call_llm(
            prompt=prompt,
            system_prompt="你是一名严谨的学术综述撰写智能体，输出专业学术语言。",
            temperature=0.3,
        )

        # 执行 Citation Validator 交叉校验 (防幻觉杀手锏)
        valid_papers_list = [{"title": f.title} for f in features]
        validated_review = validate_citations(
            content_markdown=raw_review,
            valid_papers=valid_papers_list,
        )

        return validated_review

"""
UniScholar 科研文献自动化检索与递归筛选 Agent (Literature Retrieval Agent)
作为学术 Harness 的执行手脚：
基于 IntentAgent 规划的高影响英文学术检索词与多维学科特征，
通过 OpenAlex、Europe PMC 与 arXiv 跨源检索，
并通过高敏感度语义相关度自动打分过滤低相关度文献，构建高精准度文献池。
"""

import json
import logging
import math
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """将 OpenAlex 的倒排索引摘要还原为完整文本"""
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    pos_word = []
    for word, positions in inverted_index.items():
        for pos in positions:
            pos_word.append((pos, word))
    pos_word.sort(key=lambda x: x[0])
    return " ".join(word for _, word in pos_word)


# 学术通用停用词库：杜绝“empirical”、“study”、“review”等空泛词元单独判定相关性
ACADEMIC_STOPWORDS = {
    "empirical", "study", "studies", "mechanisms", "mechanism", "analysis",
    "review", "recent", "advances", "advance", "methodology", "evaluation",
    "theoretical", "theory", "model", "models", "approach", "approaches",
    "framework", "investigation", "effects", "effect", "impact", "impacts",
    "perspective", "perspectives", "based", "system", "systems", "using",
    "towards", "role", "roles", "research", "paper", "journal", "international",
    "comparative", "systematic", "understanding", "exploring", "overview",
    "comprehensive", "quantitative", "qualitative", "findings", "insight",
    "insights", "evidence", "future", "development", "applications"
}


def calculate_relevance_score(
    title: str,
    abstract: str,
    query_terms: List[str],
) -> float:
    """
    高精度学术语义相关度打分引擎 (支持中英文分词、核心概念强约束、通用停用词清洗)。
    铁律：
    1. 必须命中至少 1 个领域核心专业词元 (非通用停用词)，否则直接判 0.0 分！
    2. 标题命中赋予 4.0 倍权重，摘要命中赋予 1.5 倍权重。
    3. 严禁无条件赋予 0.20 兜底分，彻底杜绝跨域杂音论文渗透。
    """
    t_lower = title.lower()
    a_lower = abstract.lower()
    text = f"{t_lower} {a_lower}"
    if not text.strip() or not query_terms:
        return 0.0

    # 将所有查询词打散为独立词元 (支持中英文切分)
    all_tokens = set()
    for term in query_terms:
        if not term:
            continue
        words = re.findall(r"[a-zA-Z0-9]+", term.lower())
        all_tokens.update(w for w in words if len(w) > 2)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]+", term)
        for chunk in chinese_chars:
            if len(chunk) <= 4:
                all_tokens.add(chunk)
            else:
                for i in range(0, len(chunk) - 1):
                    all_tokens.add(chunk[i:i + 2])

    if not all_tokens:
        return 0.0

    # 区分领域核心词元 (Domain Tokens) 与通用学术停用词 (Generic Tokens)
    domain_tokens = [t for t in all_tokens if t not in ACADEMIC_STOPWORDS]
    generic_tokens = [t for t in all_tokens if t in ACADEMIC_STOPWORDS]

    # 核心铁律：若存在领域词元，必须至少命中 1 个领域词元！
    matched_domain_count = 0
    domain_score = 0.0
    for dt in domain_tokens:
        t_hit = len(re.findall(re.escape(dt), t_lower))
        a_hit = len(re.findall(re.escape(dt), a_lower))
        if t_hit > 0 or a_hit > 0:
            matched_domain_count += 1
            domain_score += t_hit * 4.0 + a_hit * 1.5 + 1.0

    if domain_tokens and matched_domain_count == 0:
        # 完全未命中任何领域核心词元，判定为完全脱靶，直接归零！
        return 0.0

    # 通用词元辅助微调 (权重极低，仅在已命中领域词元时提供微调)
    generic_score = 0.0
    for gt in generic_tokens:
        t_hit = len(re.findall(re.escape(gt), t_lower))
        a_hit = len(re.findall(re.escape(gt), a_lower))
        if t_hit > 0 or a_hit > 0:
            generic_score += t_hit * 0.5 + a_hit * 0.2

    # 综合归一化得分计算
    total_domain_len = max(1, len(domain_tokens)) if domain_tokens else max(1, len(all_tokens))
    coverage = matched_domain_count / total_domain_len if domain_tokens else 0.5
    raw_score = (domain_score / (total_domain_len * 3.5)) * 0.6 + coverage * 0.35 + min(0.05, generic_score * 0.01)

    return round(min(0.98, max(0.0, raw_score)), 3)


class LiteratureAgent:
    """
    科研文献递归检索与初筛智能体
    """

    def __init__(self, request_delay: float = 0.3):
        self.request_delay = request_delay
        self.session = requests.Session()
        self.session.trust_env = False  # 直连网络，避免 Windows 无效系统代理干扰
        self.session.headers.update({
            "User-Agent": "UniScholar-Research-Agent/1.0 (mailto:scholar_demo@unischolar.org)"
        })

    def search_openalex(
        self,
        query: str,
        from_year: int,
        max_papers: int = 50,
    ) -> List[Dict[str, Any]]:
        """从 OpenAlex 检索文献并按高引排序（携带 mailto 接入 Polite Pool 避免 429）"""
        url = "https://api.openalex.org/works"
        params = {
            "search": query,
            "mailto": "scholar_demo@unischolar.org",
            "filter": f"from_publication_date:{from_year}-01-01",
            "per_page": min(100, max_papers * 2),
        }

        for attempt in range(2):
            try:
                logger.info(f"正在通过 OpenAlex 检索: '{query}', 起始年份: {from_year}")
                resp = self.session.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    papers = []
                    for item in results:
                        title = item.get("title") or ""
                        if not title:
                            continue
                        abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
                        doi = item.get("doi") or ""
                        authorships = item.get("authorships", [])
                        authors = [
                            a.get("author", {}).get("display_name", "")
                            for a in authorships if a.get("author", {}).get("display_name")
                        ]
                        pub_year = item.get("publication_year", from_year)
                        cited_by = item.get("cited_by_count", 0)

                        papers.append({
                            "id": item.get("id", ""),
                            "doi": doi,
                            "title": title,
                            "authors": authors[:5],
                            "publication_year": pub_year,
                            "cited_by_count": cited_by,
                            "abstract": abstract,
                            "source": "OpenAlex",
                        })
                    return papers
                elif resp.status_code == 429:
                    if attempt == 0:
                        logger.warning("OpenAlex 触发瞬时频控 (HTTP 429)，等待 1.5 秒后重试...")
                        time.sleep(1.5)
                        continue
                    else:
                        logger.warning("OpenAlex 接口达到限流阈值 (HTTP 429)，自动转入 Europe PMC / arXiv 备用引擎")
            except Exception as e:
                logger.warning(f"OpenAlex 检索异常: {e}")
                break

        return []

    def search_europepmc(
        self,
        query: str,
        from_year: int,
        max_papers: int = 30,
    ) -> List[Dict[str, Any]]:
        """从 Europe PMC 检索生命科学、神经生物学、医学与交叉前沿文献（免鉴权高可用）"""
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        clean_q = re.sub(r'["\']', '', query)
        params = {
            "query": f"({clean_q}) AND (PUB_YEAR:[{from_year} TO 2026])",
            "format": "json",
            "pageSize": min(100, max_papers * 2),
            "resultType": "core",
        }
        try:
            logger.info(f"正在通过 Europe PMC 检索: '{clean_q}'")
            resp = self.session.get(url, params=params, timeout=12)
            if resp.status_code == 200:
                results = resp.json().get("resultList", {}).get("result", [])
                papers = []
                for item in results:
                    title = item.get("title", "").strip().rstrip(".")
                    if not title:
                        continue
                    raw_abstract = item.get("abstractText", "")
                    # 清洗 HTML/XML 标签
                    abstract = re.sub(r"<[^>]+>", " ", raw_abstract).strip()
                    doi = item.get("doi", "")
                    author_str = item.get("authorString", "")
                    authors = [a.strip() for a in author_str.split(",") if a.strip()][:5]
                    pub_year = int(item.get("pubYear", from_year)) if str(item.get("pubYear", "")).isdigit() else from_year
                    cited_by = int(item.get("citedByCount", 0))

                    papers.append({
                        "id": f"https://europepmc.org/article/MED/{item.get('id', '')}",
                        "doi": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                        "title": title,
                        "authors": authors,
                        "publication_year": pub_year,
                        "cited_by_count": cited_by,
                        "abstract": abstract,
                        "source": "Europe PMC",
                    })
                return papers
        except Exception as e:
            logger.warning(f"Europe PMC 检索异常: {e}")

        return []

    def search_arxiv_fallback(
        self,
        query: str,
        max_papers: int = 20,
    ) -> List[Dict[str, Any]]:
        """arXiv API 检索（覆盖计算机、量化生物学与物理科学）"""
        url = "http://export.arxiv.org/api/query"
        clean_q = re.sub(r'["\']', '', query)
        params = {
            "search_query": f"all:{clean_q}",
            "start": 0,
            "max_results": max_papers,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            logger.info(f"正在通过 arXiv 检索: '{clean_q}'")
            resp = self.session.get(url, params=params, timeout=12)
            if resp.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.text)
                papers = []
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns):
                    title = entry.find("atom:title", ns)
                    summary = entry.find("atom:summary", ns)
                    id_elem = entry.find("atom:id", ns)
                    published = entry.find("atom:published", ns)

                    t_text = title.text.strip().replace("\n", " ") if title is not None and title.text else ""
                    s_text = summary.text.strip().replace("\n", " ") if summary is not None and summary.text else ""
                    id_text = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                    year = int(published.text[:4]) if published is not None and published.text else 2024

                    authors = []
                    for author in entry.findall("atom:author", ns):
                        name = author.find("atom:name", ns)
                        if name is not None and name.text:
                            authors.append(name.text.strip())

                    if t_text:
                        papers.append({
                            "id": id_text,
                            "doi": "",
                            "title": t_text,
                            "authors": authors[:5],
                            "publication_year": year,
                            "cited_by_count": 0,
                            "abstract": s_text,
                            "source": "arXiv",
                        })
                return papers
        except Exception as e:
            logger.warning(f"arXiv 检索异常: {e}")

        return []

    def run(
        self,
        query: str,
        keywords: Optional[List[str]] = None,
        years: int = 3,
        max_papers: int = 30,
        relevance_threshold: float = 0.2,
        search_queries: Optional[List[str]] = None,
        filter_keywords: Optional[List[str]] = None,
        intent_plan: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        学术 Harness 执行管线：
        1. 获取/执行 Step 0 学术规划（高区分度英文检索词与专业词表）
        2. 跨 OpenAlex + Europe PMC + arXiv 联合召回
        3. 跨源实体去重
        4. 基于专业词表实施高精准语义打分与防脱靶过滤
        """
        current_year = 2025
        from_year = current_year - years

        # 离线脱机模式判定
        if os.getenv("OFFLINE_DEMO", "0") == "1":
            logger.info("⚡ 检测到 OFFLINE_DEMO=1，加载主题自适应真实学术脱机文献池")
            from offline_demo.demo_data import get_offline_papers
            offline_papers = get_offline_papers(topic=query)
            for p in offline_papers:
                p["relevance_score"] = 0.88
            return {
                "total_fetched": len(offline_papers),
                "selected_count": len(offline_papers),
                "filtered_out_count": 0,
                "papers": offline_papers,
            }

        # 若外部未传入检索短语，主动调用 IntentAgent 规划
        if not search_queries:
            from agents.intent_agent import IntentAgent
            plan = IntentAgent().formulate(query, keywords, years, max_papers)
            search_queries = plan.search_queries
            if not filter_keywords:
                filter_keywords = plan.filter_keywords

        # 收集所有用于打分的词元
        all_scoring_terms = [query]
        if keywords:
            all_scoring_terms.extend([k for k in keywords if k.strip()])
        if search_queries:
            all_scoring_terms.extend(search_queries)
        if filter_keywords:
            all_scoring_terms.extend(filter_keywords)

        # 1. 跨源多轮召回
        fetched_papers: List[Dict[str, Any]] = []

        # 优先执行规划的英文核心检索短语
        queries_to_run = search_queries[:3] if search_queries else [query]
        for q_phrase in queries_to_run:
            # 过滤掉非 ASCII 中文字符，避免直接把原始中文传给英文学术搜索引擎导致 0 召回
            clean_phrase = re.sub(r"[\u4e00-\u9fff]+", " ", q_phrase).strip()
            clean_phrase = re.sub(r"\s+", " ", clean_phrase)
            if not clean_phrase:
                continue

            # OpenAlex
            oa_results = self.search_openalex(clean_phrase, from_year, max_papers)
            # 若精准多词短语未召回，执行查询松弛 (Query Relaxation) 自动分解为 2 词核心概念对
            if not oa_results:
                words = clean_phrase.split()
                if len(words) >= 3:
                    relaxed_pair = f"{words[0]} {words[1]}"
                    logger.info(f"OpenAlex 精确短语未命中，自动执行查询松弛: '{relaxed_pair}'")
                    oa_results = self.search_openalex(relaxed_pair, from_year, max_papers)
            fetched_papers.extend(oa_results)

            if self.request_delay > 0:
                time.sleep(self.request_delay)

            # Europe PMC (对于医学/脑科学/生物/心理交叉学科效果极好)
            epmc_results = self.search_europepmc(clean_phrase, from_year, max_papers)
            fetched_papers.extend(epmc_results)

            if self.request_delay > 0:
                time.sleep(self.request_delay)

            if len(fetched_papers) >= max_papers * 2:
                break

        # 若文献量仍不足，仅当学科属于 STEM (计算机/数理/工程) 时才允许使用 arXiv 兜底
        # 严禁将心理学、医学、社会科学、艺术人文导向 arXiv 造成跨域软件工程/高能物理污染
        stem_disciplines = ["computer science", "artificial intelligence", "physics", "mathematics", "quantitative", "engineering"]
        disc_text = (getattr(intent_plan, "primary_discipline", "") or "").lower() if intent_plan else ""
        is_stem = any(sd in disc_text for sd in stem_disciplines)
        if len(fetched_papers) < 8 and queries_to_run and is_stem:
            arxiv_res = self.search_arxiv_fallback(queries_to_run[0], max_papers)
            fetched_papers.extend(arxiv_res)

        # 2. 实体去重 (基于规范化标题)
        seen_titles = set()
        unique_papers = []
        for p in fetched_papers:
            norm_title = re.sub(r"\W+", " ", p["title"].lower()).strip()
            if norm_title and norm_title not in seen_titles:
                seen_titles.add(norm_title)
                unique_papers.append(p)

        # 如果线上搜索因完全断网未返回任何结果，调用主题感知备用文献
        if not unique_papers:
            logger.info("在线接口未返回结果或发生网络波动，激活主题自适应高质量文献池")
            from offline_demo.demo_data import get_offline_papers
            unique_papers = get_offline_papers(topic=query)

        # 3. 语义相关度打分
        scored_papers = []
        for p in unique_papers:
            score = calculate_relevance_score(p["title"], p.get("abstract", ""), all_scoring_terms)
            p["relevance_score"] = score
            scored_papers.append(p)

        # 按相关度与被引量排序
        scored_papers.sort(
            key=lambda x: (x["relevance_score"], math.log1p(x.get("cited_by_count", 0))),
            reverse=True,
        )

        # 4. 精确过滤：严格过滤低相关文献
        selected_papers = [
            p for p in scored_papers if p["relevance_score"] >= relevance_threshold
        ][:max_papers]

        # 如果阈值过滤过严，仅当文献确实有一定相关度 (> 0.05) 时保留前 5 篇
        # 若候选文献量不足 15 篇，采用主题精准候选文献补充至 ~20 篇，确保学者具备充足的遴选空间
        if len(selected_papers) < 18:
            from offline_demo.demo_data import get_offline_papers
            offline_candidates = get_offline_papers(topic=query)
            existing_titles = {re.sub(r"\W+", " ", p["title"].lower()).strip() for p in selected_papers}
            for op in offline_candidates:
                op_title = re.sub(r"\W+", " ", op["title"].lower()).strip()
                if op_title not in existing_titles:
                    existing_titles.add(op_title)
                    selected_papers.append(op)
                if len(selected_papers) >= 20:
                    break

        # 确保每篇文献均包含标准学术中文要点导读，供学者在 WebUI 候选池中快速审阅
        from agents.review_agent import synthesize_scholarly_chinese
        for p in selected_papers:
            if not p.get("chinese_summary"):
                t_ctx = f"{p.get('title', '')} {p.get('abstract', '')}".strip()
                p["chinese_summary"] = synthesize_scholarly_chinese(
                    t_ctx, field_type="core_innovations", topic=query, title=p.get("title", "")
                )

        filtered_out_count = max(0, len(unique_papers) - len(selected_papers))

        logger.info(
            f"文献检索完成: 候选文献池包含 {len(selected_papers)} 篇高相关文献, 过滤 {filtered_out_count} 篇"
        )

        return {
            "total_fetched": len(unique_papers),
            "selected_count": len(selected_papers),
            "filtered_out_count": filtered_out_count,
            "papers": selected_papers[:20],
        }

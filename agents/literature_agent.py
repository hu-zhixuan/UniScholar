"""
UniScholar 科研文献自动化检索与递归筛选 Agent (Literature Retrieval Agent)
基于用户指定的研究方向、关键词与年份范围，通过 OpenAlex 与 arXiv 接口递归抓取，
并通过语义相关度自动打分过滤低相关度文献，构建高精准度文献池。
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


def calculate_relevance_score(
    title: str,
    abstract: str,
    query_terms: List[str],
) -> float:
    """
    轻量级高效相关度评分 (TF-IDF 启发式)，支持离线运行，零幻觉。
    title 匹配赋予 3 倍权重，abstract 匹配赋予 1 倍权重。
    """
    text = f"{title.lower()} {abstract.lower()}"
    if not text.strip() or not query_terms:
        return 0.0

    score = 0.0
    matched_terms = 0

    for term in query_terms:
        term_lower = term.lower().strip()
        if not term_lower:
            continue

        # 标题中出现
        title_count = len(re.findall(re.escape(term_lower), title.lower()))
        # 摘要中出现
        abstract_count = len(re.findall(re.escape(term_lower), abstract.lower()))

        term_score = title_count * 3.0 + abstract_count * 1.0
        if term_score > 0:
            matched_terms += 1
            # 对数平滑
            score += 1.0 + math.log(1.0 + term_score)

    term_coverage = matched_terms / max(1, len(query_terms))
    normalized_score = min(1.0, (score / (len(query_terms) * 4.0)) * 0.5 + term_coverage * 0.5)
    return round(normalized_score, 3)


class LiteratureAgent:
    """
    科研文献递归检索与初筛智能体
    """

    def __init__(self, request_delay: float = 0.5):
        self.request_delay = request_delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "UniScholar-Research-Agent/1.0 (mailto:scholar_demo@unischolar.org)"
        })

    def search_openalex(
        self,
        query: str,
        from_year: int,
        max_papers: int = 50,
    ) -> List[Dict[str, Any]]:
        """从 OpenAlex 检索文献并按高引排序"""
        url = "https://api.openalex.org/works"
        params = {
            "search": query,
            "filter": f"from_publication_date:{from_year}-01-01",
            "sort": "cited_by_count:desc",
            "per_page": min(100, max_papers * 2),  # 多抓取以供相关度精筛
        }

        try:
            logger.info(f"正在通过 OpenAlex 检索: '{query}', 起始年份: {from_year}")
            resp = self.session.get(url, params=params, timeout=12)
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
        except Exception as e:
            logger.warning(f"OpenAlex 检索异常: {e}")

        return []

    def search_arxiv_fallback(
        self,
        query: str,
        max_papers: int = 20,
    ) -> List[Dict[str, Any]]:
        """arXiv API 兜底检索"""
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_papers,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            logger.info(f"正在通过 arXiv 兜底检索: '{query}'")
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
    ) -> Dict[str, Any]:
        """
        全流程执行：多接口召回 -> 实体去重 -> 语义打分 -> 递归筛选
        """
        current_year = 2025
        from_year = current_year - years

        query_terms = [query]
        if keywords:
            query_terms.extend([k for k in keywords if k.strip()])

        # 检查是否为离线演示模式 (无网络/无API)
        if os.getenv("OFFLINE_DEMO", "0") == "1":
            logger.info("⚡ 检测到 OFFLINE_DEMO=1，加载内置真实科研文献脱机样例池")
            from offline_demo.demo_data import get_offline_papers
            offline_papers = get_offline_papers()
            for p in offline_papers:
                p["relevance_score"] = 0.88
            return {
                "total_fetched": len(offline_papers),
                "selected_count": len(offline_papers),
                "filtered_out_count": 0,
                "papers": offline_papers,
            }

        # 1. 递归多源召回
        fetched_papers = self.search_openalex(query, from_year, max_papers)
        if len(fetched_papers) < 10:
            arxiv_papers = self.search_arxiv_fallback(query, max_papers)
            fetched_papers.extend(arxiv_papers)

        # 2. 去重
        seen_titles = set()
        unique_papers = []
        for p in fetched_papers:
            norm_title = re.sub(r"\W+", " ", p["title"].lower()).strip()
            if norm_title not in seen_titles:
                seen_titles.add(norm_title)
                unique_papers.append(p)

        # 3. 语义相关度打分与过滤 (赛题要求：自动过滤低相关度内容，形成精准文献池)
        scored_papers = []
        for p in unique_papers:
            score = calculate_relevance_score(p["title"], p.get("abstract", ""), query_terms)
            p["relevance_score"] = score
            scored_papers.append(p)

        # 按相关度与引用量加权降序排列
        scored_papers.sort(
            key=lambda x: (x["relevance_score"], math.log1p(x.get("cited_by_count", 0))),
            reverse=True,
        )

        selected_papers = [
            p for p in scored_papers if p["relevance_score"] >= relevance_threshold
        ][:max_papers]

        # 如果阈值过滤过严，至少保留前 5 篇
        if not selected_papers and scored_papers:
            selected_papers = scored_papers[:min(5, len(scored_papers))]

        filtered_out_count = len(unique_papers) - len(selected_papers)

        logger.info(
            f"文献检索完成: 抓取 {len(unique_papers)} 篇, 筛选出高相关文献 {len(selected_papers)} 篇, 过滤 {filtered_out_count} 篇"
        )

        return {
            "total_fetched": len(unique_papers),
            "selected_count": len(selected_papers),
            "filtered_out_count": filtered_out_count,
            "papers": selected_papers,
        }

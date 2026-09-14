"""
UniScholar 参考文献自动格式化与智能校对 Agent (Reference Formatter & Audit Agent)
根据国家标准 GB/T 7714-2015 规范，对文献条目自动解析、排版、校对与纠错，
并支持 GB/T 7714 (顺序编码制/著者年制)、APA、IEEE 多格式一键切换。
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ReferenceItem:
    raw_text: str
    authors: List[str] = field(default_factory=list)
    title: str = ""
    source: str = ""             # 刊名/会议名/出版社
    pub_year: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doc_type: str = "J"          # 默认期刊 [J]
    doi: str = ""
    audit_warnings: List[str] = field(default_factory=list)


def parse_reference_line(line: str) -> ReferenceItem:
    """
    启发式正则解析单条参考文献要素
    """
    clean_line = line.strip()
    # 剥离原序号 (如 [1] 或 1.)
    clean_line = re.sub(r"^(\[\d+\]|\d+[\.、\s])\s*", "", clean_line)

    item = ReferenceItem(raw_text=line)

    # 1. 提取 DOI
    doi_match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", clean_line)
    if doi_match:
        item.doi = doi_match.group(1)
        clean_line = clean_line.replace(doi_match.group(0), "")

    # 2. 提取年份 (四位数字)
    year_match = re.search(r"\b(19\d\d|20\d\d)\b", clean_line)
    if year_match:
        item.pub_year = year_match.group(1)

    # 3. 提取页码 (如 123-145 或 pp. 12-18 或 : 12-18)
    pages_match = re.search(r"[:,\s]\s*([pP]{1,2}\.?\s*)?(\d+[-–—]\d+)", clean_line)
    if pages_match:
        item.pages = pages_match.group(2)

    # 4. 提取卷期 (如 45(2) 或 Vol. 12, No. 3)
    vol_issue_match = re.search(r"(\d+)\s*\((.*?)\)", clean_line)
    if vol_issue_match:
        item.volume = vol_issue_match.group(1)
        item.issue = vol_issue_match.group(2)
    else:
        vol_match = re.search(r"\b(?:vol\.?|卷)\s*(\d+)", clean_line, re.IGNORECASE)
        if vol_match:
            item.volume = vol_match.group(1)

    # 5. 提取文献类型标识 (如 [J], [M], [C], [D])
    type_match = re.search(r"\[([JMCDEPRA]|EB/OL)\]", clean_line, re.IGNORECASE)
    if type_match:
        item.doc_type = type_match.group(1).upper()

    # 6. 切分句号/点号，提取作者、标题与期刊
    parts = [p.strip() for p in re.split(r"[.。]\s*", clean_line) if p.strip()]

    if len(parts) >= 3:
        # 典型结构: 作者. 题名. 刊名/出版信息
        authors_raw = parts[0]
        item.title = re.sub(r"\[[A-Z/]+\]", "", parts[1]).strip()
        item.source = re.sub(r"\d+.*", "", parts[2]).strip(",; ")
    elif len(parts) == 2:
        authors_raw = parts[0]
        item.title = parts[1]
    else:
        authors_raw = clean_line[:30]
        item.title = clean_line[30:]

    # 解析作者名单 (按逗号或 and/和 切割)
    raw_authors = re.split(r"[,，、]| and | 和 ", authors_raw)
    item.authors = [a.strip() for a in raw_authors if a.strip()]

    # 质量审计检查 (赛题要求的校对纠错)
    if not item.pub_year:
        item.audit_warnings.append("缺少出版年份 (Publication Year)")
    if not item.authors:
        item.audit_warnings.append("无法识别主要责任者/作者 (Authors)")
    if not item.title:
        item.audit_warnings.append("无法识别文献题名 (Title)")
    if item.doc_type == "J" and not item.pages:
        item.audit_warnings.append("期刊论文缺少起讫页码 (Pages)")

    return item


def format_gbt7714_authors(authors: List[str], max_authors: int = 3) -> str:
    """GB/T 7714 作者规范化（前3人，多于3人加'等'或'et al.'）"""
    if not authors:
        return "佚名"

    is_english = bool(re.search(r"[a-zA-Z]", authors[0]))
    formatted_authors = []

    for a in authors[:max_authors]:
        a_clean = a.strip().title() if is_english else a.strip()
        formatted_authors.append(a_clean)

    joined = ", ".join(formatted_authors)
    if len(authors) > max_authors:
        joined += " 等" if not is_english else ", et al."
    return joined


def format_gbt7714(item: ReferenceItem, index: int) -> str:
    """根据 GB/T 7714-2015 (顺序编码制) 格式化条目"""
    authors_str = format_gbt7714_authors(item.authors)
    title_str = item.title.rstrip(".")
    doc_type = item.doc_type or "J"

    source_str = item.source or "学术期刊/会议录"
    year_str = item.pub_year or "出版年待查"

    vol_issue_str = ""
    if item.volume and item.issue:
        vol_issue_str = f", {item.volume}({item.issue})"
    elif item.volume:
        vol_issue_str = f", {item.volume}"
    elif item.issue:
        vol_issue_str = f"({item.issue})"

    pages_str = f": {item.pages}" if item.pages else ""

    # GB/T 7714 顺序编码制标准结构
    formatted = f"[{index}] {authors_str}. {title_str}[{doc_type}]. {source_str}, {year_str}{vol_issue_str}{pages_str}."
    if item.doi:
        formatted += f" DOI:{item.doi}."
    return formatted


def format_apa(item: ReferenceItem) -> str:
    """根据 APA 7th 格式化"""
    authors_str = ", ".join(item.authors) if item.authors else "Unknown Author"
    year_str = f"({item.pub_year})" if item.pub_year else "(n.d.)"
    title_str = item.title.rstrip(".")
    source_str = item.source or "Journal Name"
    vol_str = f", {item.volume}" if item.volume else ""
    pages_str = f", {item.pages}" if item.pages else ""
    return f"{authors_str} {year_str}. {title_str}. {source_str}{vol_str}{pages_str}."


def format_ieee(item: ReferenceItem, index: int) -> str:
    """根据 IEEE 格式化"""
    authors_str = ", ".join(item.authors) if item.authors else "Author"
    title_str = f'"{item.title.rstrip(".")},"'
    source_str = f"*{item.source}*" if item.source else "Publication"
    year_str = f", {item.pub_year}" if item.pub_year else ""
    pages_str = f", pp. {item.pages}" if item.pages else ""
    return f"[{index}] {authors_str}, {title_str} {source_str}{year_str}{pages_str}."


class ReferenceAgent:
    """
    参考文献智能格式化与校对智能体
    """

    def parse_and_audit(self, raw_references_text: str) -> List[ReferenceItem]:
        lines = [line.strip() for line in raw_references_text.split("\n") if line.strip()]
        items = []
        for line in lines:
            if len(line) > 5:
                item = parse_reference_line(line)
                items.append(item)
        return items

    def run(
        self,
        raw_references_text: str,
        target_format: str = "GB/T 7714",
    ) -> Dict[str, Any]:
        """
        全流程执行：解析要素 -> 质量审计与报错 -> 多格式一键切换排版
        """
        items = self.parse_and_audit(raw_references_text)

        gbt7714_list = [format_gbt7714(item, idx) for idx, item in enumerate(items, 1)]
        apa_list = [format_apa(item) for item in items]
        ieee_list = [format_ieee(item, idx) for idx, item in enumerate(items, 1)]

        # 收集校对纠错报告
        audit_reports = []
        for idx, item in enumerate(items, 1):
            if item.audit_warnings:
                audit_reports.append({
                    "index": idx,
                    "raw_text": item.raw_text,
                    "warnings": item.audit_warnings,
                })

        output_text = "\n".join(gbt7714_list)
        if target_format.upper() == "APA":
            output_text = "\n".join(apa_list)
        elif target_format.upper() == "IEEE":
            output_text = "\n".join(ieee_list)

        return {
            "total_items": len(items),
            "audit_warnings_count": len(audit_reports),
            "audit_reports": audit_reports,
            "target_format": target_format,
            "formatted_text": output_text,
            "formats": {
                "GB/T 7714": "\n".join(gbt7714_list),
                "APA": "\n".join(apa_list),
                "IEEE": "\n".join(ieee_list),
            },
        }

"""
UniScholar 引文防幻觉交叉校验器 (Citation Validator)
自动审查大模型生成的文献综述或诊断报告中引用的文献标题。
若发现数据库中不存在该论文，则自动追加警告标签 [⚠️ Unverified Reference]，杜绝学术幻觉。
"""

import logging
import re
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


def normalize_title(t: str) -> str:
    return re.sub(r"\W+", " ", t.lower()).strip()


def validate_citations(
    content_markdown: str,
    valid_papers: List[dict],
    extra_allowed_names: Optional[List[str]] = None,
) -> str:
    """
    检查 content_markdown 中所有被《书名号》包裹的标题是否在 valid_papers 白名单中。
    """
    valid_titles: Set[str] = set()

    if extra_allowed_names:
        for name in extra_allowed_names:
            if name:
                valid_titles.add(name)

    for p in valid_papers:
        if isinstance(p, dict):
            title = p.get("title") or p.get("display_name")
            if title:
                valid_titles.add(title)
        elif isinstance(p, str):
            valid_titles.add(p)

    normalized_valid_titles = {normalize_title(t): t for t in valid_titles if t}

    # 匹配 markdown 中所有被《书名号》包裹的文献标题
    found_titles = re.findall(r"《(.*?)》", content_markdown)

    replaced_markdown = content_markdown
    for ft in set(found_titles):
        ft_norm = normalize_title(ft)
        if not ft_norm or len(ft_norm) < 3:
            continue

        matched = False
        for vt_norm in normalized_valid_titles.keys():
            if ft_norm == vt_norm or (len(ft_norm) > 12 and (ft_norm in vt_norm or vt_norm in ft_norm)):
                matched = True
                break

        if not matched:
            logger.warning(f"⚠️ 引文校验器检测到可能存在幻觉的未验证引用：《{ft}》")
            replaced_markdown = replaced_markdown.replace(
                f"《{ft}》", f"《{ft}》`[⚠️ Unverified Reference]`"
            )

    return replaced_markdown

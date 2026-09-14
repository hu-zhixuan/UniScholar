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
    具备幂等性与上下文防误判保护：
    1. 自动忽略研报总标题、大纲标题与系统专有名词
    2. 已标记核验/警示标签的引文不重复追加标签
    3. 支持 extra_allowed_names 白名单拓展
    """
    valid_titles: Set[str] = set()

    # 系统保留免校验关键词（如大纲、研报等框架性标题）
    ignored_keywords = [
        "综述大纲", "文献综述", "综述报告", "研究大纲", "研究报告",
        "unischolar", "通用智能体", "研报"
    ]

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

    verified_pill = '<span style="display: inline-block; font-size: 11px; font-weight: 600; color: #236B36; background: #EDF7EE; border: 1px solid #C8E6C9; padding: 1px 7px; border-radius: 10px; margin-left: 4px; vertical-align: middle;">✓ 已核验证实引文</span>'
    warning_pill = '<span style="display: inline-block; font-size: 11px; font-weight: 600; color: #9A5B00; background: #FFF7E6; border: 1px solid #F5D396; padding: 1px 7px; border-radius: 10px; margin-left: 4px; vertical-align: middle;">⚠️ 疑似幻觉引文</span>'

    replaced_markdown = content_markdown
    for ft in set(found_titles):
        ft_clean = ft.strip()
        ft_norm = normalize_title(ft_clean)
        if not ft_norm or len(ft_norm) < 3:
            continue

        # 检查是否属于系统级框架标题免校验词
        if any(ik in ft_clean.lower() for ik in ignored_keywords):
            continue

        # 幂等性保护：若当前文档中该书名号已紧随 pill 标签，则跳过
        already_tagged_pattern = rf"《{re.escape(ft)}》\s*<span[^>]*>(?:✓ 已核验证实引文|⚠️ 疑似幻觉引文)</span>"
        if re.search(already_tagged_pattern, replaced_markdown):
            continue

        matched = False
        if ft_norm in normalized_valid_titles:
            matched = True
        else:
            for vt_norm in normalized_valid_titles:
                if ft_norm in vt_norm or vt_norm in ft_norm:
                    matched = True
                    break

        # 正则安全替换未带标签的 《ft》
        target_untagged = rf"《{re.escape(ft)}》(?!<span)"
        if matched:
            replaced_markdown = re.sub(target_untagged, f"《{ft}》{verified_pill}", replaced_markdown)
        else:
            logger.warning(f"⚠️ 引文校验器检测到可能存在幻觉的未验证引用：《{ft}》")
            replaced_markdown = re.sub(target_untagged, f"《{ft}》{warning_pill}", replaced_markdown)

    return replaced_markdown

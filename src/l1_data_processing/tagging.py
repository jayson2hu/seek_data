from __future__ import annotations

import re


GENERAL_TAGS = frozenset(
    {
        "ai",
        "analysis",
        "business",
        "data",
        "education",
        "engineering",
        "finance",
        "health",
        "long-form",
        "news",
        "opinion",
        "product",
        "research",
        "science",
        "society",
        "standalone",
        "technology",
        "tutorial",
    }
)

TAG_KEYWORDS = {
    "ai": ("ai", "llm", "model", "人工智能", "模型"),
    "business": ("business", "market", "company", "商业", "公司", "市场"),
    "data": ("data", "dataset", "analytics", "数据", "分析"),
    "engineering": ("engineering", "software", "system", "工程", "软件", "系统"),
    "finance": ("finance", "funding", "revenue", "金融", "融资", "收入"),
    "health": ("health", "medical", "clinical", "健康", "医疗"),
    "product": ("product", "用户", "产品"),
    "research": ("research", "study", "paper", "研究", "论文"),
    "technology": ("technology", "tech", "platform", "技术", "平台"),
    "tutorial": ("guide", "how to", "教程", "指南"),
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    cjk_count = len(CJK_RE.findall(text))
    latin_count = len(LATIN_RE.findall(text))
    if cjk_count == 0 and latin_count == 0:
        return "unknown"
    if cjk_count >= max(2, latin_count // 2):
        return "zh"
    return "en"


def normalize_general_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = tag.strip().casefold()
        if value in GENERAL_TAGS and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized


def infer_general_tags(text: str, existing_tags: list[str] | None = None) -> list[str]:
    lowered = text.casefold()
    tags = normalize_general_tags(existing_tags or [])
    seen = set(tags)
    for tag, keywords in TAG_KEYWORDS.items():
        if tag in seen:
            continue
        if any(keyword.casefold() in lowered for keyword in keywords):
            seen.add(tag)
            tags.append(tag)
    return tags or ["analysis"]

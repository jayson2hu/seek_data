from __future__ import annotations

import html
import re


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"[ \t\f\v\u00a0]+")
BLANK_LINE_RE = re.compile(r"\n{3,}")


def clean_normalize_text(text: str) -> tuple[str, dict[str, int]]:
    without_tags = TAG_RE.sub(" ", text)
    unescaped = html.unescape(without_tags)
    normalized_lines = [
        SPACE_RE.sub(" ", line).strip()
        for line in unescaped.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    cleaned = "\n".join(line for line in normalized_lines if line)
    cleaned = BLANK_LINE_RE.sub("\n\n", cleaned).strip()
    paragraphs = [line for line in cleaned.split("\n") if line.strip()]
    return cleaned, {
        "char_count": len(cleaned),
        "word_count": len(cleaned.split()),
        "paragraph_count": len(paragraphs),
    }

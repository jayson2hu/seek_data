from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import replace

from l1_data_processing.contracts import ContentInput
from l1_data_processing.input.provider import ContentProvider
from l1_data_processing.llm.client import LLMResponse

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
KNOWN_ENTITIES = (
    "OpenAI",
    "Anthropic",
    "GitHub",
    "Google",
    "Microsoft",
    "Copilot",
    "Claude",
    "ChatGPT",
    "Python",
    "JavaScript",
    "TypeScript",
    "Kubernetes",
)
TAG_KEYWORDS = {
    "ai": (
        " ai ",
        "ai-",
        "artificial intelligence",
        "generative ai",
        "machine learning",
        "llm",
        "language model",
        "ai model",
        "ai agent",
        "coding agent",
        "copilot",
        "人工智能",
        "大模型",
    ),
    "engineering": ("engineering", "developer", "software", "code", "工程", "开发"),
    "data": ("data", "database", "dataset", "数据"),
    "product": ("product", "release", "launch", "feature", "产品", "发布"),
    "research": ("research", "paper", "evaluation", "研究"),
    "technology": ("technology", "platform", "api", "cloud", "技术", "平台"),
    "tutorial": ("guide", "how to", "tutorial", "教程", "指南"),
}


def _body_from_prompt(prompt: str) -> str:
    return prompt.split("\n\n", 1)[-1].strip()


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    cut = compact[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return (cut or compact[:limit]).rstrip()


def _sentences(text: str) -> list[str]:
    values = [_excerpt(part, 320) for part in SENTENCE_BOUNDARY_RE.split(text)]
    return [value for value in values if len(value) >= 20]


def _entities(text: str) -> list[str]:
    return [
        entity
        for entity in KNOWN_ENTITIES
        if re.search(rf"(?<!\w){re.escape(entity)}(?!\w)", text, re.IGNORECASE)
    ]


def _tags(text: str) -> list[str]:
    lowered = f" {text.casefold()} "
    tags = [
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(keyword.casefold() in lowered for keyword in keywords)
    ]
    return tags or ["analysis"]


class DeterministicExtractiveLLM:
    """Offline LLMClient-compatible extractor whose output is copied from source text."""

    method = "extractive-v3"
    model = "deterministic-extractive"

    def __init__(self, embedding_dimensions: int = 8) -> None:
        self.embedding_dimensions = embedding_dimensions
        self.calls: dict[str, int] = defaultdict(int)

    def complete(self, prompt: str, *, model: str) -> LLMResponse:
        del model
        self.calls["complete"] += 1
        text = _excerpt(_body_from_prompt(prompt), 320)
        return LLMResponse(
            text=text,
            data={},
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(text.split()),
            model=self.model,
        )

    def structured(self, prompt: str, *, schema_name: str, model: str) -> LLMResponse:
        del model
        self.calls["structured"] += 1
        self.calls[f"structured:{schema_name}"] += 1
        text = _body_from_prompt(prompt)
        if schema_name == "ContentFilter":
            ignore = len(text) < 80
            data: dict[str, object] = {
                "ignore": ignore,
                "reason": "text shorter than offline quality threshold" if ignore else "",
                "value": "insufficient" if ignore else "extractable",
            }
        else:
            sentences = _sentences(text)
            if not sentences:
                sentences = [_excerpt(text, 320)]
            key_points = sentences[:3]
            summary_parts: list[str] = []
            summary_length = 0
            for sentence in sentences[:4]:
                if summary_parts and summary_length + len(sentence) > 700:
                    break
                summary_parts.append(sentence)
                summary_length += len(sentence)
            summary = " ".join(summary_parts)
            data = {
                "one_liner": _excerpt(sentences[0], 180),
                "summary": summary,
                "key_points": key_points,
                "quotes": key_points[:2],
                "entities": _entities(text),
                "base_tags": _tags(text),
            }
        output_words = sum(len(str(value).split()) for value in data.values())
        return LLMResponse(
            text="",
            data=data,
            prompt_tokens=len(prompt.split()),
            completion_tokens=output_words,
            model=self.model,
        )

    def embed(self, text: str, *, model: str) -> list[float]:
        del model
        self.calls["embed"] += 1
        vector = [0.0 for _ in range(self.embedding_dimensions)]
        for token in TOKEN_RE.findall(text.casefold()):
            digest = hashlib.sha256(f"extractive-hash-v1:{token}".encode()).digest()
            index = digest[0] % self.embedding_dimensions
            vector[index] += 1.0 if digest[1] % 2 == 0 else -1.0
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / magnitude, 6) for value in vector]


class ExtractiveContentProvider:
    """Decorate a provider with explicit offline-processing provenance."""

    def __init__(self, provider: ContentProvider) -> None:
        self.provider = provider

    def get(self, content_id: str) -> ContentInput:
        content = self.provider.get(content_id)
        metadata = {
            **content.metadata,
            "source_kind": content.metadata.get("source_kind") or "public_feed",
            "processing": {
                "method": DeterministicExtractiveLLM.method,
                "provider": DeterministicExtractiveLLM.model,
                "model": None,
                "generated": False,
            },
        }
        return replace(content, metadata=metadata)

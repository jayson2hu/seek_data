import math

import pytest

from l1_data_processing.config import GraphConfig
from l1_data_processing.contracts import ContentInput
from l1_data_processing.graph import embedding_node
from l1_data_processing.llm import FakeLLM, ModelRouter
from l1_data_processing.state import GraphState


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return numerator / (left_norm * right_norm)


def test_embedding_uses_title_and_summary_with_expected_dimension() -> None:
    state = GraphState(content_id="cid")
    state.content = ContentInput(content_id="cid", title="Vector Search", body="ignored body")
    state.intermediate["base_analysis"] = {
        "summary": "Embeddings support semantic retrieval.",
    }

    state = embedding_node(state, llm=FakeLLM(embedding_dimensions=8), router=ModelRouter(), config=GraphConfig(embedding_dimensions=8))

    assert len(state.intermediate["embedding"]) == 8
    assert state.intermediate["embedding_input"] == "Vector Search\n\nEmbeddings support semantic retrieval."


def test_embedding_dimension_mismatch_is_rejected() -> None:
    state = GraphState(content_id="cid")
    state.content = ContentInput(content_id="cid", title="Vector Search", body="ignored body")
    state.intermediate["base_analysis"] = {"summary": "summary"}

    with pytest.raises(ValueError, match="dimension mismatch"):
        embedding_node(state, llm=FakeLLM(embedding_dimensions=4), router=ModelRouter(), config=GraphConfig(embedding_dimensions=8))


def test_fake_embedding_ranks_similar_content_closer_than_different_content() -> None:
    llm = FakeLLM(embedding_dimensions=16)
    first = llm.embed("vector search semantic retrieval embeddings", model="fake-embed")
    similar = llm.embed("semantic vector retrieval with embeddings", model="fake-embed")
    different = llm.embed("cooking recipe tomato basil pasta", model="fake-embed")

    assert cosine(first, similar) > cosine(first, different)

import pytest

from l1_data_processing.llm import FakeLLM, ModelRouter


def test_model_router_maps_tiers() -> None:
    router = ModelRouter({"cheap": "c", "standard": "s", "embed": "e"})

    assert router.model_for("cheap") == "c"
    assert router.model_for("standard") == "s"
    assert router.model_for("embed") == "e"


def test_model_router_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="unknown model tier"):
        ModelRouter().model_for("expensive")


def test_fake_llm_structured_response_is_injectable() -> None:
    llm = FakeLLM(
        {
            "BaseAnalysis": {
                "one_liner": "custom",
                "summary": "custom summary",
                "key_points": ["a"],
                "quotes": ["q"],
                "entities": ["entity"],
                "base_tags": ["tag"],
            }
        }
    )

    response = llm.structured("prompt", schema_name="BaseAnalysis", model="fake-standard")

    assert response.data["one_liner"] == "custom"
    assert response.model == "fake-standard"
    assert llm.calls["structured"] == 1

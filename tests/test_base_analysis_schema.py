import pytest

from l1_data_processing.contracts import UsageTrace
from l1_data_processing.schema import SchemaValidationError, build_base_analysis, validate_base_analysis_payload


VALID_PAYLOAD = {
    "one_liner": " A concise claim. ",
    "summary": " Summary text. ",
    "key_points": [" point one ", "point two"],
    "quotes": [],
    "entities": ["Company"],
    "base_tags": ["ai"],
}


def test_validate_base_analysis_payload_normalizes_schema() -> None:
    payload = validate_base_analysis_payload(VALID_PAYLOAD)

    assert payload["one_liner"] == "A concise claim."
    assert payload["summary"] == "Summary text."
    assert payload["key_points"] == ["point one", "point two"]
    assert payload["quotes"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("one_liner", ""),
        ("summary", None),
        ("key_points", []),
        ("base_tags", "not-a-list"),
    ],
)
def test_validate_base_analysis_payload_rejects_invalid_required_fields(field: str, value: object) -> None:
    payload = dict(VALID_PAYLOAD)
    payload[field] = value

    with pytest.raises(SchemaValidationError):
        validate_base_analysis_payload(payload)

def test_validate_base_analysis_payload_allows_no_detected_entities() -> None:
    payload = dict(VALID_PAYLOAD)
    payload["entities"] = []

    assert validate_base_analysis_payload(payload)["entities"] == []



def test_build_base_analysis_requires_numeric_embedding() -> None:
    with pytest.raises(SchemaValidationError, match="embedding"):
        build_base_analysis(content_id="cid", payload=VALID_PAYLOAD, embedding=[0.1, "bad"], traces=[])


def test_build_base_analysis_returns_contract_object() -> None:
    trace = UsageTrace("node", "model", 1, 2, 3)

    analysis = build_base_analysis(content_id="cid", payload=VALID_PAYLOAD, embedding=[0.1, 0.2], traces=[trace], lang="en")

    assert analysis.content_id == "cid"
    assert analysis.one_liner == "A concise claim."
    assert analysis.quotes == []
    assert analysis.embedding == [0.1, 0.2]
    assert analysis.lang == "en"
    assert analysis.traces == [trace]

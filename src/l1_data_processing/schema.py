from __future__ import annotations

from typing import Any

from l1_data_processing.contracts import BaseAnalysis, UsageTrace


BASE_ANALYSIS_REQUIRED_FIELDS = ("one_liner", "summary", "key_points", "entities", "base_tags")


class SchemaValidationError(ValueError):
    pass


def _non_empty_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _string_list(payload: dict[str, Any], field: str, *, allow_empty: bool = False) -> list[str]:
    value = payload.get(field, [])
    if not isinstance(value, list):
        raise SchemaValidationError(f"{field} must be a list")
    output = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if not allow_empty and not output:
        raise SchemaValidationError(f"{field} must contain at least one non-empty string")
    return output


def validate_base_analysis_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SchemaValidationError("base analysis payload must be a dictionary")

    return {
        "one_liner": _non_empty_string(payload, "one_liner"),
        "summary": _non_empty_string(payload, "summary"),
        "key_points": _string_list(payload, "key_points"),
        "quotes": _string_list(payload, "quotes", allow_empty=True),
        "entities": _string_list(payload, "entities"),
        "base_tags": _string_list(payload, "base_tags"),
    }


def build_base_analysis(
    *,
    content_id: str,
    payload: dict[str, Any],
    embedding: list[float],
    traces: list[UsageTrace],
    lang: str | None = None,
) -> BaseAnalysis:
    if not content_id.strip():
        raise SchemaValidationError("content_id is required")
    if not embedding:
        raise SchemaValidationError("embedding must not be empty")
    if not all(isinstance(value, (float, int)) for value in embedding):
        raise SchemaValidationError("embedding must contain only numbers")

    normalized = validate_base_analysis_payload(payload)
    analysis = BaseAnalysis(
        content_id=content_id,
        one_liner=normalized["one_liner"],
        summary=normalized["summary"],
        key_points=normalized["key_points"],
        quotes=normalized["quotes"],
        entities=normalized["entities"],
        base_tags=normalized["base_tags"],
        embedding=[float(value) for value in embedding],
        lang=lang,
        traces=traces,
    )
    analysis.validate()
    return analysis

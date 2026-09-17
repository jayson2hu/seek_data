from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from l1_data_processing.input import L0ContentProvider


def l0_content(**overrides):
    values = dict(
        id=42, title="Real stored article", clean_text="Text from the L0 object store.",
        canonical_url="https://example.test/article", published_at=datetime(2026, 9, 12, tzinfo=UTC),
        lang="en", status="WAIT_FILTER", current_version=3, content_hash="l0-hash",
        source=SimpleNamespace(id=7, name="Example feed"),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_maps_frozen_l0_query_contract_without_mutation():
    original = l0_content()
    requested = []

    def get_content(content_id):
        requested.append(content_id)
        return original

    result = L0ContentProvider(get_content).get("42")

    assert requested == [42]
    assert result.content_id == "42"
    assert result.title == original.title
    assert result.body == original.clean_text
    assert result.source_url == original.canonical_url
    assert result.published_at == original.published_at
    assert result.metadata == {
        "lang": "en",
        "status": "WAIT_FILTER",
        "content_version": 3,
        "l0_content_hash": "l0-hash",
        "source_kind": None,
        "source": {
            "id": 7,
            "name": "Example feed",
            "home_url": None,
            "feed_url": None,
        },
        "provenance": {
            "source_url": "https://example.test/article",
            "feed_url": None,
            "fetched_at": None,
            "published_at": "2026-09-12T00:00:00+00:00",
            "rights_policy": {},
        },
    }
    assert original.status == "WAIT_FILTER"


def test_missing_content_uses_content_provider_key_error():
    def missing(content_id):
        raise LookupError(content_id)

    with pytest.raises(KeyError, match="L0 content not found"):
        L0ContentProvider(missing).get("42")


@pytest.mark.parametrize("content_id", ["demo-article", "0", "-1", "1.5", "", "true", "４２"])
def test_invalid_l0_ids_fail_before_query(content_id):
    def unexpected_query(_):
        pytest.fail("invalid ID reached L0")

    with pytest.raises(ValueError, match="positive decimal integer"):
        L0ContentProvider(unexpected_query).get(content_id)


def test_nullable_title_does_not_discard_body():
    result = L0ContentProvider(lambda _: l0_content(title=None)).get("42")
    assert result.title == ""
    assert result.normalized_text() == result.body


def test_empty_trend_content_fails_explicitly():
    with pytest.raises(ValueError, match="TREND"):
        L0ContentProvider(lambda _: l0_content(clean_text=" ", status="TREND")).get("42")


def test_mismatched_query_id_is_rejected():
    with pytest.raises(ValueError, match="different content_id"):
        L0ContentProvider(lambda _: l0_content(id=99)).get("42")


def test_storage_failure_propagates_without_fixture_fallback():
    def unavailable(_):
        raise OSError("object storage unavailable")

    with pytest.raises(OSError, match="object storage unavailable"):
        L0ContentProvider(unavailable).get("42")

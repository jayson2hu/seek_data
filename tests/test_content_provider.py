from l1_data_processing.input import StubContentProvider


def test_stub_content_provider_loads_fixture() -> None:
    content = StubContentProvider().get("demo-article")

    assert content.content_id == "demo-article"
    assert content.title
    assert "without L0" in content.body

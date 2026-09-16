import pytest

pytest.importorskip("core_data", reason="Install sibling deepdata to exercise the real L0 pipeline")

from l1_data_processing.l0_smoke import run_l0_integration_checks


def test_real_l0_ingestion_to_l1_enrichment_and_duplicate_delivery():
    assert run_l0_integration_checks() == [
        "L0 ingestion", "stored content", "integer event", "L1 analysis", "duplicate delivery", "L0 read-only",
    ]

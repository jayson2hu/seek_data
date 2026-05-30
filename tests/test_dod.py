from l1_data_processing.dod import run_dod_checks


def test_dod_checks_cover_core_l1_acceptance() -> None:
    checks = run_dod_checks()

    assert checks == ["standalone pipeline", "cache hit", "reprocess", "filter cancel", "long content"]

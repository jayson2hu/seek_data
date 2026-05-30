from __future__ import annotations

from l1_data_processing.dod import run_dod_checks


def main() -> None:
    checks = run_dod_checks()
    print(f"L1 PIPELINE: PASS checks={','.join(checks)}")


if __name__ == "__main__":
    main()

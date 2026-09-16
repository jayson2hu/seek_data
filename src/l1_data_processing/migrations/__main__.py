from __future__ import annotations

import argparse

from sqlalchemy import create_engine

from l1_data_processing.migrations import downgrade, upgrade


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate only L1-owned SQL tables")
    parser.add_argument("direction", choices=["upgrade", "downgrade"])
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    engine = create_engine(args.database_url)
    try:
        (upgrade if args.direction == "upgrade" else downgrade)(engine)
    finally:
        engine.dispose()
    print(f"L1 MIGRATIONS: {args.direction} PASS")


if __name__ == "__main__":
    main()

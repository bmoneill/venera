"""Command-line utility to (re)build the SQLite municipality gazetteer.

Run with ``python -m backend.scripts.build_municipalities_db`` from the
``venera`` project root to regenerate ``backend/data/municipalities.db``
from the canonical ``backend/data/municipalities.csv`` source.
"""

from .. import geodata


def main() -> None:
    """Rebuild the SQLite gazetteer database from the CSV source."""
    count = geodata.build_sqlite_from_csv()
    print(
        f"Wrote {count} municipalities to {geodata.DEFAULT_SQLITE_PATH} "
        f"(table '{geodata.DEFAULT_TABLE_NAME}')."
    )


if __name__ == "__main__":
    main()

"""Command-line utility to (re)seed the municipalities table.

Run with ``python -m backend.scripts.build_municipalities_db`` from the
``venera`` project root to (re)populate the ``municipalities`` table in the
application database from the canonical ``backend/data/municipalities.csv``
source. Any existing rows are replaced.
"""

from .. import geodata
from ..database import SessionLocal
from ..models import Municipality


def main() -> None:
    """Rebuild the ``municipalities`` table from the CSV source."""
    session = SessionLocal()
    try:
        session.query(Municipality).delete()
        session.commit()
        count = geodata.seed_municipalities_from_csv(session)
    finally:
        session.close()
    print(f"Wrote {count} municipalities to the application database.")


if __name__ == "__main__":
    main()

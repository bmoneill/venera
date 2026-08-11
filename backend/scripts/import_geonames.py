"""Command-line entry point for importing the GeoNames gazetteer.

This is a one-off/occasional operator tool, *not* something the running
application imports or executes automatically -- ``allCountries.txt`` is
~1.5+ GB and far too large to bundle into the Docker image or run on
every startup. Run this script once (locally, or against a deployed
database) whenever you want to (re-)populate the ``municipalities``
table from a fresh GeoNames dump.

Example:
    Download ``allCountries.zip`` and ``admin1CodesASCII.txt`` from
    https://download.geonames.org/export/dump/, unzip
    ``allCountries.txt``, then run::

        python -m backend.scripts.import_geonames \\
            --all-countries /path/to/allCountries.txt \\
            --admin1-codes /path/to/admin1CodesASCII.txt \\
            --replace

    By default this imports into whatever ``DATABASE_URL`` the backend
    is configured with (same environment variable read by
    :mod:`backend.database`).
"""

import argparse
import sys
import time

from ..database import Base, engine
from ..geonames_import import DEFAULT_BATCH_SIZE, import_geonames


def _format_elapsed(seconds: float) -> str:
    """Return ``seconds`` formatted as ``"Xm Ys"``."""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s"


def main(argv: "list[str] | None" = None) -> int:
    """Parse arguments and run the GeoNames import.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (``0`` on success).
    """
    parser = argparse.ArgumentParser(
        description="Import the GeoNames gazetteer into Venera's municipalities table."
    )
    parser.add_argument(
        "--all-countries",
        required=True,
        help="Path to GeoNames' allCountries.txt",
    )
    parser.add_argument(
        "--admin1-codes",
        required=True,
        help="Path to GeoNames' admin1CodesASCII.txt",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per INSERT statement (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete any existing municipalities rows before importing "
        "(without this flag, the import is skipped if the table is "
        "already populated).",
    )
    args = parser.parse_args(argv)

    # Ensure the schema (including any new columns/indexes) exists before
    # importing -- a no-op for an already up-to-date database.
    Base.metadata.create_all(bind=engine)

    print(f"Importing from {args.all_countries} ...")
    started_at = time.monotonic()
    last_reported = 0

    def report_progress(processed: int) -> None:
        nonlocal last_reported
        last_reported = processed
        elapsed = _format_elapsed(time.monotonic() - started_at)
        print(f"  ... {processed:,} rows processed ({elapsed} elapsed)")

    inserted = import_geonames(
        engine,
        args.all_countries,
        args.admin1_codes,
        batch_size=args.batch_size,
        replace_existing=args.replace,
        on_progress=report_progress,
    )

    elapsed = _format_elapsed(time.monotonic() - started_at)
    if inserted == 0 and last_reported == 0:
        print(
            "Table already contains municipalities; skipped import "
            "(use --replace to overwrite)."
        )
    else:
        print(f"Done: inserted {inserted:,} municipalities in {elapsed}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Streaming importer for the GeoNames ``allCountries.txt`` gazetteer.

GeoNames (https://www.geonames.org/) publishes a free, worldwide
gazetteer as two plain-text, tab-separated files:

* ``allCountries.txt`` -- every named geographical feature GeoNames
  knows about (tens of millions of rows, ~1.5+ GB uncompressed). Each
  row has a "feature class"; populated places (cities, towns, villages)
  use feature class ``"P"``.
* ``admin1CodesASCII.txt`` -- a small lookup table mapping
  ``"<country code>.<admin1 code>"`` (e.g. ``"US.NY"``) to the name of
  that first-level administrative division (state/province/region).

This module streams ``allCountries.txt`` line-by-line -- it never reads
the file into memory -- filters it down to populated places, joins in
the admin1 region name and full country name, and bulk-inserts the
result into the application's ``municipalities`` table (see
:mod:`backend.models`) using batched, low-overhead SQLAlchemy Core
``INSERT`` statements (not the ORM, which is far slower for millions of
rows).

See ``backend/scripts/import_geonames.py`` for the command-line entry
point.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from .countries import country_name
from .geodata import fold_ascii
from .models import Municipality as MunicipalityRow

#: GeoNames feature codes (all feature class "P") that are excluded by
#: default: "sections" of a populated place (basically neighborhoods,
#: not independently-locatable places), sub-city/village localities too
#: minor to be a useful search result, and abandoned/historical places.
DEFAULT_EXCLUDED_FEATURE_CODES: frozenset[str] = frozenset({"PPLX", "PPLL", "PPLQ"})

#: Number of rows buffered in memory before each bulk ``INSERT``.
DEFAULT_BATCH_SIZE: int = 20_000

# Column indices within a tab-separated allCountries.txt row. See
# https://download.geonames.org/export/dump/readme.txt for the full spec.
_COL_NAME = 1
_COL_ASCIINAME = 2
_COL_LATITUDE = 4
_COL_LONGITUDE = 5
_COL_FEATURE_CLASS = 6
_COL_FEATURE_CODE = 7
_COL_COUNTRY_CODE = 8
_COL_ADMIN1_CODE = 10
_COL_POPULATION = 14
_MIN_COLUMNS = 15

_POPULATED_PLACE_FEATURE_CLASS = "P"


@dataclass(frozen=True)
class GeonamesRow:
    """A single populated place parsed from ``allCountries.txt``."""

    name: str
    territory: str
    country: str
    latitude: float
    longitude: float
    population: int


def load_admin1_names(path: "str | Path") -> dict[str, str]:
    """Parse ``admin1CodesASCII.txt`` into a ``code -> name`` lookup.

    This file is small (a few thousand rows) so it is loaded in full;
    only ``allCountries.txt`` requires streaming.

    Args:
        path: Path to ``admin1CodesASCII.txt``.

    Returns:
        A dict mapping ``"<country code>.<admin1 code>"`` (e.g.
        ``"US.NY"``) to the region's name (e.g. ``"New York"``).
    """
    names: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            code, name = parts[0], parts[1]
            names[code] = name
    return names


def iter_populated_places(
    all_countries_path: "str | Path",
    admin1_names: dict[str, str],
    exclude_feature_codes: frozenset[str] = DEFAULT_EXCLUDED_FEATURE_CODES,
) -> Iterator[GeonamesRow]:
    """Stream populated places out of ``allCountries.txt``.

    Reads the file one line at a time (constant memory use regardless of
    file size), filtering to rows with feature class ``"P"`` and
    excluding any feature code in ``exclude_feature_codes``.

    Args:
        all_countries_path: Path to GeoNames' ``allCountries.txt``.
        admin1_names: The ``code -> name`` map from
            :func:`load_admin1_names`, used to resolve each row's
            territory (state/province/region) name.
        exclude_feature_codes: Feature codes to skip even though they
            share feature class ``"P"`` (see
            :data:`DEFAULT_EXCLUDED_FEATURE_CODES`).

    Yields:
        One :class:`GeonamesRow` per qualifying line, in file order.
        Malformed lines (too few columns, non-numeric lat/lon/population)
        are silently skipped.
    """
    with open(all_countries_path, "r", encoding="utf-8") as fh:
        for line in fh:
            columns = line.rstrip("\n").split("\t")
            if len(columns) < _MIN_COLUMNS:
                continue
            if columns[_COL_FEATURE_CLASS] != _POPULATED_PLACE_FEATURE_CLASS:
                continue
            if columns[_COL_FEATURE_CODE] in exclude_feature_codes:
                continue

            name = columns[_COL_NAME].strip()
            if not name:
                continue

            country_code = columns[_COL_COUNTRY_CODE].strip()
            admin1_code = columns[_COL_ADMIN1_CODE].strip()

            territory = None
            if admin1_code:
                territory = admin1_names.get(f"{country_code}.{admin1_code}")
            if not territory:
                territory = admin1_code or country_name(country_code)

            try:
                latitude = float(columns[_COL_LATITUDE])
                longitude = float(columns[_COL_LONGITUDE])
            except ValueError:
                continue

            try:
                population = int(columns[_COL_POPULATION] or 0)
            except ValueError:
                population = 0

            yield GeonamesRow(
                name=name,
                territory=territory,
                country=country_name(country_code),
                latitude=latitude,
                longitude=longitude,
                population=population,
            )


def _to_row_mapping(row: GeonamesRow) -> dict:
    """Convert a :class:`GeonamesRow` into a ``municipalities`` row mapping."""
    return {
        "name": row.name,
        "search_name": fold_ascii(row.name),
        "territory": row.territory,
        "country": row.country,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "population": row.population,
    }


def _batched(rows: Iterable[GeonamesRow], batch_size: int) -> Iterator[list[dict]]:
    """Group an iterable of :class:`GeonamesRow` into row-mapping batches."""
    batch: list[dict] = []
    for row in rows:
        batch.append(_to_row_mapping(row))
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def import_geonames(
    engine: Engine,
    all_countries_path: "str | Path",
    admin1_codes_path: "str | Path",
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    exclude_feature_codes: frozenset[str] = DEFAULT_EXCLUDED_FEATURE_CODES,
    replace_existing: bool = False,
    progress_every: int = 500_000,
    on_progress: Optional[Callable[[int], None]] = None,
) -> int:
    """Import GeoNames populated places into the ``municipalities`` table.

    Streams ``allCountries.txt`` (never loading it fully into memory),
    filters it down to populated places, and bulk-inserts the result in
    batches within a single transaction for speed. Uses SQLAlchemy Core
    (not the ORM) since ORM object construction is far too slow for a
    multi-million-row import.

    Args:
        engine: The SQLAlchemy engine to import into.
        all_countries_path: Path to GeoNames' ``allCountries.txt``.
        admin1_codes_path: Path to GeoNames' ``admin1CodesASCII.txt``.
        batch_size: Number of rows per ``INSERT`` statement.
        exclude_feature_codes: Populated-place feature codes to skip
            (see :data:`DEFAULT_EXCLUDED_FEATURE_CODES`).
        replace_existing: If ``True``, delete all existing
            ``municipalities`` rows before importing. If ``False``
            (default) and the table is already populated, the import is
            skipped entirely (mirrors
            :func:`backend.geodata.seed_municipalities_from_csv`'s
            no-op-when-seeded behavior).
        progress_every: Log a progress update via ``on_progress`` every
            this many rows processed.
        on_progress: Optional callback invoked with the running count of
            rows *processed* (not necessarily inserted) every
            ``progress_every`` rows, for progress reporting in a CLI.

    Returns:
        The number of rows inserted (``0`` if the table was already
        populated and ``replace_existing`` is ``False``).
    """
    table = MunicipalityRow.__table__

    with engine.connect() as connection:
        # SQLite-specific speed tuning for the duration of this bulk
        # import. Must run before any transaction is opened (SQLite
        # refuses to change these mid-transaction), and is safe here
        # because the whole import runs as a single transaction: a crash
        # mid-import simply loses the transaction, rather than
        # corrupting data.
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA synchronous = OFF")
            connection.exec_driver_sql("PRAGMA journal_mode = MEMORY")
            connection.commit()

        with connection.begin():
            already_seeded = (
                connection.execute(table.select().limit(1)).first() is not None
            )
            if already_seeded:
                if not replace_existing:
                    return 0
                connection.execute(table.delete())

            admin1_names = load_admin1_names(admin1_codes_path)
            rows = iter_populated_places(
                all_countries_path, admin1_names, exclude_feature_codes
            )

            insert_stmt = insert(table)
            total_inserted = 0
            total_processed = 0
            next_progress_at = progress_every

            for batch in _batched(rows, batch_size):
                connection.execute(insert_stmt, batch)
                total_inserted += len(batch)
                total_processed += len(batch)
                if on_progress is not None and total_processed >= next_progress_at:
                    on_progress(total_processed)
                    next_progress_at += progress_every

            if on_progress is not None:
                on_progress(total_processed)

    return total_inserted

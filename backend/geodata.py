"""Static municipality gazetteer used to resolve an observer's location.

This module provides a small, self-contained "geocoder" backed entirely by
static data bundled with the application (no network access or third-party
geocoding service is used). A municipality is described by its name,
territory (state/province/region), country, and latitude/longitude in
decimal degrees.

Two interchangeable storage formats are supported:

* A CSV file (see ``backend/data/municipalities.csv``), the canonical
  source of truth.
* A SQLite database (see ``backend/data/municipalities.db``), which can be
  generated from the CSV via :func:`build_sqlite_from_csv` and is useful
  when a queryable on-disk format is preferred over parsing a flat file
  on every startup.

The active source is selected at runtime via the ``MUNICIPALITY_SOURCE``
environment variable (``"csv"`` or ``"sqlite"``, defaulting to ``"csv"``).
"""

import csv
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

_DATA_DIR: Path = Path(__file__).resolve().parent / "data"
DEFAULT_CSV_PATH: Path = _DATA_DIR / "municipalities.csv"
DEFAULT_SQLITE_PATH: Path = _DATA_DIR / "municipalities.db"
DEFAULT_TABLE_NAME: str = "municipalities"

_CSV_FIELDS: tuple[str, ...] = ("name", "territory", "country", "latitude", "longitude")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Matches "<lat>, <lon>" or "<lat> <lon>", e.g. "48.8566, 2.3522" or
# "-33.8688 151.2093". Accepts an optional leading sign and decimals.
_LAT_LON_RE = re.compile(
    r"^\s*(?P<lat>[+-]?\d+(?:\.\d+)?)\s*[, ]\s*(?P<lon>[+-]?\d+(?:\.\d+)?)\s*$"
)

_KM_PER_LIGHT_YEAR: float = 9_460_730_472_580.8


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LocationError(Exception):
    """Base class for all coordinate/municipality resolution failures."""


class InvalidCoordinatesError(LocationError):
    """Raised when a raw ``lat, lon`` string is malformed or out of range."""


class MunicipalityNotFoundError(LocationError):
    """Raised when no municipality matches the requested query."""


class AmbiguousMunicipalityError(LocationError):
    """Raised when more than one municipality matches an unqualified query."""

    def __init__(self, matches: list["Municipality"]) -> None:
        """Store the ambiguous matches and build a human-readable message.

        Args:
            matches: The set of municipalities that all matched the query.
        """
        self.matches = matches
        options = "; ".join(m.label for m in matches)
        super().__init__(
            f"Multiple municipalities match this query: {options}. "
            "Add a territory and/or country to disambiguate."
        )


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Municipality:
    """A single municipality entry from the gazetteer.

    Attributes:
        name: The municipality's common name (e.g. ``"Paris"``).
        territory: The state, province, or region it belongs to.
        country: The country it belongs to.
        latitude: Latitude in decimal degrees (positive is north).
        longitude: Longitude in decimal degrees (positive is east).
    """

    name: str
    territory: str
    country: str
    latitude: float
    longitude: float

    @property
    def label(self) -> str:
        """Return a human-readable ``"name, territory, country"`` label."""
        return f"{self.name}, {self.territory}, {self.country}"


@dataclass(frozen=True)
class ResolvedLocation:
    """The outcome of resolving a user-supplied coordinates string.

    Attributes:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        label: A human-readable description of the resolved location.
    """

    latitude: float
    longitude: float
    label: str


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def load_from_csv(path: "str | Path" = DEFAULT_CSV_PATH) -> list[Municipality]:
    """Parse a municipality gazetteer from a CSV file.

    The CSV must contain a header row with (at least) the columns
    ``name, territory, country, latitude, longitude``. Extra columns are
    ignored, and column order does not matter.

    Args:
        path: Path to the CSV file.

    Returns:
        A list of :class:`Municipality` instances, in file order.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the header is missing required columns, or a row
            contains a non-numeric latitude/longitude.
    """
    path = Path(path)
    municipalities: list[Municipality] = []

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = set(_CSV_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                f"CSV {path} is missing required column(s): {', '.join(sorted(missing))}"
            )

        for line_no, row in enumerate(reader, start=2):
            name = (row.get("name") or "").strip()
            territory = (row.get("territory") or "").strip()
            country = (row.get("country") or "").strip()
            if not name or not country:
                raise ValueError(
                    f"Malformed row {line_no} in {path}: name/country required"
                )
            try:
                latitude = float(row["latitude"])
                longitude = float(row["longitude"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Malformed row {line_no} in {path}: invalid latitude/longitude"
                ) from exc

            municipalities.append(
                Municipality(
                    name=name,
                    territory=territory,
                    country=country,
                    latitude=latitude,
                    longitude=longitude,
                )
            )

    return municipalities


# ---------------------------------------------------------------------------
# SQLite parsing
# ---------------------------------------------------------------------------


def _validate_identifier(identifier: str) -> str:
    """Validate that ``identifier`` is safe to interpolate into raw SQL.

    Args:
        identifier: The candidate SQL identifier (e.g. a table name).

    Returns:
        The identifier unchanged, if valid.

    Raises:
        ValueError: If the identifier is not a simple alphanumeric/underscore
            token (i.e. it could not plausibly be a legitimate table name).
    """
    if not _IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier!r}")
    return identifier


def load_from_sqlite(
    path: "str | Path" = DEFAULT_SQLITE_PATH,
    table: str = DEFAULT_TABLE_NAME,
) -> list[Municipality]:
    """Parse a municipality gazetteer from a SQLite database.

    The table must have (at least) the columns
    ``name, territory, country, latitude, longitude``.

    Args:
        path: Path to the SQLite database file.
        table: Name of the table containing municipality rows.

    Returns:
        A list of :class:`Municipality` instances, in row order.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If ``table`` is not a valid SQL identifier.
        sqlite3.Error: If the query fails (e.g. the table does not exist).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite database not found: {path}")
    table = _validate_identifier(table)

    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            f"SELECT name, territory, country, latitude, longitude FROM {table}"  # noqa: S608
        )
        return [
            Municipality(
                name=row["name"],
                territory=row["territory"],
                country=row["country"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
            for row in cursor.fetchall()
        ]


def build_sqlite_from_csv(
    csv_path: "str | Path" = DEFAULT_CSV_PATH,
    sqlite_path: "str | Path" = DEFAULT_SQLITE_PATH,
    table: str = DEFAULT_TABLE_NAME,
) -> int:
    """Build (or rebuild) a SQLite gazetteer database from a CSV source.

    This lets the same static dataset be served from either storage
    format: the CSV is the canonical source, and this function produces an
    equivalent SQLite database for deployments that prefer querying a
    database file.

    Args:
        csv_path: Path to the source CSV file.
        sqlite_path: Path where the SQLite database should be written. Any
            existing file at this path is replaced.
        table: Name of the table to create.

    Returns:
        The number of municipality rows written.
    """
    table = _validate_identifier(table)
    municipalities = load_from_csv(csv_path)

    sqlite_path = Path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        sqlite_path.unlink()

    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.execute(
            f"CREATE TABLE {table} ("  # noqa: S608
            "name TEXT NOT NULL, "
            "territory TEXT NOT NULL, "
            "country TEXT NOT NULL, "
            "latitude REAL NOT NULL, "
            "longitude REAL NOT NULL"
            ")"
        )
        conn.executemany(
            f"INSERT INTO {table} (name, territory, country, latitude, longitude) "  # noqa: S608
            "VALUES (?, ?, ?, ?, ?)",
            [
                (m.name, m.territory, m.country, m.latitude, m.longitude)
                for m in municipalities
            ],
        )
        conn.commit()

    return len(municipalities)


# ---------------------------------------------------------------------------
# In-memory lookup index
# ---------------------------------------------------------------------------


class MunicipalityGazetteer:
    """Case-insensitive, in-memory index over a list of municipalities."""

    def __init__(self, municipalities: Iterable[Municipality]) -> None:
        """Build the lookup index.

        Args:
            municipalities: The municipalities to index, in any order.
        """
        self._all: list[Municipality] = list(municipalities)
        self._by_name: dict[str, list[Municipality]] = {}
        for municipality in self._all:
            key = municipality.name.strip().lower()
            self._by_name.setdefault(key, []).append(municipality)

    @classmethod
    def from_csv(cls, path: "str | Path" = DEFAULT_CSV_PATH) -> "MunicipalityGazetteer":
        """Build a gazetteer by parsing a CSV file."""
        return cls(load_from_csv(path))

    @classmethod
    def from_sqlite(
        cls,
        path: "str | Path" = DEFAULT_SQLITE_PATH,
        table: str = DEFAULT_TABLE_NAME,
    ) -> "MunicipalityGazetteer":
        """Build a gazetteer by querying a SQLite database."""
        return cls(load_from_sqlite(path, table))

    def find(
        self,
        name: str,
        territory: Optional[str] = None,
        country: Optional[str] = None,
    ) -> list[Municipality]:
        """Look up municipalities by name, optionally filtered further.

        Args:
            name: Municipality name (case-insensitive, exact match).
            territory: If given, restrict matches to this territory
                (case-insensitive, exact match).
            country: If given, restrict matches to this country
                (case-insensitive, exact match).

        Returns:
            All municipalities matching the given criteria, in dataset
            order. Empty if none match.
        """
        candidates = list(self._by_name.get(name.strip().lower(), ()))
        if territory:
            wanted = territory.strip().lower()
            candidates = [m for m in candidates if m.territory.lower() == wanted]
        if country:
            wanted = country.strip().lower()
            candidates = [m for m in candidates if m.country.lower() == wanted]
        return candidates

    def suggest(self, prefix: str, limit: int = 10) -> list[Municipality]:
        """Return municipalities whose name starts with ``prefix``.

        Intended for text-completion in a search-as-you-type UI (e.g. a
        municipality dropdown). Matching is case-insensitive and based on
        the municipality's ``name`` only (not its territory or country).

        Args:
            prefix: The partial municipality name typed by the user. A
                blank/whitespace-only prefix yields no suggestions.
            limit: Maximum number of suggestions to return.

        Returns:
            Matching municipalities, sorted by name, then territory, then
            country, truncated to ``limit`` entries. Empty if ``prefix``
            is blank or nothing matches.
        """
        text = prefix.strip().lower()
        if not text:
            return []
        matches = [m for m in self._all if m.name.lower().startswith(text)]
        matches.sort(key=lambda m: (m.name, m.territory, m.country))
        return matches[:limit]

    def __len__(self) -> int:
        return len(self._all)


# ---------------------------------------------------------------------------
# Coordinate parsing and resolution
# ---------------------------------------------------------------------------


def try_parse_lat_lon(text: str) -> Optional[tuple[float, float]]:
    """Attempt to parse ``text`` as a raw ``"lat, lon"`` coordinate pair.

    Args:
        text: The candidate coordinate string.

    Returns:
        A ``(latitude, longitude)`` tuple if ``text`` matches the expected
        numeric pattern, or ``None`` if it does not look like coordinates
        at all (in which case the caller should try a municipality lookup
        instead).

    Raises:
        InvalidCoordinatesError: If ``text`` looks like a coordinate pair
            but the values are out of the valid latitude/longitude range.
    """
    match = _LAT_LON_RE.match(text)
    if match is None:
        return None

    lat = float(match.group("lat"))
    lon = float(match.group("lon"))
    if not -90.0 <= lat <= 90.0:
        raise InvalidCoordinatesError(f"Latitude {lat} is out of range (-90 to 90).")
    if not -180.0 <= lon <= 180.0:
        raise InvalidCoordinatesError(f"Longitude {lon} is out of range (-180 to 180).")
    return lat, lon


def resolve_coordinates(
    coordinates: str, gazetteer: MunicipalityGazetteer
) -> ResolvedLocation:
    """Resolve a user-supplied ``coordinates`` search parameter.

    Accepts either:

    * Raw decimal coordinates, e.g. ``"48.8566, 2.3522"``.
    * A municipality name, e.g. ``"Paris"``.
    * A municipality name with a country, e.g. ``"Paris, France"``.
    * A municipality name with a territory and country, e.g.
      ``"Paris, Texas, United States"``.

    Args:
        coordinates: The raw value of the ``coordinates`` query parameter.
        gazetteer: The municipality index to search when ``coordinates``
            is not a raw lat/lon pair.

    Returns:
        A :class:`ResolvedLocation` with the latitude, longitude, and a
        human-readable label describing the resolved location.

    Raises:
        InvalidCoordinatesError: If ``coordinates`` is empty, or looks
            like a lat/lon pair but is out of range.
        MunicipalityNotFoundError: If no municipality matches the query.
        AmbiguousMunicipalityError: If more than one municipality matches
            an under-specified query (e.g. name only, when multiple
            municipalities share that name).
    """
    text = coordinates.strip()
    if not text:
        raise InvalidCoordinatesError("Coordinates must not be empty.")

    lat_lon = try_parse_lat_lon(text)
    if lat_lon is not None:
        lat, lon = lat_lon
        return ResolvedLocation(
            latitude=lat, longitude=lon, label=f"{lat:.4f}, {lon:.4f}"
        )

    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        raise InvalidCoordinatesError("Coordinates must not be empty.")

    name = parts[0]
    territory = parts[1] if len(parts) >= 3 else None
    country = parts[-1] if len(parts) >= 2 else None

    matches = gazetteer.find(name, territory=territory, country=country)
    if not matches:
        raise MunicipalityNotFoundError(
            f"No municipality found matching '{coordinates}'."
        )
    if len(matches) > 1:
        raise AmbiguousMunicipalityError(matches)

    municipality = matches[0]
    return ResolvedLocation(
        latitude=municipality.latitude,
        longitude=municipality.longitude,
        label=municipality.label,
    )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_gazetteer: Optional[MunicipalityGazetteer] = None


def get_gazetteer() -> MunicipalityGazetteer:
    """Return the process-wide :class:`MunicipalityGazetteer`, loading it on first use.

    The data source is chosen via the ``MUNICIPALITY_SOURCE`` environment
    variable (``"csv"`` or ``"sqlite"``, defaulting to ``"csv"``), with the
    file path overridable via ``MUNICIPALITIES_CSV_PATH`` /
    ``MUNICIPALITIES_DB_PATH``.

    Returns:
        The shared :class:`MunicipalityGazetteer` instance.
    """
    global _gazetteer
    if _gazetteer is None:
        source = os.getenv("MUNICIPALITY_SOURCE", "csv").strip().lower()
        if source == "sqlite":
            db_path = os.getenv("MUNICIPALITIES_DB_PATH", str(DEFAULT_SQLITE_PATH))
            _gazetteer = MunicipalityGazetteer.from_sqlite(db_path)
        else:
            csv_path = os.getenv("MUNICIPALITIES_CSV_PATH", str(DEFAULT_CSV_PATH))
            _gazetteer = MunicipalityGazetteer.from_csv(csv_path)
    return _gazetteer


def reset_gazetteer_cache() -> None:
    """Clear the cached gazetteer singleton (primarily for use in tests)."""
    global _gazetteer
    _gazetteer = None


def light_years_to_km(distance_ly: float) -> float:
    """Convert a distance in light-years to kilometers.

    Args:
        distance_ly: Distance in light-years.

    Returns:
        The equivalent distance in kilometers.
    """
    return distance_ly * _KM_PER_LIGHT_YEAR

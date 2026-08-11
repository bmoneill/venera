"""Static municipality gazetteer used to resolve an observer's location.

This module provides a small, self-contained "geocoder" backed entirely by
static data (no network access or third-party geocoding service is used).
A municipality is described by its name, territory (state/province/region),
country, and latitude/longitude in decimal degrees.

Municipality locations are persisted in the application's SQLAlchemy-managed
database (see :mod:`backend.models`), which is seeded on first use from the
bundled CSV source (``backend/data/municipalities.csv``) via
:func:`seed_municipalities_from_csv`.
"""

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Municipality as MunicipalityRow

_DATA_DIR: Path = Path(__file__).resolve().parent / "data"
DEFAULT_CSV_PATH: Path = _DATA_DIR / "municipalities.csv"

_CSV_FIELDS: tuple[str, ...] = ("name", "territory", "country", "latitude", "longitude")

# Matches "<lat>, <lon>" or "<lat> <lon>", e.g. "48.8566, 2.3522" or
# "-33.8688 151.2093". Accepts an optional leading sign and decimals.
_LAT_LON_RE = re.compile(
    r"^\s*(?P<lat>[+-]?\d+(?:\.\d+)?)\s*[, ]\s*(?P<lon>[+-]?\d+(?:\.\d+)?)\s*$"
)

_KM_PER_LIGHT_YEAR: float = 9_460_730_472_580.8

#: Cap on how many candidate matches an :class:`AmbiguousMunicipalityError`
#: message will list by name -- with the full GeoNames gazetteer imported,
#: a common name (e.g. "San Jose") can match hundreds of tiny places
#: worldwide, so the message is truncated for readability.
_MAX_LISTED_AMBIGUOUS_MATCHES: int = 10


def fold_ascii(text: str) -> str:
    """Lower-case ``text`` and strip Latin diacritics, for fuzzy matching.

    Used to build/query the ``search_name`` column so that, e.g., a user
    typing "Sao Paulo" or "sao paulo" still matches a municipality stored
    as "São Paulo". This only folds *combining* diacritics on Latin
    characters (e.g. é -> e); it does not transliterate other scripts
    (Cyrillic, CJK, Arabic, etc.) -- for those, matching relies on
    GeoNames' own precomputed ASCII name (see :mod:`backend.geonames_import`).

    Args:
        text: Arbitrary text (a municipality name or a user's query).

    Returns:
        The lower-cased, diacritic-stripped text.
    """
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _prefix_upper_bound(text: str) -> Optional[str]:
    """Return the smallest string that sorts after every string starting with ``text``.

    Used to turn a prefix search into a plain ``>=``/``<`` range
    condition, e.g. "lon" -> "loo", so that
    ``search_name >= "lon" AND search_name < "loo"`` matches exactly the
    strings starting with "lon".

    Args:
        text: A non-empty prefix string.

    Returns:
        The upper bound string, or ``None`` if ``text``'s last character
        is already the maximum representable code point (in which case
        the caller should apply only the ``>=`` half of the range).
    """
    if not text:
        return None
    last_codepoint = ord(text[-1])
    if last_codepoint >= 0x10FFFF:
        return None
    return text[:-1] + chr(last_codepoint + 1)


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
        shown = matches[:_MAX_LISTED_AMBIGUOUS_MATCHES]
        options = "; ".join(m.label for m in shown)
        remaining = len(matches) - len(shown)
        if remaining > 0:
            options += f"; and {remaining} more"
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
# Database-backed persistence
# ---------------------------------------------------------------------------


def load_from_db(session: Session) -> list[Municipality]:
    """Load all municipalities from the application database.

    Args:
        session: An active SQLAlchemy session.

    Returns:
        A list of :class:`Municipality` instances, ordered by primary key.
    """
    rows = session.query(MunicipalityRow).order_by(MunicipalityRow.id).all()
    return [
        Municipality(
            name=row.name,
            territory=row.territory,
            country=row.country,
            latitude=row.latitude,
            longitude=row.longitude,
        )
        for row in rows
    ]


def seed_municipalities_from_csv(
    session: Session, csv_path: "str | Path" = DEFAULT_CSV_PATH
) -> int:
    """Populate the ``municipalities`` table from the CSV source.

    This is a no-op if the table is already populated, so it is safe to
    call unconditionally at application startup.

    Args:
        session: An active SQLAlchemy session.
        csv_path: Path to the CSV file to seed from.

    Returns:
        The number of municipality rows inserted (``0`` if the table was
        already populated).
    """
    already_seeded = session.query(MunicipalityRow.id).first() is not None
    if already_seeded:
        return 0

    municipalities = load_from_csv(csv_path)
    session.bulk_save_objects(
        [
            MunicipalityRow(
                name=m.name,
                territory=m.territory,
                country=m.country,
                latitude=m.latitude,
                longitude=m.longitude,
                search_name=fold_ascii(m.name),
                population=0,
            )
            for m in municipalities
        ]
    )
    session.commit()
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
    def from_db(cls, session: Session) -> "MunicipalityGazetteer":
        """Build a gazetteer by querying the application database."""
        return cls(load_from_db(session))

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
# SQL-backed lookup index (for large, e.g. GeoNames-scale, datasets)
# ---------------------------------------------------------------------------


class SqlMunicipalityGazetteer:
    """Municipality index backed directly by indexed SQL queries.

    Unlike :class:`MunicipalityGazetteer`, this class never materializes
    the full municipality table in Python memory or performs an
    in-memory linear scan. Instead, every lookup issues one or two
    narrowly-scoped SQL queries against indexed columns -- see
    :meth:`suggest` for why it uses two queries instead of one.

    This is what makes text-completion remain fast even when the
    ``municipalities`` table holds millions of rows -- e.g. after
    importing the full GeoNames gazetteer via
    :mod:`backend.geonames_import` -- since :class:`MunicipalityGazetteer`
    loading every row into a Python list at startup (and re-scanning that
    list on every keystroke) would not scale to that size.
    """

    #: Safety cap on how many rows an unqualified :meth:`find` query can
    #: return -- a common name can otherwise match hundreds of tiny
    #: places worldwide once the full GeoNames gazetteer is loaded.
    _MAX_FIND_RESULTS = 200

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        """Create a gazetteer that opens a short-lived session per query.

        Args:
            session_factory: A callable returning a new SQLAlchemy
                ``Session`` (defaults to the application's
                ``SessionLocal``). Each call to :meth:`find` or
                :meth:`suggest` opens and closes its own session, so
                this object is safe to share/cache across requests.
        """
        self._session_factory = session_factory

    def find(
        self,
        name: str,
        territory: Optional[str] = None,
        country: Optional[str] = None,
    ) -> list[Municipality]:
        """Look up municipalities by name, optionally filtered further.

        Args:
            name: Municipality name (case/accent-insensitive, exact match).
            territory: If given, restrict matches to this territory
                (case-insensitive, exact match).
            country: If given, restrict matches to this country
                (case-insensitive, exact match).

        Returns:
            Up to :attr:`_MAX_FIND_RESULTS` municipalities matching the
            given criteria. Empty if none match.
        """
        session = self._session_factory()
        try:
            query = session.query(MunicipalityRow).filter(
                MunicipalityRow.search_name == fold_ascii(name.strip())
            )
            if territory:
                query = query.filter(
                    func.lower(MunicipalityRow.territory) == territory.strip().lower()
                )
            if country:
                query = query.filter(
                    func.lower(MunicipalityRow.country) == country.strip().lower()
                )
            rows = query.limit(self._MAX_FIND_RESULTS).all()
            return [_row_to_municipality(row) for row in rows]
        finally:
            session.close()

    def suggest(self, prefix: str, limit: int = 10) -> list[Municipality]:
        """Return municipalities whose name starts with ``prefix``.

        Intended for text-completion in a search-as-you-type UI. Matching
        is case/accent-insensitive and based on the municipality's
        ``name`` only. Results are ranked by population (descending) so
        that well-known places surface first, with ties broken
        alphabetically.

        Implemented as a ``search_name >= prefix AND search_name < upper_bound``
        range condition (rather than ``LIKE 'prefix%'``). This is
        deliberate: SQLite's ``LIKE`` is case-insensitive by default,
        which disables its usual "turn LIKE into an index range scan"
        optimization (a case-sensitive BINARY index can't safely serve a
        case-insensitive comparison) -- so a naive ``LIKE`` query here
        falls back to a full table scan, taking seconds against a
        multi-million-row GeoNames-scale table instead of milliseconds.
        A plain ``>=``/``<`` range always uses the ``search_name`` index.

        The query runs in two phases to avoid a second, subtler
        slow-down: a short, common prefix (e.g. "a" or "san") can match
        tens of thousands of rows, and ranking *those* by population
        would otherwise force SQLite to fetch every matching row from
        the main table just to read its ``population`` -- before it can
        even sort -- which is slow (hundreds of milliseconds or more) at
        GeoNames scale. Instead:

        1. Select just the ``id`` column, filtered/sorted/limited using
           only ``ix_municipalities_suggest_cover`` (a covering index
           over ``search_name``, ``population``, ``name``, ``territory``,
           ``country``) -- so SQLite never touches the main table for
           this step.
        2. Fetch the full rows for just those (at most ``limit``) ids.

        Args:
            prefix: The partial municipality name typed by the user. A
                blank/whitespace-only prefix yields no suggestions.
            limit: Maximum number of suggestions to return.

        Returns:
            Matching municipalities, truncated to ``limit`` entries.
            Empty if ``prefix`` is blank or nothing matches.
        """
        text = fold_ascii(prefix.strip())
        if not text:
            return []

        upper_bound = _prefix_upper_bound(text)

        session = self._session_factory()
        try:
            id_query = session.query(MunicipalityRow.id).filter(
                MunicipalityRow.search_name >= text
            )
            if upper_bound is not None:
                id_query = id_query.filter(MunicipalityRow.search_name < upper_bound)
            ordered_ids = [
                row.id
                for row in id_query.order_by(
                    MunicipalityRow.population.desc(),
                    MunicipalityRow.name,
                    MunicipalityRow.territory,
                    MunicipalityRow.country,
                )
                .limit(limit)
                .all()
            ]
            if not ordered_ids:
                return []

            rows_by_id = {
                row.id: row
                for row in session.query(MunicipalityRow)
                .filter(MunicipalityRow.id.in_(ordered_ids))
                .all()
            }
            return [
                _row_to_municipality(rows_by_id[municipality_id])
                for municipality_id in ordered_ids
                if municipality_id in rows_by_id
                and rows_by_id[municipality_id].search_name.startswith(text)
            ]
        finally:
            session.close()

    def __len__(self) -> int:
        session = self._session_factory()
        try:
            return session.query(func.count(MunicipalityRow.id)).scalar() or 0
        finally:
            session.close()


def _row_to_municipality(row: MunicipalityRow) -> Municipality:
    """Convert a Municipality ORM row to the dataclass."""
    return Municipality(
        name=row.name,
        territory=row.territory,
        country=row.country,
        latitude=row.latitude,
        longitude=row.longitude,
    )


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
    coordinates: str, gazetteer: "MunicipalityGazetteer | SqlMunicipalityGazetteer"
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

_gazetteer: Optional["MunicipalityGazetteer | SqlMunicipalityGazetteer"] = None


def get_gazetteer() -> "MunicipalityGazetteer | SqlMunicipalityGazetteer":
    """Return the process-wide municipality gazetteer, building it on first use.

    Municipality data is read from the application's SQLAlchemy-managed
    database (seeded from ``backend/data/municipalities.csv`` at startup,
    see :func:`seed_municipalities_from_csv`, or, for production-scale
    deployments, from the full GeoNames gazetteer, see
    :mod:`backend.geonames_import`).

    The returned gazetteer is always a :class:`SqlMunicipalityGazetteer`,
    which queries the database directly (via indexed columns) rather
    than loading every row into memory, so lookups stay fast regardless
    of how many municipalities are in the table.

    Returns:
        The shared gazetteer instance.
    """
    global _gazetteer
    if _gazetteer is None:
        _gazetteer = SqlMunicipalityGazetteer()
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

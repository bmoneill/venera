"""SQLAlchemy ORM models for the Venera application database.

The application database contains exactly one kind of persisted data:
municipality locations (used to resolve an observer's coordinates from a
place name — see :mod:`backend.geodata`).
"""

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Municipality(Base):
    """A single municipality location (name, territory, country, lat/long).

    ``search_name`` is a lower-cased, ASCII-folded copy of ``name`` used
    exclusively for fast, case/accent-insensitive lookups (see
    :class:`backend.geodata.SqlMunicipalityGazetteer`); it is indexed so
    that both exact-match and prefix (``LIKE 'prefix%'``) queries can use
    the index instead of scanning the whole table, which matters once
    this table holds millions of rows (e.g. after importing the full
    GeoNames gazetteer -- see :mod:`backend.scripts.import_geonames`).

    ``population`` is used to rank autocomplete suggestions so that,
    e.g., "Paris, France" is suggested ahead of an obscure hamlet that
    happens to share the same name.

    ``ix_municipalities_suggest_cover`` is a covering index over
    ``(search_name, population, name, territory, country)``. It exists
    purely for :meth:`backend.geodata.SqlMunicipalityGazetteer.suggest`
    performance: without it, ranking the (potentially tens of thousands
    of) rows that share a short prefix by population would force SQLite
    to fetch every matching row from the main table before it can even
    sort, which is slow at GeoNames scale (hundreds of milliseconds to
    seconds). With this index, SQLite can filter, sort, and apply the
    result limit using only the index, touching the main table only for
    the handful of rows actually returned.
    """

    __tablename__ = "municipalities"
    __table_args__ = (
        Index(
            "ix_municipalities_suggest_cover",
            "search_name",
            "population",
            "name",
            "territory",
            "country",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    search_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    territory: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    population: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

"""SQLAlchemy ORM models for the Venera application database.

The application database contains exactly one kind of persisted data:
municipality locations (used to resolve an observer's coordinates from a
place name — see :mod:`backend.geodata`).
"""

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Municipality(Base):
    """A single municipality location (name, territory, country, lat/long)."""

    __tablename__ = "municipalities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    territory: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

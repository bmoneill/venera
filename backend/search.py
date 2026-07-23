"""Search router — look up a celestial object by name and return its coordinates."""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from skyfield.api import wgs84

from . import astronomy
from .auth import get_current_user
from .models import User

# ---------------------------------------------------------------------------
# Solar-system bodies available in de421.bsp, keyed by lowercase display name.
# Value: (BSP target string, human-readable type label)
# ---------------------------------------------------------------------------

SOLAR_SYSTEM_BODIES: dict[str, tuple[str, str]] = {
    "sun": ("sun", "Star"),
    "moon": ("moon", "Natural Satellite"),
    "mercury": ("mercury barycenter", "Planet"),
    "venus": ("venus barycenter", "Planet"),
    "mars": ("mars barycenter", "Planet"),
    "jupiter": ("jupiter barycenter", "Planet"),
    "saturn": ("saturn barycenter", "Planet"),
    "uranus": ("uranus barycenter", "Planet"),
    "neptune": ("neptune barycenter", "Planet"),
    "pluto": ("pluto barycenter", "Dwarf Planet"),
}

# ---------------------------------------------------------------------------
# Curated named-star catalog.
# Keys are lowercase; values are (ra_hours, dec_degrees) in J2000.
# Coordinates are sourced from the Hipparcos catalog.
# ---------------------------------------------------------------------------

NAMED_STARS: dict[str, tuple[float, float]] = {
    "sirius": (6.752477, -16.716114),
    "canopus": (6.399197, -52.695661),
    "arcturus": (14.261020, 19.182408),
    "vega": (18.615649, 38.783689),
    "capella": (5.278155, 45.997992),
    "rigel": (5.242298, -8.201639),
    "procyon": (7.655033, 5.224989),
    "betelgeuse": (5.919529, 7.407064),
    "aldebaran": (4.598677, 16.509303),
    "antares": (16.490128, -26.431947),
    "spica": (13.419883, -11.161319),
    "pollux": (7.755264, 28.026200),
    "fomalhaut": (22.960846, -29.622236),
    "deneb": (20.690532, 45.280339),
    "regulus": (10.139531, 11.967208),
    "polaris": (2.530303, 89.264108),
    "acrux": (12.443304, -63.099092),
    "mimosa": (12.795353, -59.688769),
    "gacrux": (12.519433, -57.113214),
    "hadar": (14.063724, -60.373039),
    "rigil kentaurus": (14.660138, -60.833992),
    "alpha centauri": (14.660138, -60.833992),
    "alioth": (12.900486, 55.959822),
    "dubhe": (11.062131, 61.751033),
    "mirfak": (3.405381, 49.861181),
    "bellatrix": (5.418851, 6.349703),
    "alnilam": (5.603559, -1.201919),
    "alnitak": (5.679313, -1.942572),
    "mintaka": (5.533444, -0.299094),
    "adhara": (6.977100, -28.972089),
    "elnath": (5.438198, 28.607453),
    "castor": (7.576628, 31.888283),
    "peacock": (20.427460, -56.735086),
    "alnair": (22.137217, -46.960975),
    "shaula": (17.560144, -37.103822),
    "miaplacidus": (9.219994, -69.717208),
    "avior": (8.375232, -59.509492),
    "wezen": (7.139856, -26.393208),
    "menkent": (14.111374, -36.369958),
    "atria": (16.811082, -69.027717),
}


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class SearchResult(BaseModel):
    """Equatorial coordinates for a matched celestial object."""

    name: str
    type: str
    ra_hours: float
    dec_degrees: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _search_solar_system(key: str) -> SearchResult:
    """Compute current geocentric RA/Dec for a solar system body.

    Uses the de421 ephemeris with a geocentric observer at (0°, 0°).

    Args:
        key: Lowercase name of the solar system body (must be in
            ``SOLAR_SYSTEM_BODIES``).

    Returns:
        A :class:`SearchResult` with the body's current coordinates.
    """
    bsp_name, body_type = SOLAR_SYSTEM_BODIES[key]
    t = astronomy.ts.now()
    earth = astronomy.eph["earth"]
    observer = earth + wgs84.latlon(0.0, 0.0)
    target = astronomy.eph[bsp_name]
    apparent = observer.at(t).observe(target).apparent()
    ra, dec, _ = apparent.radec()
    return SearchResult(
        name=key.capitalize(),
        type=body_type,
        ra_hours=round(cast(float, ra.hours), 4),
        dec_degrees=round(cast(float, dec.degrees), 4),
    )


def _search_named_star(key: str) -> SearchResult:
    """Return catalog (J2000) RA/Dec for a named star.

    Args:
        key: Lowercase name of the star (must be in ``NAMED_STARS``).

    Returns:
        A :class:`SearchResult` with the star's catalog coordinates.
    """
    ra_hours, dec_degrees = NAMED_STARS[key]
    return SearchResult(
        name=key.title(),
        type="Star",
        ra_hours=round(ra_hours, 4),
        dec_degrees=round(dec_degrees, 4),
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/search", response_model=SearchResult)
def search_object(
    name: str,
    current_user: User = Depends(get_current_user),
) -> SearchResult:
    """Search for a celestial object by name and return its equatorial coordinates.

    Solar-system bodies return their *current* geocentric position.
    Named stars return their J2000 catalog coordinates.

    Args:
        name: Case-insensitive object name (e.g. ``"Sirius"``, ``"Mars"``).
        current_user: Authenticated user (injected by FastAPI).

    Returns:
        A :class:`SearchResult` containing name, type, RA, and Dec.

    Raises:
        HTTPException: 404 if the object is not in the catalog.
    """
    key = name.strip().lower()
    if key in SOLAR_SYSTEM_BODIES:
        return _search_solar_system(key)
    if key in NAMED_STARS:
        return _search_named_star(key)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Celestial object '{name}' not found.",
    )

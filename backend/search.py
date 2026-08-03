"""Search router — look up a celestial object by name and return its
position (RA/Dec, altitude/azimuth, and distance) as seen from a
user-supplied observer location.
"""

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from skyfield.api import Star, wgs84

from . import astronomy, geodata
from .auth import get_current_user
from .geodata import ResolvedLocation
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
# Keys are lowercase; values are (ra_hours, dec_degrees, distance_ly) in
# J2000. RA/Dec are sourced from the Hipparcos catalog; distances are
# well-known approximate literature values (static, no network lookup).
# ---------------------------------------------------------------------------

NAMED_STARS: dict[str, tuple[float, float, float]] = {
    "sirius": (6.752477, -16.716114, 8.6),
    "canopus": (6.399197, -52.695661, 310.0),
    "arcturus": (14.261020, 19.182408, 37.0),
    "vega": (18.615649, 38.783689, 25.0),
    "capella": (5.278155, 45.997992, 43.0),
    "rigel": (5.242298, -8.201639, 860.0),
    "procyon": (7.655033, 5.224989, 11.5),
    "betelgeuse": (5.919529, 7.407064, 550.0),
    "aldebaran": (4.598677, 16.509303, 65.0),
    "antares": (16.490128, -26.431947, 550.0),
    "spica": (13.419883, -11.161319, 250.0),
    "pollux": (7.755264, 28.026200, 34.0),
    "fomalhaut": (22.960846, -29.622236, 25.0),
    "deneb": (20.690532, 45.280339, 2600.0),
    "regulus": (10.139531, 11.967208, 79.0),
    "polaris": (2.530303, 89.264108, 433.0),
    "acrux": (12.443304, -63.099092, 320.0),
    "mimosa": (12.795353, -59.688769, 280.0),
    "gacrux": (12.519433, -57.113214, 88.0),
    "hadar": (14.063724, -60.373039, 390.0),
    "rigil kentaurus": (14.660138, -60.833992, 4.37),
    "alpha centauri": (14.660138, -60.833992, 4.37),
    "alioth": (12.900486, 55.959822, 81.0),
    "dubhe": (11.062131, 61.751033, 123.0),
    "mirfak": (3.405381, 49.861181, 510.0),
    "bellatrix": (5.418851, 6.349703, 250.0),
    "alnilam": (5.603559, -1.201919, 2000.0),
    "alnitak": (5.679313, -1.942572, 800.0),
    "mintaka": (5.533444, -0.299094, 900.0),
    "adhara": (6.977100, -28.972089, 430.0),
    "elnath": (5.438198, 28.607453, 130.0),
    "castor": (7.576628, 31.888283, 51.0),
    "peacock": (20.427460, -56.735086, 180.0),
    "alnair": (22.137217, -46.960975, 101.0),
    "shaula": (17.560144, -37.103822, 570.0),
    "miaplacidus": (9.219994, -69.717208, 111.0),
    "avior": (8.375232, -59.509492, 610.0),
    "wezen": (7.139856, -26.393208, 1600.0),
    "menkent": (14.111374, -36.369958, 61.0),
    "atria": (16.811082, -69.027717, 391.0),
}


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class SearchResult(BaseModel):
    """Position of a matched celestial object as seen from a given location."""

    name: str
    type: str
    ra_hours: float
    dec_degrees: float
    altitude_degrees: float
    azimuth_degrees: float
    distance_km: float
    location: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _search_solar_system(key: str, location: ResolvedLocation) -> SearchResult:
    """Compute the apparent position of a solar system body for an observer.

    Uses the de421 ephemeris with a topocentric observer at the resolved
    latitude/longitude.

    Args:
        key: Lowercase name of the solar system body (must be in
            ``SOLAR_SYSTEM_BODIES``).
        location: The observer's resolved location.

    Returns:
        A :class:`SearchResult` with the body's current apparent position.
    """
    bsp_name, body_type = SOLAR_SYSTEM_BODIES[key]
    t = astronomy.ts.now()
    earth = astronomy.eph["earth"]
    observer = earth + wgs84.latlon(location.latitude, location.longitude)
    target = astronomy.eph[bsp_name]
    apparent = observer.at(t).observe(target).apparent()
    ra, dec, distance = apparent.radec()
    alt, az, _ = apparent.altaz()
    return SearchResult(
        name=key.capitalize(),
        type=body_type,
        ra_hours=round(cast(float, ra.hours), 4),
        dec_degrees=round(cast(float, dec.degrees), 4),
        altitude_degrees=round(cast(float, alt.degrees), 2),
        azimuth_degrees=round(cast(float, az.degrees), 2),
        distance_km=round(cast(float, distance.km), 0),
        location=location.label,
    )


def _search_named_star(key: str, location: ResolvedLocation) -> SearchResult:
    """Compute the apparent position of a catalog star for an observer.

    RA/Dec/distance are derived from the star's static catalog values;
    altitude and azimuth are computed for the resolved observer location
    and the current time.

    Args:
        key: Lowercase name of the star (must be in ``NAMED_STARS``).
        location: The observer's resolved location.

    Returns:
        A :class:`SearchResult` with the star's apparent position.
    """
    ra_hours, dec_degrees, distance_ly = NAMED_STARS[key]
    star = Star(ra_hours=ra_hours, dec_degrees=dec_degrees)
    t = astronomy.ts.now()
    earth = astronomy.eph["earth"]
    observer = earth + wgs84.latlon(location.latitude, location.longitude)
    apparent = observer.at(t).observe(star).apparent()
    ra, dec, _ = apparent.radec()
    alt, az, _ = apparent.altaz()
    return SearchResult(
        name=key.title(),
        type="Star",
        ra_hours=round(cast(float, ra.hours), 4),
        dec_degrees=round(cast(float, dec.degrees), 4),
        altitude_degrees=round(cast(float, alt.degrees), 2),
        azimuth_degrees=round(cast(float, az.degrees), 2),
        distance_km=round(geodata.light_years_to_km(distance_ly), 0),
        location=location.label,
    )


def _resolve_location(coordinates: str) -> ResolvedLocation:
    """Resolve the ``coordinates`` query parameter into a concrete location.

    Args:
        coordinates: Either raw ``"lat, lon"`` decimal coordinates, or a
            municipality name optionally qualified with a territory and/or
            country (e.g. ``"Paris"``, ``"Paris, France"``, or
            ``"Paris, Texas, United States"``).

    Returns:
        The resolved :class:`ResolvedLocation`.

    Raises:
        HTTPException: 400 if the coordinates are malformed or out of
            range, 404 if no municipality matches, or 409 if the query is
            ambiguous.
    """
    try:
        return geodata.resolve_coordinates(coordinates, geodata.get_gazetteer())
    except geodata.InvalidCoordinatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except geodata.AmbiguousMunicipalityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except geodata.MunicipalityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/search", response_model=SearchResult)
def search_object(
    name: str,
    coordinates: str,
    current_user: User = Depends(get_current_user),
) -> SearchResult:
    """Search for a celestial object and return its position for an observer.

    Solar-system bodies return their *current* apparent position as seen
    from the resolved observer location. Named stars return their catalog
    RA/Dec (adjusted for the observer's location) along with altitude and
    azimuth for that same location.

    Args:
        name: Case-insensitive object name (e.g. ``"Sirius"``, ``"Mars"``).
        coordinates: The observer's location — either raw ``"lat, lon"``
            coordinates or a municipality name (optionally qualified with
            a territory and/or country) resolved via the static
            municipality gazetteer.
        current_user: Authenticated user (injected by FastAPI).

    Returns:
        A :class:`SearchResult` containing name, type, RA, Dec, altitude,
        azimuth, distance, and the resolved location label.

    Raises:
        HTTPException: 400/404/409 if ``coordinates`` cannot be resolved,
            or 404 if the celestial object is not in the catalog.
    """
    location = _resolve_location(coordinates)

    key = name.strip().lower()
    if key in SOLAR_SYSTEM_BODIES:
        return _search_solar_system(key, location)
    if key in NAMED_STARS:
        return _search_named_star(key, location)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Celestial object '{name}' not found.",
    )

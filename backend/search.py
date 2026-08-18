"""Search router — look up a celestial object by name and return its
position (RA/Dec, altitude/azimuth, and distance) as seen from a
user-supplied observer location.
"""

from typing import Optional, cast

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from skyfield.api import Star, wgs84

from . import astronomy, compass, geodata, magnitudes, moons, openmeteo
from .geodata import ResolvedLocation
from .location import resolve_location

# ---------------------------------------------------------------------------
# "Is it visible right now?" thresholds
# ---------------------------------------------------------------------------

#: Minimum altitude (degrees) above the horizon for an object to be
#: considered currently visible.
MIN_VISIBLE_ALTITUDE_DEGREES: float = 10.0

#: Sun altitude (degrees) at or below which the sky is considered dark
#: enough for naked-eye viewing (roughly civil twilight).
MAX_SUN_ALTITUDE_FOR_VISIBILITY_DEGREES: float = -6.0

#: Maximum current cloud cover (percentage) for the sky to be
#: considered clear enough for naked-eye viewing.
CLOUD_COVER_VISIBILITY_THRESHOLD_PERCENT: float = 50.0

#: Faintest apparent magnitude generally visible to the naked eye under
#: a clear, dark sky away from significant light pollution.
NAKED_EYE_LIMITING_MAGNITUDE: float = 6.0

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
# Curated named-star catalog of naked-eye-visible stars, covering all 21
# first-magnitude stars plus many second-magnitude traditional/Bayer names.
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
    "achernar": (1.62857, -57.23667, 139.0),
    "altair": (19.846388, 8.868322, 17.0),
    "alphard": (9.459789, -8.658601, 177.0),
    "alphecca": (15.578131, 26.714694, 75.0),
    "alpheratz": (0.13979, 29.090942, 97.0),
    "ankaa": (0.438069, -42.305981, 77.0),
    "denebola": (11.817657, 14.572058, 36.0),
    "diphda": (0.726428, -17.986605, 96.0),
    "enif": (21.736434, 9.875010, 690.0),
    "gienah": (12.263449, -17.541929, 154.0),
    "hamal": (2.119558, 23.462423, 66.0),
    "kaus australis": (18.402866, -34.384617, 143.0),
    "kochab": (14.845090, 74.155502, 126.0),
    "markab": (23.079346, 15.205260, 133.0),
    "menkar": (3.037739, 4.089735, 220.0),
    "merak": (11.030689, 56.382423, 79.0),
    "mirach": (1.162194, 35.620557, 197.0),
    "nunki": (18.921108, -26.296722, 224.0),
    "phecda": (11.897157, 53.694761, 84.0),
    "rasalhague": (17.582239, 12.560034, 47.0),
    "sabik": (17.172907, -15.724911, 88.0),
    "sadalmelik": (22.096024, -0.319703, 520.0),
    "sadr": (20.370461, 40.256671, 1800.0),
    "saiph": (5.795941, -9.669605, 720.0),
    "sargas": (17.622040, -42.997822, 272.0),
    "scheat": (23.062942, 28.082789, 196.0),
    "schedar": (0.675116, 56.537331, 228.0),
    "suhail": (9.133202, -43.432588, 545.0),
    "thuban": (14.073152, 64.375862, 303.0),
    "unukalhai": (15.738361, 6.425628, 74.0),
    "zosma": (11.234845, 20.523721, 58.0),
    "zubenelgenubi": (14.847959, -16.041778, 77.0),
    "zubeneschamali": (15.283402, -9.382916, 185.0),
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
    apparent_magnitude: float
    sun_altitude_degrees: float
    cloud_cover_pct: Optional[float] = None
    visible: bool
    moon_separation_degrees: Optional[float] = None
    moon_direction: Optional[str] = None


class ObjectSuggestion(BaseModel):
    """A single celestial object suggestion for text-completion."""

    name: str
    type: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _current_cloud_cover_pct(location: ResolvedLocation) -> Optional[float]:
    """Best-effort fetch of the current cloud cover percentage for a location.

    Mirrors the best-effort pattern used elsewhere for weather
    integration (e.g. :func:`backend.viewrec._fetch_weather_forecast`):
    failures talking to the Open-Meteo API are swallowed here rather
    than propagated, so a visibility check still degrades gracefully
    without cloud data.

    Args:
        location: The observer's resolved location.

    Returns:
        The current cloud cover percentage, or ``None`` if it could not
        be retrieved.
    """
    try:
        return openmeteo.fetch_current_weather(
            location.latitude, location.longitude
        ).cloud_cover_pct
    except openmeteo.WeatherServiceError:
        return None


def _sun_altitude_degrees(observer, t) -> float:
    """Compute the Sun's current altitude for an observer.

    Args:
        observer: A Skyfield topocentric observer (Earth plus a
            ``wgs84.latlon`` offset).
        t: The Skyfield time at which to compute the Sun's position.

    Returns:
        The Sun's altitude above the horizon, in degrees.
    """
    sun_apparent = observer.at(t).observe(astronomy.eph["sun"]).apparent()
    sun_alt, _sun_az, _sun_distance = sun_apparent.altaz()
    return round(cast(float, sun_alt.degrees), 2)


def _moon_radec(observer, t) -> tuple[float, float]:
    """Compute the Moon's current Right Ascension and Declination.

    Args:
        observer: A Skyfield topocentric observer (Earth plus a
            ``wgs84.latlon`` offset).
        t: The Skyfield time at which to compute the Moon's position.

    Returns:
        A tuple of ``(ra_hours, dec_degrees)`` for the Moon's apparent
        position as seen by ``observer``.
    """
    moon_apparent = observer.at(t).observe(astronomy.eph["moon"]).apparent()
    moon_ra, moon_dec, _moon_distance = moon_apparent.radec()
    return cast(float, moon_ra.hours), cast(float, moon_dec.degrees)


def _moon_relative_position(
    observer, t, ra_hours: float, dec_degrees: float
) -> tuple[float, str]:
    """Describe an object's position relative to the Moon.

    Args:
        observer: A Skyfield topocentric observer (Earth plus a
            ``wgs84.latlon`` offset).
        t: The Skyfield time at which to compute the Moon's position.
        ra_hours: The object's Right Ascension, in hours.
        dec_degrees: The object's Declination, in degrees.

    Returns:
        A tuple of ``(separation_degrees, direction)``, where
        ``direction`` is one of the eight compass points (e.g.
        ``"NE"``) describing which way the object lies from the Moon.
    """
    moon_ra_hours, moon_dec_degrees = _moon_radec(observer, t)
    separation_degrees = round(
        compass.angular_separation_degrees(
            moon_ra_hours, moon_dec_degrees, ra_hours, dec_degrees
        ),
        2,
    )
    bearing = compass.bearing_degrees(
        moon_ra_hours, moon_dec_degrees, ra_hours, dec_degrees
    )
    return separation_degrees, compass.compass_direction(bearing)


def _is_currently_visible(
    object_altitude_degrees: float,
    sun_altitude_degrees: float,
    cloud_cover_pct: Optional[float],
    apparent_magnitude: float,
) -> bool:
    """Decide whether an object is visible right now, in plain terms.

    An object counts as visible when it is comfortably above the
    horizon, the sky is dark enough, the sky is clear enough (when
    cloud-cover data is available), and the object itself is bright
    enough for the naked eye. Sample times with no cloud-cover data
    (see :func:`_current_cloud_cover_pct`) are treated as acceptable on
    that count, since there's simply no data to judge them by.

    Args:
        object_altitude_degrees: The object's altitude above the
            horizon, in degrees.
        sun_altitude_degrees: The Sun's current altitude, in degrees.
        cloud_cover_pct: The current cloud cover percentage, or
            ``None`` if unavailable.
        apparent_magnitude: The object's current apparent magnitude.

    Returns:
        ``True`` if the object satisfies every visibility condition.
    """
    cloud_cover_ok = (
        cloud_cover_pct is None
        or cloud_cover_pct < CLOUD_COVER_VISIBILITY_THRESHOLD_PERCENT
    )
    return (
        object_altitude_degrees >= MIN_VISIBLE_ALTITUDE_DEGREES
        and sun_altitude_degrees <= MAX_SUN_ALTITUDE_FOR_VISIBILITY_DEGREES
        and cloud_cover_ok
        and apparent_magnitude <= NAKED_EYE_LIMITING_MAGNITUDE
    )


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

    ra_hours = cast(float, ra.hours)
    dec_degrees = cast(float, dec.degrees)
    altitude_degrees = round(cast(float, alt.degrees), 2)

    moon_separation_degrees: Optional[float] = None
    moon_direction: Optional[str] = None

    if key == "sun":
        # The Sun's own altitude *is* the relevant "sun altitude", and
        # its position relative to the Moon isn't meaningful to report.
        sun_altitude_degrees = altitude_degrees
        apparent_magnitude = magnitudes.sun_magnitude(cast(float, distance.au))
    elif key == "moon":
        sun_altitude_degrees = _sun_altitude_degrees(observer, t)
        phase_angle_degrees = cast(
            float, apparent.phase_angle(astronomy.eph["sun"]).degrees
        )
        apparent_magnitude = magnitudes.moon_magnitude(phase_angle_degrees)
    else:
        sun_altitude_degrees = _sun_altitude_degrees(observer, t)
        apparent_magnitude = magnitudes.planet_magnitude(apparent)
        if apparent_magnitude is None:
            apparent_magnitude = magnitudes.STATIC_MAGNITUDES.get(key, 0.0)
        moon_separation_degrees, moon_direction = _moon_relative_position(
            observer, t, ra_hours, dec_degrees
        )

    apparent_magnitude = round(apparent_magnitude, 2)
    cloud_cover_pct = _current_cloud_cover_pct(location)
    visible = _is_currently_visible(
        altitude_degrees, sun_altitude_degrees, cloud_cover_pct, apparent_magnitude
    )

    return SearchResult(
        name=key.capitalize(),
        type=body_type,
        ra_hours=round(ra_hours, 4),
        dec_degrees=round(dec_degrees, 4),
        altitude_degrees=altitude_degrees,
        azimuth_degrees=round(cast(float, az.degrees), 2),
        distance_km=round(cast(float, distance.km), 0),
        location=location.label,
        apparent_magnitude=apparent_magnitude,
        sun_altitude_degrees=sun_altitude_degrees,
        cloud_cover_pct=cloud_cover_pct,
        visible=visible,
        moon_separation_degrees=moon_separation_degrees,
        moon_direction=moon_direction,
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

    ra_hours_result = cast(float, ra.hours)
    dec_degrees_result = cast(float, dec.degrees)
    altitude_degrees = round(cast(float, alt.degrees), 2)
    sun_altitude_degrees = _sun_altitude_degrees(observer, t)
    apparent_magnitude = round(
        magnitudes.NAMED_STAR_MAGNITUDES.get(key, NAKED_EYE_LIMITING_MAGNITUDE), 2
    )
    cloud_cover_pct = _current_cloud_cover_pct(location)
    visible = _is_currently_visible(
        altitude_degrees, sun_altitude_degrees, cloud_cover_pct, apparent_magnitude
    )
    moon_separation_degrees, moon_direction = _moon_relative_position(
        observer, t, ra_hours_result, dec_degrees_result
    )

    return SearchResult(
        name=key.title(),
        type="Star",
        ra_hours=round(ra_hours_result, 4),
        dec_degrees=round(dec_degrees_result, 4),
        altitude_degrees=altitude_degrees,
        azimuth_degrees=round(cast(float, az.degrees), 2),
        distance_km=round(geodata.light_years_to_km(distance_ly), 0),
        location=location.label,
        apparent_magnitude=apparent_magnitude,
        sun_altitude_degrees=sun_altitude_degrees,
        cloud_cover_pct=cloud_cover_pct,
        visible=visible,
        moon_separation_degrees=moon_separation_degrees,
        moon_direction=moon_direction,
    )


def _search_moon(key: str, location: ResolvedLocation) -> SearchResult:
    """Compute the apparent position of a Jupiter/Saturn moon for an observer.

    Combines the de421 ephemeris position of the parent planet with a
    two-body Keplerian approximation of the moon's offset from it (see
    :mod:`backend.moons` for the accuracy caveats of this approach).

    Args:
        key: Lowercase name of the moon (must be in ``moons.MOONS``).
        location: The observer's resolved location.

    Returns:
        A :class:`SearchResult` with the moon's current apparent position.
    """
    t = astronomy.ts.now()
    earth = astronomy.eph["earth"]
    observer = earth + wgs84.latlon(location.latitude, location.longitude)
    target = moons.moon_target(key)
    apparent = observer.at(t).observe(target).apparent()
    ra, dec, distance = apparent.radec()
    alt, az, _ = apparent.altaz()

    ra_hours = cast(float, ra.hours)
    dec_degrees = cast(float, dec.degrees)
    altitude_degrees = round(cast(float, alt.degrees), 2)
    sun_altitude_degrees = _sun_altitude_degrees(observer, t)
    apparent_magnitude = round(
        magnitudes.STATIC_MAGNITUDES.get(key, NAKED_EYE_LIMITING_MAGNITUDE), 2
    )
    cloud_cover_pct = _current_cloud_cover_pct(location)
    visible = _is_currently_visible(
        altitude_degrees, sun_altitude_degrees, cloud_cover_pct, apparent_magnitude
    )
    moon_separation_degrees, moon_direction = _moon_relative_position(
        observer, t, ra_hours, dec_degrees
    )

    return SearchResult(
        name=key.capitalize(),
        type="Natural Satellite",
        ra_hours=round(ra_hours, 4),
        dec_degrees=round(dec_degrees, 4),
        altitude_degrees=altitude_degrees,
        azimuth_degrees=round(cast(float, az.degrees), 2),
        distance_km=round(cast(float, distance.km), 0),
        location=location.label,
        apparent_magnitude=apparent_magnitude,
        sun_altitude_degrees=sun_altitude_degrees,
        cloud_cover_pct=cloud_cover_pct,
        visible=visible,
        moon_separation_degrees=moon_separation_degrees,
        moon_direction=moon_direction,
    )


def _suggest_objects(prefix: str, limit: int = 10) -> list[ObjectSuggestion]:
    """Suggest catalog objects (solar-system bodies and named stars) whose
    name starts with ``prefix``.

    Intended for text-completion in a search-as-you-type UI (e.g. the
    celestial object search dropdown). Matching is case-insensitive and
    based on the object's name only.

    Args:
        prefix: The partial object name typed by the user. A blank/
            whitespace-only prefix yields no suggestions.
        limit: Maximum number of suggestions to return.

    Returns:
        Matching objects as :class:`ObjectSuggestion` instances, sorted
        alphabetically by name and truncated to ``limit`` entries. Empty
        if ``prefix`` is blank or nothing matches.
    """
    text = prefix.strip().lower()
    if not text:
        return []

    matches: list[tuple[str, str]] = []
    for key, (_, body_type) in SOLAR_SYSTEM_BODIES.items():
        if key.startswith(text):
            matches.append((key.capitalize(), body_type))
    for key in NAMED_STARS:
        if key.startswith(text):
            matches.append((key.title(), "Star"))
    for key in moons.MOONS:
        if key.startswith(text):
            matches.append((key.capitalize(), "Natural Satellite"))

    matches.sort(key=lambda pair: pair[0])
    return [ObjectSuggestion(name=n, type=t) for n, t in matches[:limit]]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/search/suggestions", response_model=list[ObjectSuggestion])
def suggest_objects(
    query: str = "",
    limit: int = Query(default=10, ge=1, le=50),
) -> list[ObjectSuggestion]:
    """Suggest celestial objects whose name starts with ``query``.

    Powers a search-as-you-type dropdown for the celestial object name
    field, drawing from ``SOLAR_SYSTEM_BODIES``, ``NAMED_STARS``, and
    ``moons.MOONS``.

    Args:
        query: The partial object name typed by the user. A blank query
            yields no suggestions.
        limit: Maximum number of suggestions to return (1-50).

    Returns:
        Matching objects as :class:`ObjectSuggestion` objects, sorted
        alphabetically by name.
    """
    return _suggest_objects(query, limit=limit)


@router.get("/search", response_model=SearchResult)
def search_object(
    name: str,
    coordinates: str,
) -> SearchResult:
    """Search for a celestial object and return its position for an observer.

    Solar-system bodies return their *current* apparent position as seen
    from the resolved observer location. Named stars return their catalog
    RA/Dec (adjusted for the observer's location) along with altitude and
    azimuth for that same location. Jupiter's and Saturn's major moons
    return an approximate current position (see :mod:`backend.moons`).

    The response also reports whether the object is currently visible
    to the naked eye -- comfortably above the horizon, in a sufficiently
    dark and clear sky, and bright enough (see
    :data:`MIN_VISIBLE_ALTITUDE_DEGREES`,
    :data:`MAX_SUN_ALTITUDE_FOR_VISIBILITY_DEGREES`,
    :data:`CLOUD_COVER_VISIBILITY_THRESHOLD_PERCENT`, and
    :data:`NAKED_EYE_LIMITING_MAGNITUDE`) -- along with the object's
    angular separation and compass direction relative to the Moon.

    Args:
        name: Case-insensitive object name (e.g. ``"Sirius"``, ``"Mars"``).
        coordinates: The observer's location — either raw ``"lat, lon"``
            coordinates or a municipality name (optionally qualified with
            a territory and/or country) resolved via the static
            municipality gazetteer.

    Returns:
        A :class:`SearchResult` containing name, type, RA, Dec, altitude,
        azimuth, distance, apparent magnitude, current visibility, and
        the object's position relative to the Moon, along with the
        resolved location label.

    Raises:
        HTTPException: 400/404/409 if ``coordinates`` cannot be resolved,
            or 404 if the celestial object is not in the catalog.
    """
    location = resolve_location(coordinates)

    key = name.strip().lower()
    if key in SOLAR_SYSTEM_BODIES:
        return _search_solar_system(key, location)
    if key in NAMED_STARS:
        return _search_named_star(key, location)
    if key in moons.MOONS:
        return _search_moon(key, location)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Celestial object '{name}' not found.",
    )

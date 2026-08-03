"""Best-time-to-view recommendation engine.

Given a celestial object and an observer's resolved location, this module
searches a bounded future time window to find the soonest moment the
object will be in "clear view": comfortably above the horizon, with the
sky dark enough that the object is genuinely visible to the naked eye.

The Sun is a special case: since it can only be observed during
daylight, "clear view" for the Sun means it is well above the horizon,
rather than requiring a dark sky.

This module has no FastAPI/HTTP dependencies. The ``/api/viewrec`` router
in :mod:`backend.viewrec` is responsible for translating its exceptions
into HTTP responses.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
from skyfield.api import Star, wgs84

from . import astronomy
from .geodata import ResolvedLocation
from .search import NAMED_STARS, SOLAR_SYSTEM_BODIES

# ---------------------------------------------------------------------------
# Visibility thresholds
# ---------------------------------------------------------------------------

#: Minimum altitude (degrees) above the horizon for an object to be
#: considered in "clear view". Objects lower than this are typically
#: obscured by horizon haze, trees, or buildings.
MIN_OBJECT_ALTITUDE_DEGREES: float = 15.0

#: Sun altitude (degrees) at or below which the sky is considered dark
#: enough for stargazing (roughly nautical twilight).
MAX_SUN_ALTITUDE_FOR_DARKNESS_DEGREES: float = -12.0

#: Minimum Sun altitude (degrees) for the Sun *itself* to be in clear view.
MIN_SUN_ALTITUDE_DEGREES: float = 10.0

#: How far into the future to search, and at what resolution, by default.
DEFAULT_SEARCH_WINDOW_DAYS: float = 14.0
DEFAULT_STEP_MINUTES: float = 5.0

#: Safety cap on the number of sampled time points, regardless of the
#: requested window/step, to bound computation time per request.
MAX_SAMPLE_POINTS: int = 20_000


class UnknownObjectError(Exception):
    """Raised when the requested celestial object is not in the catalog."""


@dataclass(frozen=True)
class ViewingMoment:
    """A single moment at which a celestial object is in clear view.

    Attributes:
        time: The UTC datetime of the moment.
        altitude_degrees: The object's altitude above the horizon.
        azimuth_degrees: The object's azimuth (compass bearing).
        sun_altitude_degrees: The Sun's altitude at that same moment.
    """

    time: datetime
    altitude_degrees: float
    azimuth_degrees: float
    sun_altitude_degrees: float


def _resolve_target(key: str) -> tuple[object, str]:
    """Resolve a lowercase object key to a Skyfield-observable target.

    Args:
        key: Lowercase, stripped celestial object name.

    Returns:
        A tuple of ``(target, type_label)`` where ``target`` is either a
        solar-system body from the loaded ephemeris or a :class:`Star`
        built from the static named-star catalog.

    Raises:
        UnknownObjectError: If ``key`` is not a recognised object.
    """
    if key in SOLAR_SYSTEM_BODIES:
        bsp_name, type_label = SOLAR_SYSTEM_BODIES[key]
        return astronomy.eph[bsp_name], type_label
    if key in NAMED_STARS:
        ra_hours, dec_degrees, _distance_ly = NAMED_STARS[key]
        return Star(ra_hours=ra_hours, dec_degrees=dec_degrees), "Star"
    raise UnknownObjectError(f"Celestial object '{key}' not found.")


def find_next_viewing_window(
    name: str,
    location: ResolvedLocation,
    search_window_days: float = DEFAULT_SEARCH_WINDOW_DAYS,
    step_minutes: float = DEFAULT_STEP_MINUTES,
) -> Optional[ViewingMoment]:
    """Find the soonest time an object will be in clear view for an observer.

    Samples the sky at regular intervals over the requested window,
    starting now, and returns the first moment at which the object clears
    :data:`MIN_OBJECT_ALTITUDE_DEGREES` while the sky is dark enough (Sun
    at or below :data:`MAX_SUN_ALTITUDE_FOR_DARKNESS_DEGREES`). The Sun
    itself is treated specially: it is "in clear view" once it rises
    above :data:`MIN_SUN_ALTITUDE_DEGREES`, since it can only be observed
    during daylight.

    Args:
        name: Case-insensitive object name (e.g. ``"Mars"``, ``"Sirius"``).
        location: The observer's resolved location.
        search_window_days: How many days into the future to search.
        step_minutes: The sampling resolution, in minutes.

    Returns:
        The soonest :class:`ViewingMoment` satisfying the visibility
        criteria, or ``None`` if no such moment is found within the
        search window.

    Raises:
        UnknownObjectError: If ``name`` is not a recognised celestial
            object.
    """
    key = name.strip().lower()
    target, _type_label = _resolve_target(key)

    earth = astronomy.eph["earth"]
    sun = astronomy.eph["sun"]
    observer = earth + wgs84.latlon(location.latitude, location.longitude)

    t0 = astronomy.ts.now()
    num_points = min(
        MAX_SAMPLE_POINTS,
        max(2, int((search_window_days * 24 * 60) / step_minutes) + 1),
    )
    t1 = astronomy.ts.tt_jd(t0.tt + search_window_days)
    times = astronomy.ts.linspace(t0, t1, num_points)

    observer_at_times = observer.at(times)

    target_alt, target_az, _ = observer_at_times.observe(target).apparent().altaz()
    sun_alt, _sun_az, _ = observer_at_times.observe(sun).apparent().altaz()

    alt_deg = np.asarray(target_alt.degrees)
    az_deg = np.asarray(target_az.degrees)
    sun_alt_deg = np.asarray(sun_alt.degrees)

    if key == "sun":
        mask = sun_alt_deg >= MIN_SUN_ALTITUDE_DEGREES
    else:
        mask = (alt_deg >= MIN_OBJECT_ALTITUDE_DEGREES) & (
            sun_alt_deg <= MAX_SUN_ALTITUDE_FOR_DARKNESS_DEGREES
        )

    indices = np.nonzero(mask)[0]
    if indices.size == 0:
        return None

    idx = int(indices[0])
    return ViewingMoment(
        time=times[idx].utc_datetime(),
        altitude_degrees=round(float(alt_deg[idx]), 2),
        azimuth_degrees=round(float(az_deg[idx]), 2),
        sun_altitude_degrees=round(float(sun_alt_deg[idx]), 2),
    )

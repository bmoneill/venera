"""Celestial-events calendar generator.

Given an observer's resolved location, this module computes a list of
notable celestial events over a bounded future window: Moon phase changes
(new moon, first quarter, full moon, last quarter) and the best clear-view
moment for each visible solar-system planet.

This module has no FastAPI/HTTP dependencies. The ``/api/calendar`` router
in :mod:`backend.calendar` is responsible for translating its exceptions
into HTTP responses.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from skyfield import almanac

from . import astronomy, visibility
from .geodata import ResolvedLocation
from .search import SOLAR_SYSTEM_BODIES

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: How far into the future the calendar covers, by default.
DEFAULT_CALENDAR_WINDOW_DAYS: float = 30.0

#: Sampling resolution (minutes) used when scanning for each planet's best
#: clear-view moment within the calendar window. Coarser than
#: :data:`backend.visibility.DEFAULT_STEP_MINUTES` since a month-long scan
#: at 5-minute resolution would be needlessly expensive for a "best night"
#: summary.
CALENDAR_STEP_MINUTES: float = 15.0

#: Human-readable names for the four Skyfield Moon-phase quarters, in
#: ``almanac.moon_phases`` integer order (0-3).
_MOON_PHASE_NAMES: tuple[str, str, str, str] = (
    "New Moon",
    "First Quarter",
    "Full Moon",
    "Last Quarter",
)

#: Solar-system bodies eligible for "best time to view" events. The Sun is
#: excluded (visible every day by definition) and the Moon is excluded
#: (its phases are reported separately, via :func:`moon_phase_events`).
CALENDAR_PLANETS: tuple[str, ...] = tuple(
    key for key in SOLAR_SYSTEM_BODIES if key not in ("sun", "moon")
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EphemerisUnavailableError(Exception):
    """Raised when the shared Skyfield ephemeris/timescale is unavailable."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalendarEvent:
    """A single notable celestial event within a calendar window.

    Attributes:
        time: The UTC datetime of the event.
        name: The celestial object involved (e.g. ``"Moon"``, ``"Mars"``).
        category: A short machine-readable event category (``"moon_phase"``
            or ``"best_view"``).
        title: A short, human-readable event title.
        description: A longer human-readable description.
        altitude_degrees: The object's altitude at ``time``, if applicable.
        azimuth_degrees: The object's azimuth at ``time``, if applicable.
    """

    time: datetime
    name: str
    category: str
    title: str
    description: str
    altitude_degrees: Optional[float] = None
    azimuth_degrees: Optional[float] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_ephemeris() -> None:
    """Raise if the shared Skyfield ephemeris/timescale has not been loaded.

    Raises:
        EphemerisUnavailableError: If ``astronomy.eph`` or ``astronomy.ts``
            is ``None``.
    """
    if astronomy.eph is None or astronomy.ts is None:
        raise EphemerisUnavailableError("The astronomical ephemeris is not available.")


# ---------------------------------------------------------------------------
# Event generators
# ---------------------------------------------------------------------------


def moon_phase_events(
    window_days: float = DEFAULT_CALENDAR_WINDOW_DAYS,
) -> list[CalendarEvent]:
    """Return Moon phase events within the next ``window_days``.

    Args:
        window_days: How many days into the future to search.

    Returns:
        A list of :class:`CalendarEvent` instances, one per phase change
        (new moon, first quarter, full moon, last quarter), in
        chronological order.

    Raises:
        EphemerisUnavailableError: If the Skyfield ephemeris is unavailable.
    """
    _require_ephemeris()

    t0 = astronomy.ts.now()
    t1 = astronomy.ts.tt_jd(t0.tt + window_days)
    times, phases = almanac.find_discrete(t0, t1, almanac.moon_phases(astronomy.eph))

    events: list[CalendarEvent] = []
    for t, phase in zip(times, phases):
        phase_name = _MOON_PHASE_NAMES[int(phase)]
        events.append(
            CalendarEvent(
                time=t.utc_datetime(),
                name="Moon",
                category="moon_phase",
                title=phase_name,
                description=f"The Moon is at its {phase_name} phase.",
            )
        )
    return events


def best_viewing_events(
    location: ResolvedLocation,
    window_days: float = DEFAULT_CALENDAR_WINDOW_DAYS,
    step_minutes: float = CALENDAR_STEP_MINUTES,
) -> list[CalendarEvent]:
    """Return the best clear-view moment for each visible planet.

    For every planet in :data:`CALENDAR_PLANETS`, this finds the single
    moment within the window at which it reaches its highest altitude
    while still in clear view (see
    :func:`backend.visibility.find_best_viewing_moment`). Planets that
    are never in clear view within the window are omitted entirely.

    Args:
        location: The observer's resolved location.
        window_days: How many days into the future to search.
        step_minutes: The sampling resolution, in minutes.

    Returns:
        A list of :class:`CalendarEvent` instances, one per visible
        planet, in chronological order.

    Raises:
        EphemerisUnavailableError: If the Skyfield ephemeris is unavailable.
    """
    _require_ephemeris()

    events: list[CalendarEvent] = []
    for key in CALENDAR_PLANETS:
        moment = visibility.find_best_viewing_moment(
            key, location, search_window_days=window_days, step_minutes=step_minutes
        )
        if moment is None:
            continue
        display_name = key.capitalize()
        events.append(
            CalendarEvent(
                time=moment.time,
                name=display_name,
                category="best_view",
                title=f"Best time to view {display_name}",
                description=(
                    f"{display_name} reaches its highest point in a dark sky "
                    f"as seen from {location.label}."
                ),
                altitude_degrees=moment.altitude_degrees,
                azimuth_degrees=moment.azimuth_degrees,
            )
        )
    return events


def build_calendar(
    location: ResolvedLocation,
    window_days: float = DEFAULT_CALENDAR_WINDOW_DAYS,
    step_minutes: float = CALENDAR_STEP_MINUTES,
) -> list[CalendarEvent]:
    """Build the full, chronologically-sorted calendar for a location.

    Combines :func:`moon_phase_events` and :func:`best_viewing_events`.

    Args:
        location: The observer's resolved location.
        window_days: How many days into the future the calendar covers.
        step_minutes: The sampling resolution used for planet visibility.

    Returns:
        All notable events within the window, sorted by ``time``.

    Raises:
        EphemerisUnavailableError: If the Skyfield ephemeris is unavailable.
    """
    events = moon_phase_events(window_days) + best_viewing_events(
        location, window_days, step_minutes
    )
    events.sort(key=lambda event: event.time)
    return events

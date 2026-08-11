"""Calendar router — a month's worth of notable celestial events for a
user-supplied observer location.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from . import calendar_events
from .location import resolve_location

# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class CalendarEventOut(BaseModel):
    """A single notable celestial event, as returned by the API."""

    time: datetime
    name: str
    category: str
    title: str
    description: str
    altitude_degrees: Optional[float] = None
    azimuth_degrees: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    weather_description: Optional[str] = None


class CalendarResponse(BaseModel):
    """A calendar of notable celestial events for an observer location."""

    location: str
    window_days: float
    events: list[CalendarEventOut]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/calendar", response_model=CalendarResponse)
def get_calendar(
    coordinates: str,
    days: float = Query(
        default=calendar_events.DEFAULT_CALENDAR_WINDOW_DAYS, gt=0, le=90
    ),
) -> CalendarResponse:
    """Return a calendar of notable celestial events for an observer location.

    The calendar currently includes Moon phase changes (new moon, first
    quarter, full moon, last quarter) and the best clear-view moment for
    each visible planet within the requested window.

    Args:
        coordinates: The observer's location — either a municipality name
            (optionally qualified with a territory and/or country) or raw
            "lat, lon" coordinates.
        days: How many days into the future the calendar should cover
            (0-90, default 30).

    Returns:
        A :class:`CalendarResponse` listing all notable events within the
        window, sorted chronologically.

    Raises:
        HTTPException: 400/404/409 if ``coordinates`` cannot be resolved,
            or 503 if the astronomical ephemeris is unavailable.
    """
    location = resolve_location(coordinates)

    try:
        events = calendar_events.build_calendar(location, window_days=days)
    except calendar_events.EphemerisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return CalendarResponse(
        location=location.label,
        window_days=days,
        events=[
            CalendarEventOut(
                time=event.time,
                name=event.name,
                category=event.category,
                title=event.title,
                description=event.description,
                altitude_degrees=event.altitude_degrees,
                azimuth_degrees=event.azimuth_degrees,
                cloud_cover_pct=event.cloud_cover_pct,
                weather_description=event.weather_description,
            )
            for event in events
        ],
    )

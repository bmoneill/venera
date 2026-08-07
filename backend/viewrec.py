"""Viewing-recommendation router — suggest the soonest time a celestial
object will be in clear view from a user-supplied observer location.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from . import openmeteo, visibility
from .geodata import ResolvedLocation
from .location import resolve_location
from .search import NAMED_STARS, SOLAR_SYSTEM_BODIES

# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class ViewingRecommendation(BaseModel):
    """The soonest "clear view" moment for a celestial object, if any."""

    name: str
    type: str
    location: str
    visible: bool
    time: Optional[datetime] = None
    altitude_degrees: Optional[float] = None
    azimuth_degrees: Optional[float] = None
    sun_altitude_degrees: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    weather_description: Optional[str] = None
    search_window_days: float
    message: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _identify_object(name: str) -> tuple[str, str]:
    """Resolve a celestial object name to its canonical display name and type.

    Args:
        name: Case-insensitive object name (e.g. ``"Sirius"``, ``"Mars"``).

    Returns:
        A tuple of ``(display_name, type_label)``.

    Raises:
        HTTPException: 404 if the object is not in the catalog.
    """
    key = name.strip().lower()
    if key in SOLAR_SYSTEM_BODIES:
        return key.capitalize(), SOLAR_SYSTEM_BODIES[key][1]
    if key in NAMED_STARS:
        return key.title(), "Star"
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Celestial object '{name}' not found.",
    )


def _fetch_weather_forecast(
    location: ResolvedLocation, search_window_days: float
) -> Optional[openmeteo.HourlyForecast]:
    """Best-effort fetch of an hourly cloud-cover forecast for a location.

    The "When to View" algorithm is still fully functional without
    weather data (it simply won't factor in cloud cover), so failures
    talking to the Open-Meteo API are swallowed here rather than
    propagated as an HTTP error.

    Args:
        location: The observer's resolved location.
        search_window_days: How many days of forecast to request, capped
            at Open-Meteo's supported horizon.

    Returns:
        The :class:`~backend.openmeteo.HourlyForecast`, or ``None`` if it
        could not be retrieved.
    """
    try:
        return openmeteo.fetch_hourly_forecast(
            location.latitude,
            location.longitude,
            days=int(search_window_days) + 1,
        )
    except openmeteo.WeatherServiceError:
        return None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/viewrec", response_model=ViewingRecommendation)
def recommend_viewing_time(
    name: str,
    coordinates: str,
) -> ViewingRecommendation:
    """Recommend the soonest time a celestial object will be in clear view.

    "Clear view" means the object is comfortably above the horizon and
    the sky is dark enough to see it with the naked eye (except for the
    Sun, which requires daylight instead). The search covers the next
    :data:`backend.visibility.DEFAULT_SEARCH_WINDOW_DAYS` days.

    Args:
        name: Case-insensitive object name (e.g. ``"Sirius"``, ``"Mars"``).
        coordinates: The observer's location — either a municipality name
            (optionally qualified with a territory and/or country) or raw
            ``"lat, lon"`` coordinates.

    Returns:
        A :class:`ViewingRecommendation` describing the soonest matching
        moment, or indicating that none was found within the search
        window.

    Raises:
        HTTPException: 400/404/409 if ``coordinates`` cannot be resolved,
            or 404 if the celestial object is not in the catalog.
    """
    location = resolve_location(coordinates)
    display_name, type_label = _identify_object(name)

    weather_forecast = _fetch_weather_forecast(
        location, visibility.DEFAULT_SEARCH_WINDOW_DAYS
    )
    moment = visibility.find_next_viewing_window(
        name, location, weather_forecast=weather_forecast
    )

    if moment is None:
        return ViewingRecommendation(
            name=display_name,
            type=type_label,
            location=location.label,
            visible=False,
            search_window_days=visibility.DEFAULT_SEARCH_WINDOW_DAYS,
            message=(
                f"{display_name} will not be in clear view from "
                f"{location.label} within the next "
                f"{int(visibility.DEFAULT_SEARCH_WINDOW_DAYS)} days."
            ),
        )

    formatted_time = moment.time.strftime("%Y-%m-%d %H:%M UTC")
    message = f"Best viewed from {location.label} at {formatted_time}."
    if moment.weather_description is not None:
        message += f" Expected sky: {moment.weather_description.lower()}."
    return ViewingRecommendation(
        name=display_name,
        type=type_label,
        location=location.label,
        visible=True,
        time=moment.time,
        altitude_degrees=moment.altitude_degrees,
        azimuth_degrees=moment.azimuth_degrees,
        sun_altitude_degrees=moment.sun_altitude_degrees,
        cloud_cover_pct=moment.cloud_cover_pct,
        weather_description=moment.weather_description,
        search_window_days=visibility.DEFAULT_SEARCH_WINDOW_DAYS,
        message=message,
    )

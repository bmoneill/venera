"""Weather router — current conditions for a user-supplied observer
location, sourced from the Open-Meteo API.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from . import openmeteo
from .auth import get_current_user
from .location import resolve_location
from .models import User

# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class WeatherReport(BaseModel):
    """Current weather conditions at a resolved observer location."""

    location: str
    time: datetime
    temperature_c: float
    apparent_temperature_c: float
    humidity_pct: float
    cloud_cover_pct: float
    precipitation_mm: float
    wind_speed_kmh: float
    weather_code: int
    description: str
    is_day: bool


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/weather", response_model=WeatherReport)
def get_weather(
    coordinates: str,
    current_user: User = Depends(get_current_user),
) -> WeatherReport:
    """Return current weather conditions for an observer location.

    Args:
        coordinates: The observer's location — either a municipality name
            (optionally qualified with a territory and/or country) or raw
            ``"lat, lon"`` coordinates.
        current_user: Authenticated user (injected by FastAPI).

    Returns:
        A :class:`WeatherReport` describing current conditions at the
        resolved location.

    Raises:
        HTTPException: 400/404/409 if ``coordinates`` cannot be resolved,
            or 502 if the Open-Meteo weather service is unreachable.
    """
    location = resolve_location(coordinates)

    try:
        current = openmeteo.fetch_current_weather(location.latitude, location.longitude)
    except openmeteo.WeatherServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return WeatherReport(
        location=location.label,
        time=current.time,
        temperature_c=current.temperature_c,
        apparent_temperature_c=current.apparent_temperature_c,
        humidity_pct=current.humidity_pct,
        cloud_cover_pct=current.cloud_cover_pct,
        precipitation_mm=current.precipitation_mm,
        wind_speed_kmh=current.wind_speed_kmh,
        weather_code=current.weather_code,
        description=current.description,
        is_day=current.is_day,
    )

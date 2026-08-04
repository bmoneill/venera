"""Open-Meteo API client.

Thin, dependency-injectable wrapper around the free Open-Meteo weather
API (https://open-meteo.com/). This module has no FastAPI/HTTP-framework
dependencies; the ``/api/weather`` router in :mod:`backend.weather` is
responsible for translating :class:`WeatherServiceError` into an HTTP
response, and :mod:`backend.visibility` consumes :class:`HourlyForecast`
to factor cloud cover into the "When to View" algorithm.

Note: this project depends on ``httpx2``, a drop-in-compatible fork of
the ``httpx`` HTTP client (same public API), imported below as ``httpx``
for readability.
"""

import bisect
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx2 as httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Base URL for the Open-Meteo forecast endpoint.
FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"

#: Network timeout for outbound requests, in seconds.
REQUEST_TIMEOUT_SECONDS: float = 10.0

#: Open-Meteo's maximum supported forecast horizon, in days.
MAX_FORECAST_DAYS: int = 16

#: Human-readable descriptions for WMO weather codes, as used by Open-Meteo.
#: See https://open-meteo.com/en/docs for the full code table.
WMO_WEATHER_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherServiceError(Exception):
    """Raised when the Open-Meteo API cannot be reached or returns bad data."""


def describe_weather_code(weather_code: int) -> str:
    """Translate a WMO weather code into a short human-readable description.

    Args:
        weather_code: A WMO weather interpretation code, as returned by
            Open-Meteo.

    Returns:
        A short description, or ``"Unknown"`` if the code is unrecognised.
    """
    return WMO_WEATHER_DESCRIPTIONS.get(weather_code, "Unknown")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CurrentWeather:
    """A snapshot of current weather conditions at a location.

    Attributes:
        time: UTC timestamp of the observation.
        temperature_c: Air temperature, in degrees Celsius.
        apparent_temperature_c: "Feels like" temperature, in degrees Celsius.
        humidity_pct: Relative humidity, as a percentage.
        cloud_cover_pct: Total cloud cover, as a percentage.
        precipitation_mm: Precipitation over the last hour, in millimetres.
        wind_speed_kmh: Wind speed, in km/h.
        weather_code: WMO weather interpretation code.
        is_day: Whether it is currently daytime at the location.
    """

    time: datetime
    temperature_c: float
    apparent_temperature_c: float
    humidity_pct: float
    cloud_cover_pct: float
    precipitation_mm: float
    wind_speed_kmh: float
    weather_code: int
    is_day: bool

    @property
    def description(self) -> str:
        """A short human-readable description of ``weather_code``."""
        return describe_weather_code(self.weather_code)


@dataclass(frozen=True)
class HourlyForecast:
    """An hourly cloud-cover/precipitation/weather-code forecast time series.

    Attributes:
        times: UTC timestamps for each hourly sample, in ascending order.
        cloud_cover_pct: Total cloud cover (percentage) at each sample time.
        precipitation_probability_pct: Precipitation probability
            (percentage) at each sample time.
        weather_code: WMO weather interpretation code at each sample time.
    """

    times: list[datetime]
    cloud_cover_pct: list[float]
    precipitation_probability_pct: list[float]
    weather_code: list[int]

    def _nearest_index(self, when: datetime) -> Optional[int]:
        """Return the index of the sample hour closest to ``when``.

        Args:
            when: A timezone-aware (or naive, assumed UTC) moment.

        Returns:
            The index into the forecast arrays, or ``None`` if ``when``
            falls outside the forecast's time range.
        """
        if not self.times:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when < self.times[0] or when > self.times[-1]:
            return None
        pos = bisect.bisect_left(self.times, when)
        if pos == 0:
            return 0
        if pos == len(self.times):
            return len(self.times) - 1
        before, after = self.times[pos - 1], self.times[pos]
        return pos - 1 if (when - before) <= (after - when) else pos

    def cloud_cover_at(self, when: datetime) -> Optional[float]:
        """Look up the cloud cover (percentage) nearest to ``when``.

        Returns:
            The cloud cover percentage, or ``None`` if ``when`` falls
            outside the forecast's time range.
        """
        index = self._nearest_index(when)
        return None if index is None else self.cloud_cover_pct[index]

    def weather_code_at(self, when: datetime) -> Optional[int]:
        """Look up the WMO weather code nearest to ``when``.

        Returns:
            The weather code, or ``None`` if ``when`` falls outside the
            forecast's time range.
        """
        index = self._nearest_index(when)
        return None if index is None else self.weather_code[index]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_iso_utc(value: str) -> datetime:
    """Parse an Open-Meteo ``timezone=UTC`` ISO-8601 timestamp.

    Args:
        value: A timestamp such as ``"2024-06-01T22:30"``.

    Returns:
        A timezone-aware UTC :class:`datetime`.
    """
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _request(params: dict[str, Any]) -> dict[str, Any]:
    """Perform a GET request against the Open-Meteo forecast endpoint.

    Args:
        params: Query parameters for the request.

    Returns:
        The parsed JSON response body.

    Raises:
        WeatherServiceError: If the request fails, times out, or the
            response is not valid JSON.
    """
    try:
        response = httpx.get(
            FORECAST_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return cast_to_dict(response.json())
    except httpx.HTTPError as exc:
        raise WeatherServiceError(
            f"Failed to reach the Open-Meteo weather service: {exc}"
        ) from exc


def cast_to_dict(value: Any) -> dict[str, Any]:
    """Validate that a decoded JSON response is a top-level object.

    Args:
        value: The decoded JSON value.

    Returns:
        ``value``, typed as a dictionary.

    Raises:
        WeatherServiceError: If ``value`` is not a dictionary.
    """
    if not isinstance(value, dict):
        raise WeatherServiceError("Unexpected response from the weather service.")
    return value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_current_weather(latitude: float, longitude: float) -> CurrentWeather:
    """Fetch current weather conditions for a location.

    Args:
        latitude: Observer latitude, in decimal degrees.
        longitude: Observer longitude, in decimal degrees.

    Returns:
        The current :class:`CurrentWeather` snapshot.

    Raises:
        WeatherServiceError: If the Open-Meteo API cannot be reached or
            returns an unexpected payload.
    """
    payload = _request(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "cloud_cover",
                    "precipitation",
                    "wind_speed_10m",
                    "weather_code",
                    "is_day",
                ]
            ),
            "timezone": "UTC",
        }
    )
    try:
        current = payload["current"]
        return CurrentWeather(
            time=_parse_iso_utc(current["time"]),
            temperature_c=float(current["temperature_2m"]),
            apparent_temperature_c=float(current["apparent_temperature"]),
            humidity_pct=float(current["relative_humidity_2m"]),
            cloud_cover_pct=float(current["cloud_cover"]),
            precipitation_mm=float(current["precipitation"]),
            wind_speed_kmh=float(current["wind_speed_10m"]),
            weather_code=int(current["weather_code"]),
            is_day=bool(current["is_day"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherServiceError(
            "Unexpected response shape from the weather service."
        ) from exc


def fetch_hourly_forecast(
    latitude: float, longitude: float, days: int = MAX_FORECAST_DAYS
) -> HourlyForecast:
    """Fetch an hourly cloud-cover/precipitation/weather-code forecast.

    Args:
        latitude: Observer latitude, in decimal degrees.
        longitude: Observer longitude, in decimal degrees.
        days: Number of days to forecast, capped at
            :data:`MAX_FORECAST_DAYS`.

    Returns:
        The :class:`HourlyForecast` time series.

    Raises:
        WeatherServiceError: If the Open-Meteo API cannot be reached or
            returns an unexpected payload.
    """
    payload = _request(
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "cloud_cover,precipitation_probability,weather_code",
            "forecast_days": max(1, min(days, MAX_FORECAST_DAYS)),
            "timezone": "UTC",
        }
    )
    try:
        hourly = payload["hourly"]
        return HourlyForecast(
            times=[_parse_iso_utc(t) for t in hourly["time"]],
            cloud_cover_pct=[float(v) for v in hourly["cloud_cover"]],
            precipitation_probability_pct=[
                float(v) for v in hourly["precipitation_probability"]
            ],
            weather_code=[int(v) for v in hourly["weather_code"]],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherServiceError(
            "Unexpected response shape from the weather service."
        ) from exc

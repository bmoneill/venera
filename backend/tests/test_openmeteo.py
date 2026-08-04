"""Tests for the Open-Meteo API client (``backend.openmeteo``)."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend import openmeteo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(payload: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Build a MagicMock standing in for an ``httpx2`` Response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = openmeteo.httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    else:
        response.raise_for_status.return_value = None
    return response


CURRENT_PAYLOAD = {
    "current": {
        "time": "2024-06-01T22:30",
        "temperature_2m": 18.5,
        "apparent_temperature": 17.9,
        "relative_humidity_2m": 60.0,
        "cloud_cover": 25.0,
        "precipitation": 0.0,
        "wind_speed_10m": 12.3,
        "weather_code": 1,
        "is_day": 0,
    }
}

HOURLY_PAYLOAD = {
    "hourly": {
        "time": ["2024-06-01T00:00", "2024-06-01T01:00", "2024-06-01T02:00"],
        "cloud_cover": [10.0, 50.0, 90.0],
        "precipitation_probability": [0.0, 5.0, 40.0],
        "weather_code": [0, 2, 61],
    }
}


# ---------------------------------------------------------------------------
# describe_weather_code
# ---------------------------------------------------------------------------


class TestDescribeWeatherCode:
    def test_known_code_returns_description(self):
        assert openmeteo.describe_weather_code(0) == "Clear sky"

    def test_unknown_code_returns_unknown(self):
        assert openmeteo.describe_weather_code(-1) == "Unknown"


# ---------------------------------------------------------------------------
# fetch_current_weather
# ---------------------------------------------------------------------------


class TestFetchCurrentWeather:
    def test_parses_current_weather(self, monkeypatch):
        monkeypatch.setattr(
            openmeteo.httpx,
            "get",
            MagicMock(return_value=_fake_response(CURRENT_PAYLOAD)),
        )
        result = openmeteo.fetch_current_weather(48.8566, 2.3522)
        assert result.time == datetime(2024, 6, 1, 22, 30, tzinfo=timezone.utc)
        assert result.temperature_c == pytest.approx(18.5)
        assert result.cloud_cover_pct == pytest.approx(25.0)
        assert result.weather_code == 1
        assert result.is_day is False
        assert result.description == "Mainly clear"

    def test_raises_on_transport_error(self, monkeypatch):
        monkeypatch.setattr(
            openmeteo.httpx,
            "get",
            MagicMock(side_effect=openmeteo.httpx.ConnectError("no network")),
        )
        with pytest.raises(openmeteo.WeatherServiceError):
            openmeteo.fetch_current_weather(48.8566, 2.3522)

    def test_raises_on_http_status_error(self, monkeypatch):
        monkeypatch.setattr(
            openmeteo.httpx,
            "get",
            MagicMock(return_value=_fake_response({}, status_code=500)),
        )
        with pytest.raises(openmeteo.WeatherServiceError):
            openmeteo.fetch_current_weather(48.8566, 2.3522)

    def test_raises_on_malformed_payload(self, monkeypatch):
        monkeypatch.setattr(
            openmeteo.httpx,
            "get",
            MagicMock(return_value=_fake_response({"current": {}})),
        )
        with pytest.raises(openmeteo.WeatherServiceError):
            openmeteo.fetch_current_weather(48.8566, 2.3522)


# ---------------------------------------------------------------------------
# fetch_hourly_forecast
# ---------------------------------------------------------------------------


class TestFetchHourlyForecast:
    def test_parses_hourly_forecast(self, monkeypatch):
        monkeypatch.setattr(
            openmeteo.httpx,
            "get",
            MagicMock(return_value=_fake_response(HOURLY_PAYLOAD)),
        )
        forecast = openmeteo.fetch_hourly_forecast(48.8566, 2.3522)
        assert forecast.times[0] == datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
        assert forecast.cloud_cover_pct == [10.0, 50.0, 90.0]
        assert forecast.weather_code == [0, 2, 61]

    def test_clamps_days_to_max_forecast_days(self, monkeypatch):
        mock_get = MagicMock(return_value=_fake_response(HOURLY_PAYLOAD))
        monkeypatch.setattr(openmeteo.httpx, "get", mock_get)
        openmeteo.fetch_hourly_forecast(48.8566, 2.3522, days=999)
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["forecast_days"] == openmeteo.MAX_FORECAST_DAYS

    def test_raises_on_transport_error(self, monkeypatch):
        monkeypatch.setattr(
            openmeteo.httpx,
            "get",
            MagicMock(side_effect=openmeteo.httpx.ConnectError("no network")),
        )
        with pytest.raises(openmeteo.WeatherServiceError):
            openmeteo.fetch_hourly_forecast(48.8566, 2.3522)


# ---------------------------------------------------------------------------
# HourlyForecast lookups
# ---------------------------------------------------------------------------


class TestHourlyForecastLookups:
    FORECAST = openmeteo.HourlyForecast(
        times=[
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        ],
        cloud_cover_pct=[10.0, 50.0, 90.0],
        precipitation_probability_pct=[0.0, 5.0, 40.0],
        weather_code=[0, 2, 61],
    )

    def test_exact_match(self):
        when = datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)
        assert self.FORECAST.cloud_cover_at(when) == pytest.approx(50.0)

    def test_nearest_match_rounds_to_closer_hour(self):
        when = datetime(2024, 1, 1, 1, 40, tzinfo=timezone.utc)
        assert self.FORECAST.cloud_cover_at(when) == pytest.approx(90.0)

    def test_out_of_range_returns_none(self):
        when = datetime(2025, 1, 1, tzinfo=timezone.utc)
        assert self.FORECAST.cloud_cover_at(when) is None

    def test_weather_code_lookup(self):
        when = datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc)
        assert self.FORECAST.weather_code_at(when) == 61

    def test_empty_forecast_returns_none(self):
        empty = openmeteo.HourlyForecast(
            times=[],
            cloud_cover_pct=[],
            precipitation_probability_pct=[],
            weather_code=[],
        )
        assert empty.cloud_cover_at(datetime(2024, 1, 1, tzinfo=timezone.utc)) is None

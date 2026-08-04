"""Tests for the /api/weather endpoint."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend import openmeteo, weather

PARIS = {"coordinates": "Paris, France"}

SAMPLE_WEATHER = openmeteo.CurrentWeather(
    time=datetime(2024, 6, 1, 22, 30, tzinfo=timezone.utc),
    temperature_c=18.5,
    apparent_temperature_c=17.9,
    humidity_pct=60.0,
    cloud_cover_pct=25.0,
    precipitation_mm=0.0,
    wind_speed_kmh=12.3,
    weather_code=1,
    is_day=False,
)


def _patch_current_weather(monkeypatch, value=None, error=None):
    """Patch ``weather.openmeteo.fetch_current_weather`` to return or raise."""
    if error is not None:
        mock_fetch = MagicMock(side_effect=error)
    else:
        mock_fetch = MagicMock(return_value=value)
    monkeypatch.setattr(weather.openmeteo, "fetch_current_weather", mock_fetch)
    return mock_fetch


class TestWeatherEndpoint:
    """Tests for the ``/api/weather`` endpoint's happy path."""

    def test_returns_200_with_weather_report(self, client, monkeypatch):
        _patch_current_weather(monkeypatch, value=SAMPLE_WEATHER)
        response = client.get("/api/weather", params=PARIS)
        assert response.status_code == 200
        data = response.json()
        assert data["temperature_c"] == 18.5
        assert data["cloud_cover_pct"] == 25.0
        assert data["description"] == "Mainly clear"
        assert data["is_day"] is False

    def test_response_includes_resolved_location(self, client, monkeypatch):
        _patch_current_weather(monkeypatch, value=SAMPLE_WEATHER)
        response = client.get("/api/weather", params=PARIS)
        assert response.json()["location"] == "Paris, Ile-de-France, France"

    def test_raw_lat_lon_coordinates(self, client, monkeypatch):
        _patch_current_weather(monkeypatch, value=SAMPLE_WEATHER)
        response = client.get("/api/weather", params={"coordinates": "48.8566, 2.3522"})
        assert response.status_code == 200
        assert response.json()["location"] == "48.8566, 2.3522"


class TestWeatherEndpointErrors:
    """Tests for error conditions on the ``/api/weather`` endpoint."""

    def test_weather_service_error_returns_502(self, client, monkeypatch):
        _patch_current_weather(
            monkeypatch, error=openmeteo.WeatherServiceError("unreachable")
        )
        response = client.get("/api/weather", params=PARIS)
        assert response.status_code == 502

    def test_ambiguous_municipality_returns_409(self, client):
        response = client.get("/api/weather", params={"coordinates": "Paris"})
        assert response.status_code == 409

    def test_unknown_municipality_returns_404(self, client):
        response = client.get(
            "/api/weather", params={"coordinates": "Nowhereville, Nowhere"}
        )
        assert response.status_code == 404

    def test_invalid_raw_coordinates_returns_400(self, client):
        response = client.get("/api/weather", params={"coordinates": "200, 50"})
        assert response.status_code == 400

    def test_missing_coordinates_returns_422(self, client):
        response = client.get("/api/weather", params={})
        assert response.status_code == 422

    def test_requires_authentication(self):
        from fastapi.testclient import TestClient as PlainClient

        from backend.main import app

        with PlainClient(app) as plain_client:
            response = plain_client.get("/api/weather", params=PARIS)
        assert response.status_code == 401

"""Tests for the /api/calendar endpoint."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend import calendar_events

PARIS = {"coordinates": "Paris, France"}

SAMPLE_EVENTS = [
    calendar_events.CalendarEvent(
        time=datetime(2024, 6, 1, 3, 0, tzinfo=timezone.utc),
        name="Moon",
        category="moon_phase",
        title="Full Moon",
        description="The Moon is at its Full Moon phase.",
    ),
    calendar_events.CalendarEvent(
        time=datetime(2024, 6, 10, 22, 0, tzinfo=timezone.utc),
        name="Mars",
        category="best_view",
        title="Best time to view Mars",
        description="Mars reaches its highest point in a dark sky as seen from Paris, Ile-de-France, France.",
        altitude_degrees=52.3,
        azimuth_degrees=178.5,
    ),
]


def _patch_build_calendar(monkeypatch, value=None, error=None):
    """Patch ``calendar.calendar_events.build_calendar`` to return or raise."""
    from backend import calendar as calendar_router_module

    if error is not None:
        mock_build = MagicMock(side_effect=error)
    else:
        mock_build = MagicMock(return_value=value if value is not None else [])
    monkeypatch.setattr(
        calendar_router_module.calendar_events, "build_calendar", mock_build
    )
    return mock_build


class TestCalendarEndpoint:
    """Tests for the ``/api/calendar`` endpoint's happy path."""

    def test_returns_200_with_events(self, client, monkeypatch):
        _patch_build_calendar(monkeypatch, value=SAMPLE_EVENTS)
        response = client.get("/api/calendar", params=PARIS)
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 2

    def test_response_includes_resolved_location(self, client, monkeypatch):
        _patch_build_calendar(monkeypatch, value=SAMPLE_EVENTS)
        response = client.get("/api/calendar", params=PARIS)
        assert response.json()["location"] == "Paris, Ile-de-France, France"

    def test_event_shape(self, client, monkeypatch):
        _patch_build_calendar(monkeypatch, value=SAMPLE_EVENTS)
        response = client.get("/api/calendar", params=PARIS)
        event = response.json()["events"][0]
        assert set(event.keys()) == {
            "time",
            "name",
            "category",
            "title",
            "description",
            "altitude_degrees",
            "azimuth_degrees",
            "cloud_cover_pct",
            "weather_description",
        }

    def test_moon_phase_event_omits_altaz(self, client, monkeypatch):
        _patch_build_calendar(monkeypatch, value=SAMPLE_EVENTS)
        response = client.get("/api/calendar", params=PARIS)
        moon_event = response.json()["events"][0]
        assert moon_event["altitude_degrees"] is None
        assert moon_event["azimuth_degrees"] is None

    def test_best_view_event_includes_altaz(self, client, monkeypatch):
        _patch_build_calendar(monkeypatch, value=SAMPLE_EVENTS)
        response = client.get("/api/calendar", params=PARIS)
        mars_event = response.json()["events"][1]
        assert mars_event["altitude_degrees"] == pytest.approx(52.3)
        assert mars_event["azimuth_degrees"] == pytest.approx(178.5)

    def test_event_includes_weather_fields_when_present(self, client, monkeypatch):
        events = [
            calendar_events.CalendarEvent(
                time=datetime(2024, 6, 10, 22, 0, tzinfo=timezone.utc),
                name="Mars",
                category="best_view",
                title="Best time to view Mars",
                description="Mars reaches its highest point in a dark sky.",
                altitude_degrees=52.3,
                azimuth_degrees=178.5,
                cloud_cover_pct=12.0,
                weather_description="Mainly clear",
            ),
        ]
        _patch_build_calendar(monkeypatch, value=events)
        response = client.get("/api/calendar", params=PARIS)
        mars_event = response.json()["events"][0]
        assert mars_event["cloud_cover_pct"] == pytest.approx(12.0)
        assert mars_event["weather_description"] == "Mainly clear"

    def test_event_weather_fields_default_to_none(self, client, monkeypatch):
        _patch_build_calendar(monkeypatch, value=SAMPLE_EVENTS)
        response = client.get("/api/calendar", params=PARIS)
        for event in response.json()["events"]:
            assert event["cloud_cover_pct"] is None
            assert event["weather_description"] is None

    def test_no_events_returns_empty_list(self, client, monkeypatch):
        _patch_build_calendar(monkeypatch, value=[])
        response = client.get("/api/calendar", params=PARIS)
        assert response.status_code == 200
        assert response.json()["events"] == []

    def test_default_window_days(self, client, monkeypatch):
        _patch_build_calendar(monkeypatch, value=[])
        response = client.get("/api/calendar", params=PARIS)
        assert response.json()["window_days"] == pytest.approx(
            calendar_events.DEFAULT_CALENDAR_WINDOW_DAYS
        )

    def test_custom_days_param_is_forwarded(self, client, monkeypatch):
        mock_build = _patch_build_calendar(monkeypatch, value=[])
        response = client.get(
            "/api/calendar", params={"coordinates": "Paris, France", "days": 7}
        )
        assert response.status_code == 200
        assert response.json()["window_days"] == pytest.approx(7.0)
        _, kwargs = mock_build.call_args
        assert kwargs["window_days"] == pytest.approx(7.0)


class TestCalendarEndpointErrors:
    """Tests for error conditions on the ``/api/calendar`` endpoint."""

    def test_ephemeris_unavailable_returns_503(self, client, monkeypatch):
        _patch_build_calendar(
            monkeypatch,
            error=calendar_events.EphemerisUnavailableError("not loaded"),
        )
        response = client.get("/api/calendar", params=PARIS)
        assert response.status_code == 503

    def test_ambiguous_municipality_returns_409(self, client):
        response = client.get("/api/calendar", params={"coordinates": "Paris"})
        assert response.status_code == 409

    def test_unknown_municipality_returns_404(self, client):
        response = client.get(
            "/api/calendar", params={"coordinates": "Nowhereville, Nowhere"}
        )
        assert response.status_code == 404

    def test_invalid_raw_coordinates_returns_400(self, client):
        response = client.get("/api/calendar", params={"coordinates": "200, 50"})
        assert response.status_code == 400

    def test_missing_coordinates_returns_422(self, client):
        response = client.get("/api/calendar", params={})
        assert response.status_code == 422

    def test_days_out_of_range_returns_422(self, client):
        response = client.get(
            "/api/calendar", params={"coordinates": "Paris, France", "days": 0}
        )
        assert response.status_code == 422

    def test_days_above_max_returns_422(self, client):
        response = client.get(
            "/api/calendar", params={"coordinates": "Paris, France", "days": 91}
        )
        assert response.status_code == 422

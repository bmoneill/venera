"""Tests for the /api/viewrec endpoint."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend import viewrec
from backend.visibility import ViewingMoment

MARS_IN_PARIS = {"name": "Mars", "coordinates": "Paris, France"}


def _patch_visibility(monkeypatch, moment):
    """Patch ``viewrec.visibility.find_next_viewing_window`` to return ``moment``."""
    mock_find = MagicMock(return_value=moment)
    monkeypatch.setattr(viewrec.visibility, "find_next_viewing_window", mock_find)
    return mock_find


SAMPLE_MOMENT = ViewingMoment(
    time=datetime(2024, 6, 1, 22, 30, tzinfo=timezone.utc),
    altitude_degrees=42.5,
    azimuth_degrees=180.0,
    sun_altitude_degrees=-15.0,
)


# ---------------------------------------------------------------------------
# Visible cases
# ---------------------------------------------------------------------------


class TestViewRecVisible:
    """Tests for when a clear-view moment is found."""

    def test_returns_200_and_visible_true(self, client, monkeypatch):
        _patch_visibility(monkeypatch, SAMPLE_MOMENT)
        response = client.get("/api/viewrec", params=MARS_IN_PARIS)
        assert response.status_code == 200
        data = response.json()
        assert data["visible"] is True
        assert data["name"] == "Mars"
        assert data["type"] == "Planet"

    def test_returns_altaz_and_sun_altitude(self, client, monkeypatch):
        _patch_visibility(monkeypatch, SAMPLE_MOMENT)
        response = client.get("/api/viewrec", params=MARS_IN_PARIS)
        data = response.json()
        assert data["altitude_degrees"] == pytest.approx(42.5)
        assert data["azimuth_degrees"] == pytest.approx(180.0)
        assert data["sun_altitude_degrees"] == pytest.approx(-15.0)

    def test_returns_recommended_time(self, client, monkeypatch):
        _patch_visibility(monkeypatch, SAMPLE_MOMENT)
        response = client.get("/api/viewrec", params=MARS_IN_PARIS)
        data = response.json()
        assert data["time"].startswith("2024-06-01")

    def test_response_includes_resolved_location(self, client, monkeypatch):
        _patch_visibility(monkeypatch, SAMPLE_MOMENT)
        response = client.get("/api/viewrec", params=MARS_IN_PARIS)
        assert response.json()["location"] == "Paris, Ile-de-France, France"

    def test_object_lookup_is_case_insensitive(self, client, monkeypatch):
        _patch_visibility(monkeypatch, SAMPLE_MOMENT)
        response = client.get(
            "/api/viewrec", params={"name": "MARS", "coordinates": "Paris, France"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Mars"

    def test_named_star_type_is_star(self, client, monkeypatch):
        _patch_visibility(monkeypatch, SAMPLE_MOMENT)
        response = client.get(
            "/api/viewrec", params={"name": "Sirius", "coordinates": "Paris, France"}
        )
        assert response.status_code == 200
        assert response.json()["type"] == "Star"

    def test_message_mentions_location_and_time(self, client, monkeypatch):
        _patch_visibility(monkeypatch, SAMPLE_MOMENT)
        response = client.get("/api/viewrec", params=MARS_IN_PARIS)
        message = response.json()["message"]
        assert "Paris" in message
        assert "2024-06-01" in message


# ---------------------------------------------------------------------------
# Not-visible case
# ---------------------------------------------------------------------------


class TestViewRecNotVisible:
    """Tests for when no clear-view moment is found in the search window."""

    def test_returns_200_with_visible_false(self, client, monkeypatch):
        _patch_visibility(monkeypatch, None)
        response = client.get("/api/viewrec", params=MARS_IN_PARIS)
        assert response.status_code == 200
        data = response.json()
        assert data["visible"] is False
        assert data["time"] is None
        assert data["altitude_degrees"] is None

    def test_message_explains_no_window_found(self, client, monkeypatch):
        _patch_visibility(monkeypatch, None)
        response = client.get("/api/viewrec", params=MARS_IN_PARIS)
        assert "not be in clear view" in response.json()["message"]


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestViewRecErrors:
    """Tests for error conditions on the /api/viewrec endpoint."""

    def test_unknown_object_returns_404(self, client):
        response = client.get(
            "/api/viewrec",
            params={"name": "Nonexistent Object XYZ", "coordinates": "Paris, France"},
        )
        assert response.status_code == 404

    def test_ambiguous_municipality_returns_409(self, client):
        response = client.get(
            "/api/viewrec", params={"name": "Mars", "coordinates": "Paris"}
        )
        assert response.status_code == 409

    def test_unknown_municipality_returns_404(self, client):
        response = client.get(
            "/api/viewrec",
            params={"name": "Mars", "coordinates": "Nowhereville, Nowhere"},
        )
        assert response.status_code == 404

    def test_invalid_raw_coordinates_returns_400(self, client):
        response = client.get(
            "/api/viewrec", params={"name": "Mars", "coordinates": "200, 50"}
        )
        assert response.status_code == 400

    def test_missing_coordinates_returns_422(self, client):
        response = client.get("/api/viewrec", params={"name": "Mars"})
        assert response.status_code == 422

    def test_missing_name_returns_422(self, client):
        response = client.get("/api/viewrec", params={"coordinates": "Paris, France"})
        assert response.status_code == 422

    def test_requires_authentication(self):
        from fastapi.testclient import TestClient as PlainClient

        from backend.main import app

        with PlainClient(app) as plain_client:
            response = plain_client.get("/api/viewrec", params=MARS_IN_PARIS)
        assert response.status_code == 401
